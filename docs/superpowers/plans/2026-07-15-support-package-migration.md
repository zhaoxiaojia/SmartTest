# Support Package Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the global `tools` package to `support` without changing runtime, test, Android, or packaging behavior.

**Architecture:** Perform one mechanical package move, then update every Python import and repository-owned path consumer. Keep existing module ownership and APIs unchanged so later Jira and browser work starts from a stable package root.

**Tech Stack:** Python 3, pytest, PySide6/QML, PyInstaller/Inno Setup, PowerShell, Android Gradle entry scripts.

## Global Constraints

- Existing user changes are preserved and unrelated files are not modified.
- No compatibility `tools` package or forwarding imports remain.
- No desktop or Android package rebuild is required for this source migration.
- The commit contains only the `tools` to `support` migration.

---

### Task 1: Move the package and update Python imports

**Files:**
- Move: `tools/**` to `support/**`
- Modify: all tracked `.py` files importing `tools.logging`, `tools.report`, or `tools.param_conversion`
- Test: existing import, logging, report, Jira, UI, runner, and parameter tests

**Interfaces:**
- Consumes: existing `tools.logging`, `tools.report`, and `tools.param_conversion` APIs.
- Produces: identical APIs at `support.logging`, `support.report`, and `support.param_conversion`.

- [ ] **Step 1: Record the baseline and failing import contract**

Add or update an import-boundary test so it imports `support.logging`, `support.report`, and `support.param_conversion`, and asserts `importlib.util.find_spec("tools") is None` after migration.

- [ ] **Step 2: Verify the new contract fails before the move**

Run: `\.\.venv\Scripts\python.exe -m pytest testing\self_tests\tools -q`

Expected: failure because the `support` package does not exist yet.

- [ ] **Step 3: Move the directory and replace owned imports**

Move the complete tracked `tools/` tree to `support/`. Replace imports exactly as follows throughout owned Python source:

```python
from tools.logging import ...          # before
from support.logging import ...        # after

from tools.report import ...           # before
from support.report import ...         # after

from tools.param_conversion import ... # before
from support.param_conversion import ... # after
```

Do not rename `testing/tool`, MCP protocol strings such as `tools/list`, external Android SDK paths, or prose referring to generic tools.

- [ ] **Step 4: Verify imports and focused behavior**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest testing\self_tests\tools -q
.\.venv\Scripts\python.exe -m compileall support AI android_client jira_tool testing ui\example\bridge
```

Expected: all selected tests pass and compileall exits `0`.

### Task 2: Update repository-owned build and documentation paths

**Files:**
- Modify: `support/scripts/**`
- Modify: `support/packaging/pyinstaller/main.spec`
- Modify: `support/packaging/innosetup/SmartTest.iss`
- Modify: runtime-relevant README, signing, and build documentation containing `tools/` paths
- Test: packaging manifest/path-focused tests

**Interfaces:**
- Consumes: scripts formerly invoked through `tools/scripts/...`.
- Produces: equivalent commands at `support/scripts/...` and packaged data destination `support`.

- [ ] **Step 1: Add path assertions**

Update existing packaging tests to require `support/scripts`, `support/packaging`, and packaged destination `support`, while rejecting tracked runtime references to the removed root `tools/`.

- [ ] **Step 2: Verify assertions fail**

Run the affected packaging/build-manifest tests discovered under `testing/self_tests`.

Expected: failures point only to old `tools/` paths.

- [ ] **Step 3: Replace repository-owned paths**

Update Python, PowerShell, spec, installer, and documentation paths from `tools/...` to `support/...`. Preserve command arguments, artifact names, version behavior, and install destinations other than the renamed package directory.

- [ ] **Step 4: Run migration acceptance**

Run:

```powershell
rg -n "from tools\.|import tools\.|tools[\\/]scripts|tools[\\/]packaging" --glob "!docs/superpowers/**" .
.\.venv\Scripts\python.exe -m pytest testing\self_tests\tools testing\self_tests\ui\test_tool_page.py -q
git diff --check
```

Expected: `rg` returns no owned stale package/build references; tests pass; diff check exits `0`.

- [ ] **Step 5: Commit the migration**

```powershell
git add support AI android_client jira_tool testing ui main.py README.md
git commit -m "refactor: rename shared support package"
```

