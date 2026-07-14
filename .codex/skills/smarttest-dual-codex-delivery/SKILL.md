---
name: smarttest-dual-codex-delivery
description: Use when a bounded SmartTest implementation is medium/high risk, crosses layers, changes shared contracts, performs substantial refactoring, investigates an unclear regression, or explicitly requires a development worker.
---

# SmartTest Dual Codex Delivery

## Core Contract

Coco is the user, Atlas is the primary Codex, and Mason is the current worker. Atlas owns requirements and diff-led acceptance; Mason owns target-code investigation, implementation, cleanup, and self-test. Assign every future worker a unique responsibility-based English name.

This skill applies Scheme B. Small low-risk edits stay with Atlas. Delegation buys independent implementation only when its quality value exceeds its context cost.

## Route The Task

Use Atlas only for read-only work, mechanical extraction, simple checks, and small edits with obvious ownership and focused validation. Use Mason for bounded medium/high-risk work, cross-layer changes, shared mechanisms, substantial refactors, unclear regressions, or explicit user requests.

Before work, load every matching owner skill:

- `ui/**`: `smarttest-ui-workflow`
- `testing/**`: `smarttest-testing-workflow`
- case extraction/development: `smarttest-case-development`
- `android_client/**`: `smarttest-android-workflow`

## Role Boundaries

Atlas:

1. Defines intent, scope, exclusions, acceptance, and risk.
2. Gives Mason a compact contract and correct workspace.
3. Reviews actual status, scoped diff, tests, and quality evidence.
4. Sends focused rework to the same worker thread.
5. Reports `PASS`, `BLOCKED`, or `FAILED`.

Mason:

1. Records starting `git status` and preserves all user changes.
2. Reads root `AGENTS.md` and routed skills.
3. Investigates the target owners, records `reuse / extend / consolidate / new owner`, and implements only approved scope.
4. Adds necessary tests, runs the minimum sufficient set, and cleans rejected attempts and temporary diagnostics.
5. Returns compact evidence; never pushes, merges, resets, weakens tests, or exposes secrets.

Apply the single-reader rule: Atlas owns source requirements and the acceptance view; Mason owns implementation context. Neither repeats the other's full workbook, logs, repository, or module-tree investigation.

## Compact Task Contract

```text
Worker:
Objective:
Scope / out of scope:
Required skills:
Acceptance criteria and tests:
Preserve:
Report fields:
```

Use paths instead of pasted rules/code/raw artifacts. One task owns one shared capability and normally 3–5 related cases. Deterministic extraction should produce a compact manifest that only one model reads from source.

## Acceptance And Rework

Atlas starts with:

1. relevant `git status` and `git diff --stat`;
2. scoped `git diff`;
3. concise commands, exit codes, and environment evidence;
4. `git diff --check`;
5. functional and code-quality verdicts.

Read surrounding source only when the diff cannot prove the flow, a changed interface needs verification, evidence conflicts, or duplication/ownership is uncertain. Reject unnecessary abstractions, parallel flows, case-specific mechanisms, temporary diagnostics, abandoned attempts, weakened tests, and unrelated changes.

Rounds are bounded:

- Round 1: implementation and worker self-test.
- Round 2: same-thread rework containing only failed criteria, evidence, and unchanged constraints.
- Round 3: allowed only when the root cause is clear and the repair path stable.

After three unsuccessful rounds, or two failed fixes for the same root cause, stop. Ask Coco only for product ambiguity, scope expansion, destructive action, or missing external access/hardware/information.

## Worker Report

```text
Files changed/deleted:
Tests (command, exit code, concise result):
Acceptance / quality:
Relevant git status:
Limitations or blockers:
thread/task identity:
```

Add a one-line reuse decision and list a new abstraction only when one was introduced. Do not restate the task, narrate implementation, paste code, or return full logs.

## Final States

- `PASS`: Functional Acceptance and Code Quality both pass.
- `BLOCKED`: an external dependency prevents completion; state the smallest user action.
- `FAILED`: the bounded retry policy ended without acceptance; preserve and report evidence.
