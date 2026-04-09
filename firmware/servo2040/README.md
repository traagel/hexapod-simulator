# Servo2040 firmware

C++ firmware for the Pimoroni Servo2040 implementing the binary protocol from
`src/hexapod/drivers/servo/protocol.py`.

- Receives 38-byte command frames over USB CDC, applies the 18 pulse widths
  to the `ServoCluster` (PIO-driven PWM, no host-side smoothing required).
- Emits a 3-byte feedback frame at 50 Hz with per-leg contact bits (currently
  stubbed to zero — wire bumpers and replace `read_contacts()` in `main.cpp`).
- Watchdog: if no valid command arrives for 500 ms, all servos are disabled.

## Toolchain

Arch Linux:

    sudo pacman -S arm-none-eabi-gcc arm-none-eabi-newlib pico-sdk picotool cmake

`pico-sdk` lands at `/usr/share/pico-sdk` — `PICO_SDK_PATH` is exported by the
package's profile script.

`pimoroni-pico` is not packaged; it's cloned (shallow) into
`firmware/pimoroni-pico/`. To re-clone:

    git clone --depth 1 https://github.com/pimoroni/pimoroni-pico.git \
        ../pimoroni-pico

## Build

From this directory:

    PIMORONI_PICO_PATH=$(realpath ../pimoroni-pico) cmake -B build
    cmake --build build -j

Output: `build/hexapod_firmware.uf2`.

## Flash

1. Hold **BOOTSEL** on the Servo2040 and plug it in (or reset while held).
2. It enumerates as a USB mass-storage device named `RPI-RP2`. Mount it.
3. Copy the UF2:

       cp build/hexapod_firmware.uf2 /run/media/$USER/RPI-RP2/

4. The board reboots and re-enumerates as `/dev/ttyACM0`.

Or with `picotool` (no manual mount needed):

    picotool load -f build/hexapod_firmware.uf2

## Wire format

See `src/hexapod/drivers/servo/protocol.py` — that file is the canonical
reference. The constants in `main.cpp` (`CMD_START`, `FB_START`,
`CMD_FRAME_LEN`, `FB_FRAME_LEN`, channel order) must stay in sync with it.
