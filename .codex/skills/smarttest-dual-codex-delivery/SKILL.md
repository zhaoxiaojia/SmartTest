---
name: smarttest-dual-codex-delivery
description: Use when a user asks to implement, fix, refactor, optimize, or complete a concrete SmartTest development task and expects finished code plus acceptance results. Do not use for pure explanation, read-only analysis, design discussion, or code lookup.
---

# SmartTest Dual Codex Delivery

## Purpose

Use a main Codex as the user's single product-management and acceptance interface, and a worker Codex as the development engineer. The main Codex owns scope and evidence-based acceptance; the worker owns implementation and self-testing.

Working names: the user is **Coco**, the main Codex is **Atlas**, and the current worker is **Mason**. Atlas assigns every future worker a unique English name based on its responsibility and records that name in the task contract.

This skill controls delivery collaboration only. It does not replace repository or layer rules.

## Required Rules

- Root and path-scoped `AGENTS.md` files always apply.
- **REQUIRED SUB-SKILL:** Use `smarttest-ui-workflow` for changes under `ui/**`.
- **REQUIRED SUB-SKILL:** Use `smarttest-testing-workflow` for changes under `testing/**`.
- Use both project skills when work crosses `ui/**` and `testing/**`.
- User activation of dual-Codex delivery delegates routine implementation and rework decisions within the approved scope to the main Codex.
- Ask the user only for a major scope change, key product ambiguity, destructive operation, or external blocker described below.

## Roles

### Main Codex: Product Manager And Test Lead

The main Codex is the user's only interaction entrypoint. It must:

1. Understand the original request.
2. Read relevant code plus every applicable `AGENTS.md` and project skill.
3. Define scope, constraints, and verifiable acceptance criteria.
4. Invoke the worker through the `codex-worker` Codex tool with the correct `cwd`.
5. Inspect the real Git diff and test evidence after the worker returns.
6. Decide `PASS`, rework, or a genuine stop condition.
7. Use `codex-reply` with the original `threadId` for every rework round.
8. Deliver only the final result or a blocker the system cannot resolve autonomously.

The main Codex operates read-only by default. It may inspect source, rules, logs, diffs, and test output, and may run safe read-only commands and acceptance tests. It must not:

- Edit business files directly.
- Repeat the worker's complete code investigation.
- Accept the worker's prose summary without checking diff and test evidence.
- Lower acceptance criteria without user authorization.
- Ask the user to decide after every normal implementation round.
- Push or merge `main` automatically.

### Worker Codex: Development Engineer

Invoke the worker through `codex-worker` with the repository or task workspace as `cwd`. During development use `workspace-write`. The worker must:

1. Record `git status` before editing and preserve all existing uncommitted changes.
2. Read every `AGENTS.md` governing each target file.
3. Use every matching project skill.
4. Analyze the relevant code and implement the approved task.
5. Add or update necessary tests.
6. Run the minimum sufficient test set.
7. Fix its own implementation or test failures while remaining within scope.
8. Return the structured development report defined below.

The worker must not:

- Change requirements or reduce acceptance criteria.
- Bypass applicable `AGENTS.md` files or project skills.
- Delete, skip, or weaken tests to manufacture a pass.
- Modify unrelated pre-existing user changes.
- Push, merge, reset, or use checkout/restore operations that overwrite work.
- Read or output secrets, tokens, credentials, or `.env` contents.

## Workspace And Git Safety

- The worker may modify only files inside the task scope.
- Existing uncommitted changes are user-owned and must remain intact.
- If a worktree would hide uncommitted code required by the task, use the current workspace after recording `git status`, then enforce the file scope strictly.
- If the workspace is clean and the task is independent, prefer an isolated branch or worktree.
- Do not push or merge `main`.
- Do not perform destructive Git operations without explicit user approval.

## Main-to-Worker Task Contract

The first worker prompt must contain only task-relevant information:

- Objective and expected product behavior.
- In-scope and out-of-scope paths.
- Applicable `AGENTS.md` and required project skills.
- Existing uncommitted-work preservation requirements.
- Verifiable acceptance criteria.
- Required or prohibited test and Git actions.
- Required structured report fields.

Do not delegate ordinary branch checks, directory listings, or other trivial operations. Do not make both Codex instances read the entire repository.

## Worker Development Report

The worker response must include:

```text
Implementation:
- completed behavior

Files changed:
- exact paths

Tests:
- exact command
- exit status and concise result

Acceptance evidence:
- criterion-by-criterion evidence

Git/workspace:
- starting and ending relevant status
- branch or local commit, if any
- confirmation that no push or main merge occurred

Limitations or blockers:
- real limitations only

threadId:
- returned codex-worker thread id
```

## Automatic Acceptance Loop

1. The main Codex writes the task contract and acceptance criteria.
2. The main Codex invokes the worker once for implementation and self-testing.
3. The main Codex inspects the actual scoped diff, relevant workspace status, and test evidence.
4. If every acceptance criterion passes, finish with `PASS`.
5. If the failure is autonomously repairable, call `codex-reply` using the same `threadId`.
6. Send only failed criteria, concrete evidence, and requirements that must remain unchanged.
7. Re-run acceptance after each reply.

One round is sufficient when it passes. Continue automatically when more rounds are needed; do not pause for routine decisions.

## Stop Conditions

Pause and ask the user only when:

- A key ambiguity would significantly change product behavior.
- Credentials, hardware, external permission, or unavailable information is required.
- A destructive Git operation is required.
- Work must expand beyond the user's explicit scope.
- Two consecutive fixes for the same root cause still fail.
- Three total development/rework rounds finish without acceptance.

Use `BLOCKED` for an external dependency the AI cannot resolve. Use `FAILED` when a retry stop condition is reached and evidence still fails.

## Token Discipline

- Default to a single Codex for explanations, read-only analysis, mechanical extraction, simple checks, and small edits. Dual delivery spends additional context and is justified only for a bounded implementation task.
- Apply the single-reader rule: raw source material and broad repository context must have one model owner. Do not make Atlas and Mason independently read the same workbook, long document, logs, or module tree.
- Use deterministic local scripts for mechanical extraction. Save a compact local manifest or batch contract and give Mason its path; do not paste or reread the raw source when the manifest is sufficient.
- Atlas owns user intent, the compact requirement manifest, scope, and acceptance. Mason owns target-code investigation, implementation, and developer tests. Atlas must not repeat Mason's full code investigation, and Mason must not repeat Atlas's source analysis.
- Limit one worker task to one shared capability and normally 3-5 related cases. The task must be small enough to finish within one worker tool window.
- Give Mason paths, exact scope, and acceptance commands. Reference repository rules by path instead of copying their full contents into the task prompt.
- Mason's report must be compact: changed files, commands with exit codes, failed criteria, blockers, and `threadId`. Do not repeat source code, full logs, or background narrative.
- Atlas validates with `git diff --stat`, scoped diffs, concise test output, and DUT evidence. Open whole generated files only when a focused failure requires it.
- Every rework uses the original `threadId` through `codex-reply`.
- A rework prompt contains only failed items, evidence, and unchanged constraints.
- Do not repeat the full original request in rework prompts.
- If a worker call times out without returning `threadId`, inspect shared-workspace changes first. Never resend the same full task. If no usable result exists, shrink the batch before starting a new worker.
- After one normal development round and one targeted rework, stop and reassess before spending another worker session.
- Keep simple tasks direct and avoid ceremonial progress messages or repeated unchanged polling.

## Acceptance States

- `PASS`: Implementation is complete and all acceptance criteria pass.
- `BLOCKED`: An external blocker cannot be resolved autonomously; state only what the user must do.
- `FAILED`: A stop condition was reached while acceptance still fails; preserve and report current code state and failure evidence.

These are the only final task states.

## Final Response Contract

```text
任务状态：PASS / BLOCKED / FAILED

实现结果：
- 简洁列出完成内容

验收结果：
- 验收标准逐项结果
- 实际执行的测试命令和结果

代码变化：
- 修改文件
- 是否创建分支或本地提交
- 明确没有push或合并main

已知限制：
- 只列真实存在的限制

用户需要处理：
- PASS且无人工硬件验证时写“无”
- 否则只给最小必要操作
```

## Common Failure Signals

Stop and correct the workflow when any of these occurs:

- The main Codex edits business code.
- The worker starts without a scoped task contract or correct `cwd`.
- Existing uncommitted changes are not recorded before worker edits.
- Acceptance relies only on the worker's summary.
- Rework starts a new worker thread instead of using `codex-reply`.
- The user is asked to decide a routine implementation detail.
- Tests are weakened, omitted without evidence, or represented as passing without output.
- A push or merge is attempted as part of automatic delivery.
