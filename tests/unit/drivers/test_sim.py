from hexapod.api.dto import JointAngles
from hexapod.core.enums import Segment, Side
from hexapod.core.hexapod import Hexapod
from hexapod.drivers.sim import SimDriver


def test_write_then_read_round_trips(hexapod: Hexapod):
    drv = SimDriver(hexapod)
    cmds = {
        (seg, side): JointAngles(0.1, 0.2, 0.3)
        for seg in Segment
        for side in Side
    }
    drv.write(cmds)
    read = drv.read()
    assert read is not None
    for k, v in cmds.items():
        assert read[k] == v


def test_contacts_reflect_foot_z(hexapod: Hexapod):
    drv = SimDriver(hexapod)
    contacts = drv.read_contacts()
    assert contacts is not None
    assert set(contacts.keys()) == {
        (seg, side) for seg in Segment for side in Side
    }
    for v in contacts.values():
        assert isinstance(v, bool)
