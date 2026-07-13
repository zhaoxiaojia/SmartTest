---
name: smarttest-case-development
description: Use when extracting SmartTest test cases from Excel, Word, images, or plans; assessing current automation coverage and equipment gaps; extending shared test capabilities; implementing pytest or Android-backed cases; and completing worker self-test plus main-Codex environment acceptance.
---

# SmartTest Case Development

## Core Rule

Convert source material into traceable executable requirements before editing code. Reuse and extend the current SmartTest parameter, DUT, equipment, step, log, run, and report paths. Do not invent a parallel flow or a case-specific workaround.

Also use:

- `smarttest-testing-workflow` for every change under `testing/**` or `android_client/**`.
- `smarttest-ui-workflow` for every change under `ui/**`.
- `smarttest-dual-codex-delivery` for implementation and acceptance.

## Phase Gates

Complete the phases in order. Do not start implementation until the source extraction and capability assessment are reviewable.

### 1. Extract a Case Requirement Card

Use a deterministic local extractor for spreadsheets and other structured sources. Write the normalized cards to a compact local manifest. Atlas reviews that manifest once; Mason receives only the approved batch manifest and must not reread the complete source workbook unless a cited source cell is genuinely ambiguous.

For every source case, record:

- identity: source file, sheet/range, original case id, title, module, priority, plan milestone;
- prerequisites: environment, DUT, PC, accounts/resources, and external equipment;
- parameters: machine key, type, default, scope, options source, UI exposure, `required_at_start`, units, and limits;
- pre-actions: executable setup actions separated from prerequisite states;
- steps: ordered `step_id`, action, inputs, expected transition, timeout, loop behavior, and failure policy;
- checkpoints: `definition_id`, measured object, method, expected value, tolerance, evidence, pass rule, skip rule, and equipment dependency;
- ambiguities: missing thresholds, resources, equipment, or mutually incompatible interpretations.

Preserve source identity through implementation, logs, reports, and acceptance evidence. Never silently infer missing product behavior.

### 2. Assess Existing Capability

Search existing cases and owners under `testing/params/`, `testing/runtime/`, `testing/steps/`, `testing/tool/`, DUT features, Android catalog/runner code, and related reports. Classify every required action and checkpoint as:

| Class | Meaning | Action |
|---|---|---|
| supported | Existing shared capability satisfies it | Reuse |
| partially-supported | Existing owner lacks a generic input, result, or check | Extend that owner |
| software-extension | Achievable through current PC/DUT interfaces | Design a reusable extension |
| external-equipment | Requires camera, audio analyzer, HDMI device, relay, router, or similar | Specify device and connection contract |
| manual | No stable automation interface or explicitly manual | Preserve preparation/evidence requirement |
| insufficient-information | Action, threshold, or expected result is unclear | Stop that case pending clarification |
| currently-impossible | Hardware, permission, or protocol blocks execution | Report evidence and blocker |

Do not declare support from filenames alone. Map each requirement to a concrete callable contract.

### 3. Design Shared Extensions

Use this preference order:

1. Reuse an existing implementation.
2. Add a generic parameter or result to the current business owner.
3. Consolidate duplicated actions into the existing owner.
4. Extend the appropriate DUT feature, step definition, equipment service, parameter contract, or Android runner.
5. Add a module only when no current owner fits.

Reject designs that create case-local ADB/serial/install/file helpers, private parameter conversion, duplicate UI/report steps, alternate parameter transport, or static handling for one case/value/file.

For cross-layer or large changes, define module ownership, public interfaces, parameter flow, execution flow, result/log flow, and compatibility before implementation.

### 4. Implement on Existing Flows

Define each case in five parts:

1. mandatory test objective and checkpoints;
2. dynamic parameters loaded through existing parameter contracts and `ParameterHelper`;
3. pre-actions that establish test state without hiding the core check;
4. declared test steps using the shared step/cycle lifecycle;
5. checkpoints producing explicit pass/fail/skip evidence.

Use the canonical parameter path:

```text
UI persisted state -> testing/params/runtime.py -> case/step/runner consumer
```

Use `tools/param_conversion.py` for conversion and `smart_log(...)` for runtime diagnostics. Share stable step and result identities with Run and Report. Treat a checkpoint value of `None` as "do not check" and omit it from APK requests.

### 5. Worker Self-Test

The worker must record starting `git status`, preserve user changes, implement only approved scope, add necessary tests, and report exact commands and exit codes. Verify as applicable:

- compilation/imports;
- pytest discovery;
- parameter exposure and start validation;
- planned steps and runtime event identity;
- focused self-tests;
- Android APK build after Android source changes;
- deterministic tests for logic that does not require hardware.

Do not weaken, skip, or delete tests to manufacture a pass.

### 6. Main-Codex Acceptance

The main Codex must inspect the real diff, workspace status, tests, ownership, and evidence. It then runs the highest available acceptance level:

| Level | Acceptance |
|---|---|
| L1 | Compile, import, static contract checks |
| L2 | Collection, parameter, step-plan, and automated framework tests |
| L3 | Real execution on the connected PC and DUT |
| L4 | Real execution with required external equipment |

Never claim full environment acceptance when required hardware is unavailable. Report the highest completed level and the smallest remaining user action.

### 7. Rework and Stop Conditions

The main Codex sends failed criteria and concrete evidence back to the same worker thread until acceptance passes. Ask the user only for major behavior ambiguity, scope expansion, destructive operations, missing hardware/credentials/permissions/resources, two failed fixes for one root cause, three total unsuccessful rounds, or evidence the main Codex cannot judge.

Final state must be `PASS`, `BLOCKED`, or `FAILED`.

## Batch Deliverables

For each development batch provide:

1. normalized case list and source references;
2. prerequisite/pre-action inventory;
3. parameter classification;
4. steps and checkpoints;
5. capability and equipment-gap matrix;
6. reusable extension design;
7. changed files and exact tests;
8. main-Codex environment acceptance level;
9. final state and remaining user action.

Keep one batch to one shared mechanism and normally 3-5 cases. Store the approved batch contract locally so main and worker exchange a path instead of duplicating raw source content in model prompts.

## Red Flags

Stop and correct the workflow if any of these occurs:

- implementation starts before source extraction and capability mapping;
- missing requirements are replaced by invented behavior;
- a single case gains a private framework or conversion helper;
- an action is called a checkpoint without a measurable pass rule;
- worker prose is accepted without diff and test inspection;
- hardware-dependent behavior is called verified without running that hardware;
- source identity is lost between the spreadsheet, pytest nodeid, steps, logs, or report.
