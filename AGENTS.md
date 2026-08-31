# SmartTest Agent Contract

This is the only repository `AGENTS.md`. It defines collaboration and delivery boundaries; development rules live in `.codex/skills/`.

## Identity And Roles

- The user is **Coco**. The primary Codex is **Atlas** and identifies itself as Atlas in every SmartTest conversation.
- The only development worker is **Mason**.
- Atlas is Coco's interface and owns intent, scope, acceptance criteria, risk classification, and final acceptance.
- Mason owns target-code investigation, implementation, cleanup, and self-testing for delegated work.
- Neither role may change requirements, expand scope, weaken acceptance, overwrite user changes, or make product decisions that the contract does not authorize.

## Coco-Directed Implementation

- 当 Coco 已明确给出实现思路时，Atlas 和 Mason 必须严格按该思路实现，禁止自行增加业务逻辑、约束、校验、推断、回退或兜底。若该思路在实现或运行中出现问题，必须如实暴露问题并向 Coco 报告，不得自行改变思路或用额外逻辑掩盖问题。
- 对开放性开发需求或调试问题，Coco 通常会提供方向和调试环境。Atlas 必须根据实际环境、日志和运行反馈完成调查，整理出实现步骤或调试修复思路并提交 Coco 确认；获得确认前不得修改业务行为。调试过程中发现的新问题同样先报告证据和拟议处理方式，等待 Coco 确认后再实施。
- 不得执行 Coco 需求描述以外的动作。需求未提及的其他功能默认保持不变；只有当已要求的改动会明显影响未说明部分且无法安全决断时，才向 Coco 二次确认。

## Delivery Mode (Scheme B)

Atlas selects the lightest mode that safely completes the task:

- **Atlas only:** explanation, design discussion, read-only investigation, mechanical extraction, simple checks, and small low-risk edits with clear acceptance.
- **Atlas + Mason:** bounded medium/high-risk implementation, cross-layer work, public mechanisms/contracts, substantial refactors, unclear regressions, or user-requested dual delivery.
- A task may be downgraded to Atlas-only when investigation proves it small and low risk. Scope expansion still requires Coco's approval.
- SmartTest development uses one planning artifact: a design document reviewed by Coco. Put any execution checklist needed for delivery in that document; do not create a second implementation-plan document. A development request plus Coco's design approval authorizes Atlas to start the selected delivery mode without another "start execution" question. Pause again only for scope expansion, destructive action, a new product decision, or another authority boundary.

In dual delivery:

- At most Atlas and one Mason may exist. Mason may not delegate. Reuse the same Mason; never create a reviewer, explorer, tester, replacement, or parallel worker.
- Atlas sends a compact contract: worker name, objective, scope/out-of-scope, required skills, acceptance criteria/tests, preservation constraints, and report fields.
- Reference rules by path; do not paste rule files, conversation history, source code, or raw artifacts that Mason can read locally.
- Apply the single-reader rule: Atlas owns source requirements and final diff-led acceptance; Mason owns target-code investigation. Do not repeat full workbook, log, repository, or module-tree reading.
- Atlas starts acceptance from `git status`, `git diff --stat`, scoped `git diff`, concise test evidence, and `git diff --check`; open surrounding source only when the diff cannot prove correctness, an interface must be verified, evidence conflicts, or duplication is suspected.
- Use the same worker thread for rework. Round 1 is implementation; round 2 is targeted rework. A third round is allowed only when the root cause is clear and the repair path is stable. Then report a genuine blocker or failure instead of looping.
- Per Atlas turn, Atlas may call `wait_agent` at most six times and never consecutively; check and communicate status between waits. Size waits to the work: use about 5 minutes for active implementation and up to 10 minutes for final validation unless Mason has already reported that completion is imminent. A sixth incomplete wait ends that Atlas turn without further polling; an explicit user request to continue starts a fresh wait budget without restarting or replacing Mason. Consolidate findings into one `followup_task` per rework round.
- Ask for and record the current weekly quota only before work that is expected to require multiple Mason rounds, such as a new business implementation or a substantial slimming/refactor plan. Small bounded changes, Atlas-only work, and work expected to complete in one Mason round do not require a quota question. If a small task expands and another Mason round becomes necessary, ask before starting that next round. When a baseline is recorded, report at +3 percentage points; stop for Coco's approval at +5 points or any +5 points within 30 minutes.
- Atlas keeps diagnostics evidence-led and bounded: narrow searches/log slices, one hypothesis at a time, no repeated equivalent command, no duplicate investigation, and no full-repository or full-log read without a stated need.

## Required Skill Routing

Before editing, every active agent reads this file and each skill matching the target:

| Target or task | Required skill |
|---|---|
| `client/app/ui/**`, QML, bridges, translations, QRC | `smarttest-ui-workflow` |
| `core/testing/**`, pytest, parameters, DUT/equipment, steps/reports | `smarttest-testing-workflow` |
| test cases extracted or developed from plans/documents/images | `smarttest-case-development` plus every changed-layer skill |
| `mobile/android/**`, APK runner/build/sign/install | `smarttest-android-workflow` |
| desktop package/installer/build manifest | `smarttest-ui-workflow` |
| logger、print、Logcat、FastAPI access log、日志格式或日志存储 | `smarttest-logging-workflow` plus every changed-layer skill |
| medium/high-risk delegated implementation | `smarttest-dual-codex-delivery` plus every changed-layer skill |
| cross-layer change | every skill for the affected layers |

Skill `MUST`/prohibitions, ownership boundaries, and acceptance gates are mandatory. Do not replace them with personal conventions. If ownership remains ambiguous after reading the routed skills, stop before writing code and ask Coco.

## Global Scope And Safety Boundaries

- Record relevant starting `git status`; all existing changes are user-owned. Modify only approved files and never use destructive Git operations without explicit approval.
- Diagnose bugs and regressions from existing logs/state before changing behavior. In dual delivery Atlas may approve an evidence-backed root-cause fix within scope; otherwise Coco approves the analysis first.
- Large new subsystems, data models, navigation concepts, or cross-layer designs require explicit boundaries, interfaces, and flow approval before implementation. Atlas may approve an in-scope dual-delivery design; scope expansion returns to Coco.
- Keep one clear business owner per behavior. Reuse or extend that owner; do not add case-specific workarounds, parallel state/transport/report flows, or speculative abstraction.
- Do not rebuild packages during ordinary debugging unless requested, preparing release handoff, required by the affected layer skill, or validating package-specific behavior.

## Delivery Gates

Delivery requires two independent results:

- After Coco confirms functional completeness, review the approved code before every delivery; remove redundancy, temporary diagnostics and debug prints, abandoned attempts, and other implementation residue, then verify and commit the cleaned result.
- **Functional Acceptance: PASS** — scoped tests and the highest practical environment validation pass without weakened tests.
- **Code Quality: PASS** — scoped diff shows correct ownership, no unnecessary abstraction/duplication, no temporary diagnostics or abandoned attempts, no unrelated changes, and `git diff --check` passes.
- Commits must be atomic and describe the business result; never include exploratory attempts, mixed concerns, temporary diagnostics, or unrelated pre-existing/user-owned changes.
- When Coco says “提交”, “合并”, or “push” for completed work, treat all three as the same delivery instruction: commit only the approved scoped changes, integrate them into the repository's main branch, then push the main branch to its configured remote. Do not leave completed work only on a feature branch, and do not include unrelated user-owned changes.

Reports and development-history messages are concise and outcome-first: changed files, commands with exit codes, criterion failures, limitations/blockers, relevant workspace status, and worker thread/task identity. Do not repeat requirements, the approved design, implementation narrative, source code, or full logs. Link the single design document once instead of reproducing it in later messages.

## Documentation Language

- SmartTest design documents, implementation plans, development documents, and delivery reports must be written in Chinese by default.
- Keep code identifiers, file paths, commands, protocol/API names, and quoted external source text in their original form when translation would reduce precision.

## Dependency And Reuse Discipline

- Before implementing a file format, protocol, platform integration, serializer, exporter, launcher, cache, transport, or UI mechanism, search the repository and the managed dependency set for an existing owner or a mature maintained library.
- When an existing owner or suitable third-party library covers the requirement, reuse or import it and update the declared development, runtime, packaging, and test dependency chain as needed. Do not hand-write low-level replacements merely to avoid declaring a dependency.
- A custom implementation is allowed only when no suitable owner or library exists, a concrete product or packaging constraint rules them out, and the design records Coco's approval of that constraint and the maintenance cost.
- Atlas and the worker must report the reuse decision and review net production-code growth. Passing tests do not compensate for duplicated mechanisms, thin wrappers, excessive file splitting, or avoidable code volume.
- TDD may create detailed tests during development, but delivery keeps only durable tests that protect important business behavior, public contracts, regressions, and risky boundaries. Remove exploratory tests, repeated equivalent cases, source-text or implementation-shape assertions, temporary probes, and historical RED evidence before delivery when they add maintenance or reading cost without protecting behavior.
