from __future__ import annotations

from testing.steps.definitions import ActionContext, action_plan, action_step_enabled, get_action


def test_step_definitions_include_android_and_storage_plans() -> None:
    plan = action_plan(["android_client.prepare_request", "storage.emmc.copy_file"])

    assert [step["definition_id"] for step in plan] == [
        "android_client.prepare_request",
        "storage.emmc.copy_file",
    ]
    assert plan[1]["id"] == "emmc_rw.cycle.copy_file"


def test_step_definition_check_uses_dut_executor() -> None:
    class Dut:
        def ping(self, *, hostname: str) -> bool:
            return hostname == "192.168.1.1"

    action = get_action("network.ping")
    context = ActionContext(case_id="ac_onoff", params={"ac_onoff:ping_target": "192.168.1.1"}, dut=Dut())

    assert action.executor is not None
    assert action.executor(context) is True


def test_step_definition_planner_disables_empty_choice_params() -> None:
    step = {"definition_id": "bluetooth.verify_target"}

    assert action_step_enabled(step, case_id="ac_onoff", params={"ac_onoff:bt_target": ""}) is False
    assert (
        action_step_enabled(
            step,
            case_id="ac_onoff",
            params={"ac_onoff:bt_target": "Speaker 11:22:33:44:55:66"},
        )
        is True
    )
