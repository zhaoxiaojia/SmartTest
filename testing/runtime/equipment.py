from __future__ import annotations

from testing.tool.equipment import TestEquipment


_EQUIPMENT: TestEquipment | None = None


def test_equipment() -> TestEquipment:
    global _EQUIPMENT
    if _EQUIPMENT is None:
        _EQUIPMENT = TestEquipment.from_environment()
    return _EQUIPMENT


def reset_test_equipment() -> None:
    global _EQUIPMENT
    if _EQUIPMENT is not None:
        _EQUIPMENT.close()
    _EQUIPMENT = None
