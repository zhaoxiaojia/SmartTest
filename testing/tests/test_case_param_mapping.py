from __future__ import annotations

import sys
from pathlib import Path

from testing.cases.discovery import discover_pytest_cases
from testing.params.registry import default_registry


ROOT_DIR = Path(__file__).resolve().parents[2]


def test_default_registry_resolves_group_members():
    registry = default_registry()

    assert registry.resolve_param_keys(group_ids=["dut_identity"]) == [
        "dut_model",
        "dut_sn",
        "fw_version",
    ]
    assert registry.resolve_param_keys(group_ids=["stress_runtime"]) == [
        "duration_s",
        "concurrency",
        "warmup_s",
    ]


def test_default_registry_rejects_unknown_group():
    registry = default_registry()

    try:
        registry.resolve_param_keys(group_ids=["missing_group"])
    except KeyError as exc:
        assert "missing_group" in str(exc)
    else:
        raise AssertionError("Expected resolve_param_keys() to reject an unknown group.")


def test_discovery_exports_required_params_and_empty_cases():
    cases = discover_pytest_cases(
        root_dir=ROOT_DIR,
        test_paths=[
            ROOT_DIR / "testing" / "tests" / "test_demo_stress.py",
            ROOT_DIR / "testing" / "tests" / "test_demo_smoke.py",
        ],
        python_executable=sys.executable,
    )

    cases_by_nodeid = {case.nodeid: case for case in cases}

    throughput_cases = [
        case
        for nodeid, case in cases_by_nodeid.items()
        if nodeid.startswith("testing/tests/test_demo_stress.py::test_stress_throughput_placeholder[")
    ]
    assert throughput_cases
    for case in throughput_cases:
        assert case.required_param_groups == ["dut_identity", "stress_runtime"]
        assert case.required_params == [
            "dut_model",
            "dut_sn",
            "fw_version",
            "duration_s",
            "concurrency",
            "warmup_s",
        ]

    regression_case = cases_by_nodeid["testing/tests/test_demo_stress.py::test_stress_regression_placeholder"]
    assert regression_case.required_param_groups == []
    assert regression_case.required_params == ["operator"]

    smoke_case = cases_by_nodeid["testing/tests/test_demo_smoke.py::test_smoke_basic_math"]
    assert smoke_case.required_param_groups == []
    assert smoke_case.required_params == []
