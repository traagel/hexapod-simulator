cmake_minimum_required(VERSION 3.12)

# Pull in the SDK and the Pimoroni libraries. Both expect environment vars
# (PICO_SDK_PATH and PIMORONI_PICO_PATH) — see README.md.
include(pico_sdk_import.cmake)
include(pimoroni_pico_import.cmake)

project(hexapod_firmware C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

# Pimoroni servo2040 library + its transitive deps.
include(common/pimoroni_i2c)
include(drivers/pwm/pwm)
include(drivers/pwm/pwm_cluster)
include(drivers/servo/servo)
include(drivers/servo/servo_cluster)
include(drivers/analog/analog)
include(drivers/analogmux/analogmux)
include(libraries/servo2040/servo2040)

add_executable(hexapod_firmware main.cpp)

target_link_libraries(hexapod_firmware
    pico_stdlib
    servo2040
    analog
    analogmux
)

# USB CDC for the binary protocol; UART off so it doesn't fight the servos.
pico_enable_stdio_usb(hexapod_firmware 1)
pico_enable_stdio_uart(hexapod_firmware 0)

pico_add_extra_outputs(hexapod_firmware)
