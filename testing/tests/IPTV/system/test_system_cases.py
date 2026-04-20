from __future__ import annotations

import os

import pytest

from testing.runner.android_client import build_case_params, trigger_android_client_case


pytestmark = pytest.mark.case_type("system")


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


def test_cpu_freq_switch_via_android_client(request):
    trigger_android_client_case(case_id="cpu_freq_switch", trigger=request.node.nodeid)


@pytest.mark.requires_params(
    "emmc_rw:loop_count",
    "emmc_rw:source_profile",
    "emmc_rw:source_size_kb",
    "emmc_rw:min_free_kb",
    "emmc_rw:work_dir",
)
def test_emmc_rw_via_android_client(request):
    trigger_android_client_case(
        case_id="emmc_rw",
        params=build_case_params(
            "emmc_rw",
            loop_count=_env_int("SMARTTEST_EMMC_LOOP_COUNT", 1),
            source_profile=os.environ.get("SMARTTEST_EMMC_SOURCE_PROFILE", "random1"),
            source_size_kb=_env_int("SMARTTEST_EMMC_SOURCE_SIZE_KB", 51200),
            min_free_kb=_env_int("SMARTTEST_EMMC_MIN_FREE_KB", 307200),
            work_dir=os.environ.get("SMARTTEST_EMMC_WORK_DIR", "/data/local/tmp/smarttest/emmc_rw"),
        ),
        trigger=request.node.nodeid,
    )


def test_ddr_stress_via_android_client(request):
    trigger_android_client_case(case_id="ddr_stress", trigger=request.node.nodeid)


def test_thermal_control_via_android_client(request):
    trigger_android_client_case(case_id="thermal_control", trigger=request.node.nodeid)


def test_relay_power_cycle_via_android_client(request):
    trigger_android_client_case(case_id="relay_power_cycle", trigger=request.node.nodeid)


@pytest.mark.requires_params(
    "auto_reboot:cycle_count",
    "auto_reboot:interval_sec",
)
def test_auto_reboot_via_android_client(request):
    trigger_android_client_case(
        case_id="auto_reboot",
        params=build_case_params(
            "auto_reboot",
            cycle_count=_env_int("SMARTTEST_AUTO_REBOOT_CYCLE_COUNT", 1),
            interval_sec=_env_int("SMARTTEST_AUTO_REBOOT_INTERVAL_SEC", 10),
        ),
        trigger=request.node.nodeid,
    )


@pytest.mark.requires_params(
    "auto_suspend:cycle_count",
    "auto_suspend:interval_sec",
)
def test_auto_suspend_via_android_client(request):
    trigger_android_client_case(
        case_id="auto_suspend",
        params=build_case_params(
            "auto_suspend",
            cycle_count=_env_int("SMARTTEST_AUTO_SUSPEND_CYCLE_COUNT", 1),
            interval_sec=_env_int("SMARTTEST_AUTO_SUSPEND_INTERVAL_SEC", 10),
        ),
        trigger=request.node.nodeid,
    )


def test_ota_loop_via_android_client(request):
    trigger_android_client_case(case_id="ota_loop", trigger=request.node.nodeid)


def test_factory_reset_loop_via_android_client(request):
    trigger_android_client_case(case_id="factory_reset_loop", trigger=request.node.nodeid)


def test_eth_toggle_via_android_client(request):
    trigger_android_client_case(case_id="eth_toggle", trigger=request.node.nodeid)


def test_network_regression_via_android_client(request):
    trigger_android_client_case(case_id="network_regression", trigger=request.node.nodeid)
