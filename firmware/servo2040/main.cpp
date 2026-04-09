// Hexapod firmware for the Pimoroni Servo2040.
//
// Talks to the host (Python HostSerialDriver) over USB CDC using the binary
// protocol defined in src/hexapod/drivers/servo/protocol.py:
//
//   Command  (host -> MCU): 0xA5 | 18 x uint16 LE pulse_us | XOR  =  38 B
//   Feedback (MCU -> host): 0x5A | contact_bits             | XOR  =   3 B
//
// Behavior:
//   * Each valid command frame is applied to the ServoCluster immediately.
//     The PIO PWM hardware holds the pulse autonomously between frames.
//   * Watchdog: if no valid frame arrives for WATCHDOG_MS, all servos are
//     disabled (output goes to known-safe high-impedance).
//   * Feedback frames are emitted at FEEDBACK_HZ. Contact bits are stubbed
//     to zero — wire 6 bumper switches to the SENSOR_1..6 pins and replace
//     read_contacts() with the real read.
//
// IMPORTANT: any change to the on-wire format MUST be mirrored in
// src/hexapod/drivers/servo/protocol.py.

#include <cstdint>
#include <cstdio>

#include "pico/stdlib.h"
#include "servo2040.hpp"
#include "analog.hpp"
#include "analogmux.hpp"

using namespace servo;

// ── protocol constants (mirror of protocol.py) ─────────────────────────────
static constexpr uint8_t  CMD_START      = 0xA5;
static constexpr uint8_t  FB_START       = 0x5A;
static constexpr uint     NUM_CHANNELS   = 18;
static constexpr uint     CMD_FRAME_LEN  = 1 + NUM_CHANNELS * 2 + 1;  // 38
static constexpr uint     FB_FRAME_LEN   = 1 + 1 + 1;                 // 3

// ── timing ─────────────────────────────────────────────────────────────────
static constexpr uint32_t WATCHDOG_MS    = 500;
static constexpr uint32_t FEEDBACK_MS    = 20;   // 50 Hz feedback
static constexpr uint32_t SLEW_MS        = 5;    // 200 Hz inner loop

// Max servo slew rate. Derived from the profile in
// config/servos/ds3235ssg.yaml:
//   max_speed_dps * (pulse_max - pulse_min) / (angle_max - angle_min)
//   = 460 dps * 2000 us / 270 deg ≈ 3407 us/sec
// Tune here when you change servo class. Lower = smoother but laggier.
static constexpr float MAX_PULSE_PER_SEC = 3407.0f;

// Pulse value the cluster sits at when enabled — used to seed current/target
// after init and after a watchdog re-arm so the slew limiter starts coherent.
static constexpr float MID_PULSE_US = 1500.0f;

// ── servo cluster ──────────────────────────────────────────────────────────
// All 18 servos on PIO0 SM0, starting at SERVO_1 (GPIO 0).
static ServoCluster cluster(pio0, 0, servo2040::SERVO_1, NUM_CHANNELS);

// ── contact sensors ────────────────────────────────────────────────────────
// The Servo2040 has 6 analog SENSOR inputs sharing a single ADC via a 3:8
// analog mux. We configure pull-downs and read each sensor digitally — any
// reading above SENSOR_THRESHOLD_V counts as "in contact". Wire a momentary
// switch from 3.3V to a SENSOR pin to act as a bumper.
//
// Mapping (must match CONTACT_ORDER in src/hexapod/drivers/servo/protocol.py):
//   SENSOR_1 → bit 0 → front_left
//   SENSOR_2 → bit 1 → front_right
//   SENSOR_3 → bit 2 → mid_left
//   SENSOR_4 → bit 3 → mid_right
//   SENSOR_5 → bit 4 → rear_left
//   SENSOR_6 → bit 5 → rear_right
static constexpr float SENSOR_THRESHOLD_V = 1.0f;

static Analog    sen_adc(servo2040::SHARED_ADC);
static AnalogMux mux(servo2040::ADC_ADDR_0,
                     servo2040::ADC_ADDR_1,
                     servo2040::ADC_ADDR_2,
                     PIN_UNUSED,
                     servo2040::SHARED_ADC);

// ── frame parser state ─────────────────────────────────────────────────────
static uint8_t  rx_buf[CMD_FRAME_LEN];
static uint     rx_len = 0;

// ── slew limiter state ─────────────────────────────────────────────────────
// target_pulse is what the host most recently asked for; current_pulse is
// what we're actually driving the servo with. The 200 Hz inner loop walks
// current toward target at MAX_PULSE_PER_SEC.
static float target_pulse[NUM_CHANNELS];
static float current_pulse[NUM_CHANNELS];

static void seed_pulses(float v) {
    for (uint i = 0; i < NUM_CHANNELS; ++i) {
        target_pulse[i] = v;
        current_pulse[i] = v;
    }
}

static uint8_t xor_checksum(const uint8_t *data, uint len) {
    uint8_t c = 0;
    for (uint i = 0; i < len; ++i) c ^= data[i];
    return c;
}

static void apply_frame(const uint8_t *frame) {
    // Decode 18 little-endian uint16 pulse widths into target_pulse[]. The
    // 200 Hz slew loop owns what's actually written to the cluster — we
    // never touch the PIO directly here, otherwise we'd undo the smoothing.
    for (uint i = 0; i < NUM_CHANNELS; ++i) {
        uint16_t lo = frame[1 + i * 2];
        uint16_t hi = frame[1 + i * 2 + 1];
        target_pulse[i] = (float)(lo | (hi << 8));
    }
}

static void slew_step(float dt_s) {
    // Walk current_pulse[] toward target_pulse[] by at most MAX_PULSE_PER_SEC
    // in this dt window. Then push everything into the cluster atomically.
    const float max_step = MAX_PULSE_PER_SEC * dt_s;
    for (uint i = 0; i < NUM_CHANNELS; ++i) {
        float d = target_pulse[i] - current_pulse[i];
        if (d > max_step)       d = max_step;
        else if (d < -max_step) d = -max_step;
        current_pulse[i] += d;
        cluster.pulse((uint8_t)i, current_pulse[i], false);
    }
    cluster.load();
}

static bool poll_input() {
    // Drain whatever the host sent since last poll. Returns true iff a valid
    // command frame was applied (used to pet the watchdog).
    bool applied = false;
    for (;;) {
        int c = getchar_timeout_us(0);
        if (c == PICO_ERROR_TIMEOUT) break;
        uint8_t b = (uint8_t)c;

        // Resync rule: drop bytes until we see the start sentinel.
        if (rx_len == 0 && b != CMD_START) continue;

        rx_buf[rx_len++] = b;

        if (rx_len == CMD_FRAME_LEN) {
            uint8_t want = rx_buf[CMD_FRAME_LEN - 1];
            uint8_t got  = xor_checksum(rx_buf, CMD_FRAME_LEN - 1);
            if (got == want) {
                apply_frame(rx_buf);
                applied = true;
                rx_len = 0;
            } else {
                // Bad checksum — slide one byte and resync.
                for (uint i = 1; i < CMD_FRAME_LEN; ++i)
                    rx_buf[i - 1] = rx_buf[i];
                rx_len = CMD_FRAME_LEN - 1;
                // Find the next plausible start in what's left.
                while (rx_len > 0 && rx_buf[0] != CMD_START) {
                    for (uint i = 1; i < rx_len; ++i)
                        rx_buf[i - 1] = rx_buf[i];
                    --rx_len;
                }
            }
        }
    }
    return applied;
}

static uint8_t read_contacts() {
    // Walk all 6 sensor inputs through the mux. A reading above the
    // threshold means the bumper switch is pressed (3.3 V → input);
    // released sits near 0 V because of the configured pull-down.
    uint8_t bits = 0;
    for (uint i = 0; i < servo2040::NUM_SENSORS; ++i) {
        mux.select(servo2040::SENSOR_1_ADDR + i);
        if (sen_adc.read_voltage() > SENSOR_THRESHOLD_V) {
            bits |= (uint8_t)(1u << i);
        }
    }
    return bits;
}

static void send_feedback() {
    uint8_t body[2] = { FB_START, read_contacts() };
    uint8_t cs = xor_checksum(body, 2);
    putchar_raw(body[0]);
    putchar_raw(body[1]);
    putchar_raw(cs);
}

int main() {
    stdio_init_all();

    cluster.init();
    cluster.enable_all();         // PIO outputs come up at mid pulse
    seed_pulses(MID_PULSE_US);    // keep slew state coherent with hardware

    // Enable pull-downs on every sensor input. Open inputs read ~0 V; a
    // bumper switch shorting the pin to 3.3 V drives it high.
    for (uint i = 0; i < servo2040::NUM_SENSORS; ++i) {
        mux.configure_pulls(servo2040::SENSOR_1_ADDR + i, false, true);
    }

    absolute_time_t last_frame    = get_absolute_time();
    absolute_time_t last_slew     = get_absolute_time();
    absolute_time_t next_slew     = make_timeout_time_ms(SLEW_MS);
    absolute_time_t next_feedback = make_timeout_time_ms(FEEDBACK_MS);
    bool armed = true;

    while (true) {
        if (poll_input()) {
            last_frame = get_absolute_time();
            if (!armed) {
                cluster.enable_all();
                seed_pulses(MID_PULSE_US);
                last_slew = get_absolute_time();
                armed = true;
            }
        }

        // Watchdog: lose comms -> disable outputs (servos go limp). The host
        // can re-arm by simply sending a fresh frame.
        if (armed && absolute_time_diff_us(last_frame, get_absolute_time())
                       > (int64_t)WATCHDOG_MS * 1000) {
            cluster.disable_all();
            armed = false;
        }

        // 200 Hz slew step — only meaningful while armed.
        if (armed && absolute_time_diff_us(get_absolute_time(), next_slew) <= 0) {
            absolute_time_t now = get_absolute_time();
            float dt_s = (float)absolute_time_diff_us(last_slew, now) / 1e6f;
            last_slew = now;
            next_slew = make_timeout_time_ms(SLEW_MS);
            slew_step(dt_s);
        }

        if (absolute_time_diff_us(get_absolute_time(), next_feedback) <= 0) {
            send_feedback();
            next_feedback = make_timeout_time_ms(FEEDBACK_MS);
        }

        sleep_us(200);
    }
}
