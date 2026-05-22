from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from testing.cases.metadata import build_case_metadata
from testing.params.registry import default_registry


@dataclass(frozen=True)
class _Marker:
    name: str
    args: tuple[Any, ...] = ()


class _Item:
    nodeid = "testing/tests/android/stress/test_ac_onoff.py::test_ac_onoff_via_relay"
    name = "test_ac_onoff_via_relay"

    def __init__(self) -> None:
        self._markers = [
            _Marker("case_type", ("stress",)),
            _Marker("requires_equipment", ("relay",)),
            _Marker("requires_equipment", ("relay", "router")),
        ]

    def iter_markers(self, name: str | None = None):
        for marker in self._markers:
            if name is None or marker.name == name:
                yield marker

    def get_closest_marker(self, name: str):
        return next(self.iter_markers(name), None)


def test_build_case_metadata_exports_required_equipment_without_duplicates() -> None:
    metadata = build_case_metadata(_Item(), default_registry())

    assert metadata["case_type"] == "stress"
    assert metadata["required_equipment"] == ["relay", "router"]
