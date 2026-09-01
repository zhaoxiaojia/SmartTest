from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from core.testing.params.adb_devices import list_adb_devices
from core.testing.params.contracts import env_dynamic_sources
from core.testing.params.options import dynamic_param_options, normalize_option_values
from core.logging import smart_log

DutFactory = Callable[[str | None], Any]
DeviceLister = Callable[[], list[str]]
ApkEnsurer = Callable[..., bool]
StageCallback = Callable[[str, int, str], None]


@dataclass(frozen=True)
class CaseParameterOptionsResult:
    source: str
    dut_serial: str
    options: list[str] = field(default_factory=list)
    error: str = ""


@dataclass(frozen=True)
class ContextRefreshResult:
    param_results: list[dict[str, Any]] = field(default_factory=list)
    env_results: list[dict[str, Any]] = field(default_factory=list)


class ParameterHelper:
    """
    Single boundary for UI-triggered DUT discovery and contract-driven dynamic loading.
    """

    def __init__(
        self,
        *,
        device_lister: DeviceLister | None = None,
        dut_factory: DutFactory | None = None,
        apk_ensurer: ApkEnsurer | None = None,
        to_thread=None,
    ) -> None:
        self._device_lister = device_lister or list_adb_devices
        self._dut_factory = dut_factory or _android_dut
        self._apk_ensurer = apk_ensurer
        self._to_thread = to_thread or asyncio.to_thread

    def refresh_duts(self, selected_serial: str | None = None) -> list[str]:
        try:
            devices = _dedupe_strings(self._device_lister())
        except Exception as exc:
            smart_log(f"refresh_duts error={exc}", domain="dut", level="error", source="ParameterHelper")
            return []
        smart_log(f"refresh_duts devices={devices}", domain="dut", source="ParameterHelper")
        return devices

    async def refresh_duts_async(self, selected_serial: str | None = None) -> list[str]:
        return await self._to_thread(self.refresh_duts, selected_serial=selected_serial)

    def prepare_android_client(
        self,
        selected_serial: str,
        *,
        stage_callback: StageCallback | None = None,
    ) -> bool:
        target = str(selected_serial or "").strip()
        if not target:
            raise ValueError("Android Client preparation requires a selected DUT.")
        if self._apk_ensurer is None:
            raise RuntimeError("Android Client preparation requires an APK provisioning owner.")
        smart_log(f"apk_ensure_start dut={target}", domain="dut", source="ParameterHelper")
        installed = self._apk_ensurer(
            adb_serial=target,
            require_privileged=True,
            stage_callback=stage_callback,
        )
        smart_log(f"apk_ensure_done dut={target} installed={installed}", domain="dut", source="ParameterHelper")
        return bool(installed)

    async def prepare_android_client_async(
        self,
        selected_serial: str,
        *,
        stage_callback: StageCallback | None = None,
    ) -> bool:
        return await self._to_thread(
            self.prepare_android_client,
            selected_serial,
            stage_callback=stage_callback,
        )

    def refresh_context(
        self,
        *,
        selected_serial: str | None,
        param_targets: list[dict[str, str]],
        env_targets: list[dict[str, str]],
    ) -> ContextRefreshResult:
        param_results = [
            {
                "field_key": str(target.get("field_key", "") or ""),
                "source": str(target.get("source", "") or ""),
                "nodeid": str(target.get("nodeid", "") or ""),
                **self.refresh_case_parameter_options(
                    str(target.get("source", "") or ""),
                    selected_serial,
                    nodeid=str(target.get("nodeid", "") or ""),
                ).__dict__,
            }
            for target in param_targets
        ]
        env_results = [self._refresh_env_target(target) for target in env_targets]
        return ContextRefreshResult(param_results=param_results, env_results=env_results)

    async def refresh_context_async(
        self,
        *,
        selected_serial: str | None,
        param_targets: list[dict[str, str]],
        env_targets: list[dict[str, str]],
    ) -> ContextRefreshResult:
        return await self._to_thread(
            self.refresh_context,
            selected_serial=selected_serial,
            param_targets=param_targets,
            env_targets=env_targets,
        )

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
        smart_log(
            "refresh_case_parameter_options "
            f"source={normalized_source or '<empty>'} dut={dut_serial or '<default>'} "
            f"nodeid={normalized_nodeid or '<none>'}",
            domain="dut",
            source="ParameterHelper",
        )
        if not normalized_source:
            return CaseParameterOptionsResult(source="", dut_serial=dut_serial)
        try:
            options = self._load_options(normalized_source, dut_serial or None, nodeid=normalized_nodeid)
        except Exception as exc:  # noqa: BLE001
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

    def env_targets_for_kind(self, *, kind: str, device_type: str) -> list[dict[str, str]]:
        return [
            {"kind": kind, "device_type": device_type, "field_key": field_key, "source": source}
            for field_key, source in env_dynamic_sources(kind, device_type)
        ]

    def _refresh_env_target(self, target: Mapping[str, str]) -> dict[str, Any]:
        kind = str(target.get("kind", "") or "").strip()
        device_type = str(target.get("device_type", "") or "").strip()
        field_key = str(target.get("field_key", "") or "").strip()
        source = str(target.get("source", "") or "").strip()
        try:
            options = self._load_env_options(source)
            error = ""
        except Exception as exc:  # noqa: BLE001
            options = []
            error = str(exc)
        return {
            "kind": kind,
            "device_type": device_type,
            "field_key": field_key,
            "source": source,
            "options": options,
            "error": error,
        }

    def _load_options(self, source: str, selected_serial: str | None, *, nodeid: str = "") -> list[str]:
        if source == "core.testing.tool.dut_tool.features.local_playback:list_media_dirs":
            from core.testing.tool.dut_tool.features.local_playback import list_media_dirs

            return list_media_dirs(dut=self._dut_factory(selected_serial))
        if source == "core.testing.tool.dut_tool.features.local_playback:list_media_files":
            from core.testing.tool.dut_tool.features.local_playback import list_media_files

            return list_media_files(self._dut_factory(selected_serial), nodeid=nodeid)
        if source == "core.testing.tool.dut_tool.features.system:list_cpu_frequency_options":
            return self._dut_factory(selected_serial).available_cpu_frequencies()
        return dynamic_param_options(source, selected_serial)

    def _load_env_options(self, source: str) -> list[str]:
        module_name, separator, function_name = str(source or "").strip().partition(":")
        if not module_name or separator != ":" or not function_name:
            raise ValueError(f"Invalid environment option source: {source}")
        module = __import__(module_name, fromlist=[function_name])
        provider = getattr(module, function_name)
        if not callable(provider):
            raise TypeError(f"Environment option source is not callable: {source}")
        return list(provider())


def _android_dut(selected_serial: str | None):
    from core.testing.tool.dut_tool.duts.android import android

    return android(serialnumber=str(selected_serial or "").strip())


def _dedupe_strings(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized
