#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$DIR/build"
UF2="$BUILD_DIR/hexapod_firmware.uf2"

# ── Build ─────────────────────────────────────────────────────────────
echo "building firmware..."
PIMORONI_PICO_PATH="$(realpath "$DIR/../pimoroni-pico")" cmake -B "$BUILD_DIR" -S "$DIR" -DCMAKE_BUILD_TYPE=Release > /dev/null 2>&1
cmake --build "$BUILD_DIR" -j 2>&1 | tail -3

if [ ! -f "$UF2" ]; then
    echo "error: build failed — $UF2 not found"
    exit 1
fi
echo "built: $UF2"

# ── Select device ─────────────────────────────────────────────────────
echo ""
echo "scanning for ACM devices..."
DEVICES=()
while IFS= read -r dev; do
    DEVICES+=("$dev")
done < <(ls /dev/ttyACM* 2>/dev/null || true)

if [ ${#DEVICES[@]} -eq 0 ]; then
    echo "no /dev/ttyACM* devices found"
    exit 1
fi

# Build a display list with serial numbers.
echo "found ${#DEVICES[@]} device(s):"
SERIALS=()
for i in "${!DEVICES[@]}"; do
    ser=$(udevadm info --name="${DEVICES[$i]}" 2>/dev/null \
          | grep ID_SERIAL_SHORT= | head -1 | cut -d= -f2)
    SERIALS+=("$ser")
    echo "  [$i] ${DEVICES[$i]}  (serial: ${ser:-unknown})"
done
echo ""

TARGET=""
SERIAL=""
for i in "${!DEVICES[@]}"; do
    read -r -p "flash to ${DEVICES[$i]}? [y/N] " ans
    if [[ "$ans" =~ ^[Yy]$ ]]; then
        TARGET="${DEVICES[$i]}"
        SERIAL="${SERIALS[$i]}"
        break
    fi
done

if [ -z "$TARGET" ]; then
    echo "no device selected — aborting"
    exit 0
fi

# ── Flash ─────────────────────────────────────────────────────────────
echo ""
echo "flashing $UF2 → $TARGET (serial: ${SERIAL:-unknown}) ..."
if [ -n "$SERIAL" ]; then
    picotool load -f --ser "$SERIAL" "$UF2"
else
    picotool load -f "$UF2"
fi
echo "done — device should reboot as $TARGET"
