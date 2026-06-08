from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from testing.params.adb_devices import list_adb_devices
from testing.params.options import dynamic_param_options, normalize_option_values

DutFactory = Callable[[str | None], Any]
DeviceLister = Callable[[], list[str]]


LOCAL_PLAYBACK_OPTIONS_SOURCE = "testing.tool.dut_tool.features.local_playback:list_media_files"
LOCAL_PLAYBACK_DIR_OPTIONS_SOURCE = "testing.tool.dut_tool.features.local_playback:list_media_dirs"
CPU_FREQUENCY_OPTIONS_SOURCE = "testing.tool.dut_tool.features.system:list_cpu_frequency_options"


@dataclass(frozen=True)
class CaseParameterOptionsResult:
    source: str
    dut_serial: str
    options: list[str] = field(default_factory=list)
    error: str = ""


class DutParameterAdapter:
    """
    Single boundary for UI-triggered DUT discovery and DUT-backed parameter options.
    """

    def __init__(
        self,
        *,
        device_lister: DeviceLister | None = None,
        dut_factory: DutFactory | None = None,
    ) -> None:
        self._device_lister = device_lister or list_adb_devices
        self._dut_factory = dut_factory or _android_dut

    def refresh_duts(self) -> list[str]:
        try:
            devices = _dedupe_strings(self._device_lister())
            print(f"[DutParameterAdapter.refresh_duts] devices={devices}")
            return devices
        except Exception as exc:
            print(f"[DutParameterAdapter.refresh_duts.error] error={exc}")
            return []

    def refresh_case_parameter_options(
        self,
        source: str,
        selected_serial: str | None,
        *,
        nodeid: str | None = None,
    ) -> CaseParameterOptionsResult:
        normalized_source = str(source or "").strip()
        dut_serial = str(selected_serial or "").strip()
        normalized_nodeid = str(nodeid or "").strip()
        print(
            "[DutParameterAdapter.refresh_case_parameter_options] "
            f"source={normalized_source or '<empty>'} dut={dut_serial or '<default>'} "
            f"nodeid={normalized_nodeid or '<none>'}"
        )
        if not normalized_source:
            return CaseParameterOptionsResult(source="", dut_serial=dut_serial)

        try:
            options = self._load_options(normalized_source, dut_serial or None, nodeid=normalized_nodeid)
        except Exception as exc:  # noqa: BLE001 - UI parameter discovery must not break page render
            return CaseParameterOptionsResult(
                source=normalized_source,
                dut_serial=dut_serial,
                options=[],
                error=str(exc),
            )

        return CaseParameterOptionsResult(
            source=normalized_source,
            dut_serial=dut_serial,
            options=normalize_option_values(options),
            error="",
        )

    def _load_options(self, source: str, selected_serial: str | None, *, nodeid: str = "") -> list[str]:
        if source == LOCAL_PLAYBACK_DIR_OPTIONS_SOURCE:
            from testing.tool.dut_tool.features.local_playback import list_media_dirs

            options = list_media_dirs(dut=self._dut_factory(selected_serial))
            print(
                "[DutParameterAdapter.local_playback_dir_options] "
                f"dut={selected_serial or '<default>'} options={len(options)}"
            )
            return options
        if source == LOCAL_PLAYBACK_OPTIONS_SOURCE:
            from testing.tool.dut_tool.features.local_playback import list_media_files

            options = list_media_files(self._dut_factory(selected_serial), nodeid=nodeid)
            print(
                "[DutParameterAdapter.local_playback_options] "
                f"dut={selected_serial or '<default>'} nodeid={nodeid or '<none>'} "
                f"options={len(options)}"
            )
            return options
        if source == CPU_FREQUENCY_OPTIONS_SOURCE:
            options = self._dut_factory(selected_serial).system.available_cpu_frequencies()
            print(
                "[DutParameterAdapter.cpu_frequency_options] "
                f"dut={selected_serial or '<default>'} options={len(options)}"
            )
            return options
        options = dynamic_param_options(source, selected_serial)
        print(
            "[DutParameterAdapter.dynamic_options] "
            f"source={source} dut={selected_serial or '<default>'} options={len(options)}"
        )
        return options


def _android_dut(selected_serial: str | None):
    from testing.tool.dut_tool.duts.android import android

    return android(serialnumber=str(selected_serial or "").strip())


def _dedupe_strings(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized
