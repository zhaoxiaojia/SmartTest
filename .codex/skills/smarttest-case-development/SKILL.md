---
name: smarttest-case-development
description: Use when extracting SmartTest cases from Excel, Word, images, or plans; assessing automation/equipment gaps; designing shared capability extensions; or implementing pytest and Android-backed cases with traceable acceptance.
---

# SmartTest Case Development

## Core Rule

Turn source material into traceable executable requirements before implementation. Reuse SmartTest parameter, DUT, equipment, step, log, run, report, and Android owners; never invent missing product behavior, parallel flows, or case-specific framework workarounds.

Also load `smarttest-testing-workflow`, plus `smarttest-ui-workflow` and/or `smarttest-android-workflow` when those layers change. Use `smarttest-dual-codex-delivery` only when Scheme B classifies the implementation medium/high risk.

## 1. Requirement Cards

Use deterministic extractors for structured sources and save a compact manifest. One model reads the raw source; downstream work consumes the approved manifest unless a cited cell is ambiguous.

For each case record:

- source file/sheet/range, original id, title, module, priority, milestone;
- prerequisites, environment, DUT/PC, accounts/resources, and equipment;
- parameter key/type/default/scope/options/UI exposure/`required_at_start`/units/limits;
- executable pre-actions separated from prerequisite states;
- ordered step id/action/inputs/expected transition/timeout/loop/failure policy;
- checkpoint definition id/object/method/expected/tolerance/evidence/pass/skip/equipment dependency;
- ambiguities or missing thresholds/resources/equipment.

Preserve source identity through nodeid, steps, logs, reports, and acceptance. Stop an affected case when behavior cannot be inferred safely.

## 2. Capability Map

Map every action/checkpoint to a concrete callable owner, not a filename:

| Classification | Required action |
|---|---|
| supported | reuse owner |
| partially supported | extend owner generically |
| software extension | design reusable PC/DUT capability |
| external equipment | specify device and connection contract |
| manual | preserve preparation/evidence requirement |
| insufficient information | stop case for clarification |
| currently impossible | report evidence and blocker |

Search parameter/runtime/step/tool/DUT/equipment owners, Android catalog/runner, and report contracts before design.

## 3. Extension Decision

Choose in order: reuse; extend current owner; consolidate duplicate behavior; add a generic DUT feature/step/equipment service/parameter contract/Android runner; add a module only when no owner fits.

Reject case-local ADB/serial/install/file/conversion helpers, duplicate UI/report steps, alternate parameter transport, and static handling for one case/value/file. For large or cross-layer work, define ownership, public interfaces, parameter/execution/result/log flow, and compatibility before editing.

## 4. Implementation Contract

Each case has an objective/checkpoints, runtime parameters, explicit pre-actions, declared shared lifecycle steps, and pass/fail/skip evidence.

```text
UI persisted state -> testing/params/runtime.py -> case/step/runner
```

Use `tools/param_conversion.py`, `smart_log(...)`, and stable step/result identities. `None` checkpoint selection means do not check and is omitted from APK requests. Layer skills own further implementation rules.

## 5. Evidence And Acceptance

The implementer records starting status, preserves user work, tests only approved scope, and reports commands/exit codes. Validate applicable imports/compilation, discovery, parameter exposure/start checks, step/event identities, focused self-tests, Android build/sign after APK source changes, and deterministic non-hardware logic.

Atlas uses diff-led acceptance and records the highest completed level:

| Level | Evidence |
|---|---|
| L1 | compile/import/static contracts |
| L2 | discovery/parameter/plan/framework tests |
| L3 | real PC + DUT execution |
| L4 | execution with required equipment |

Never claim unavailable hardware acceptance. Final state is `PASS`, `BLOCKED`, or `FAILED`, following the dual-delivery round policy when delegated.

## Batch Output

Keep a batch to one shared mechanism and normally 3–5 related cases. Provide the manifest path, prerequisite/pre-action inventory, parameter/step/checkpoint definitions, capability/equipment matrix, reusable extension decision, changed files/tests, acceptance level, state, and smallest remaining user action.

Stop and correct work if implementation precedes extraction/mapping, ambiguity becomes invented behavior, a case gains a private framework, a checkpoint lacks a measurable rule, worker prose replaces diff/test evidence, hardware is claimed without execution, or source identity is lost.
