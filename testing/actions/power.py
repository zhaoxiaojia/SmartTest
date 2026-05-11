from __future__ import annotations

from .core import ActionDefinition, register_action


register_action(
    ActionDefinition(
        definition_id="power.auto_reboot.prepare",
        title="Prepare auto reboot request",
        kind="setup",
        plan_id="auto_reboot.prepare",
    )
)
register_action(
    ActionDefinition(
        definition_id="power.reboot",
        title="Cycle: reboot DUT",
        kind="step",
        plan_id="auto_reboot.cycle.reboot",
    )
)
register_action(
    ActionDefinition(
        definition_id="power.wait_resume",
        title="Cycle: wait for DUT resume",
        kind="step",
        plan_id="auto_reboot.cycle.wait_resume",
    )
)
register_action(
    ActionDefinition(
        definition_id="power.wait_interval",
        title="Cycle: wait interval {auto_reboot:interval_sec}s",
        kind="step",
        plan_id="auto_reboot.cycle.wait_interval",
    )
)
register_action(
    ActionDefinition(
        definition_id="power.capture_radio_state",
        title="Cycle: capture radio state",
        kind="check",
        plan_id="auto_reboot.cycle.capture_radio_state",
    )
)
