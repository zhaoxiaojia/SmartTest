from __future__ import annotations

from .core import ActionDefinition, register_action


register_action(
    ActionDefinition(
        definition_id="storage.emmc.prepare_request",
        title="Prepare eMMC read/write request",
        kind="step",
    )
)
register_action(
    ActionDefinition(
        definition_id="storage.emmc.trigger_execution",
        title="Trigger eMMC read/write execution",
        kind="step",
    )
)
register_action(
    ActionDefinition(
        definition_id="storage.emmc.copy_file",
        title="Cycle: copy file",
        kind="step",
        plan_id="emmc_rw.cycle.copy_file",
    )
)
register_action(
    ActionDefinition(
        definition_id="storage.emmc.read_file",
        title="Cycle: read back file",
        kind="step",
        plan_id="emmc_rw.cycle.read_file",
    )
)
register_action(
    ActionDefinition(
        definition_id="storage.emmc.cmp_file",
        title="Cycle: compare file",
        kind="check",
        plan_id="emmc_rw.cycle.cmp_file",
    )
)
