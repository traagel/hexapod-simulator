"""Config loader: symmetric mount expansion, joint defaults, sign-flip."""

from pathlib import Path

from hexapod.core import config
from hexapod.core.enums import Segment, Side

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "hexapod.yaml"


def test_loads_all_six_legs():
    cfg = config.load(CONFIG_PATH)
    assert set(cfg["legs"].keys()) == {
        (seg, side) for seg in Segment for side in Side
    }


def test_right_side_mount_y_mirrored():
    cfg = config.load(CONFIG_PATH)
    for seg in Segment:
        lx, ly = cfg["legs"][(seg, Side.LEFT)]["mount"]
        rx, ry = cfg["legs"][(seg, Side.RIGHT)]["mount"]
        assert lx == rx
        assert ly == -ry


def test_height_present():
    cfg = config.load(CONFIG_PATH)
    assert cfg["height"] > 0
