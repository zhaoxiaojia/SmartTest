# Task 1 Report — Mason

## Status

DONE

## Reuse decision

Extended the existing `config/personnel.json` department owner and `ToolBridge.amlogic_employees`; no parallel identity registry or legacy department fallback was introduced.

## Files changed

- `config/personnel.json`
- `ui/example/bridge/ToolBridge.py`
- `testing/self_tests/ui/test_tool_page.py`
- `testing/self_tests/ui/test_auth_bridge_profile.py`

## RED evidence

- Command: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/ui/test_tool_page.py -q -k "three_explicit_fae_departments"`
- Exit code: 1
- Result: expected failure because `employee_department` did not exist.

## GREEN evidence

- Command: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/ui/test_tool_page.py -q -k "three_explicit_fae_departments"`
- Exit code: 0
- Result: 1 passed, 23 deselected.
- Command: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/ui/test_tool_page.py testing/self_tests/ui/test_auth_bridge_profile.py -q`
- Exit code: 0
- Result: 40 passed; 2 existing ldap3/pyasn1 deprecation warnings.
- Command: `.\.venv\Scripts\python.exe -m py_compile ui/example/bridge/ToolBridge.py testing/self_tests/ui/test_tool_page.py testing/self_tests/ui/test_auth_bridge_profile.py`
- Exit code: 0.
- Command: `git diff --cached --check`
- Exit code: 0.

## Self-review

- Department identity is derived only from configured department node names.
- `fred.chen` is unique, resolves to `FAE-SW`, has M5 grade metadata, and owns primary SmartHome assignment.
- Existing employee assignments and access behavior are preserved; unknown accounts remain common-only.
- No clone UI/API behavior was added.
- No legacy `FAE` fallback or duplicate department mapping was added.
- Scoped commit contains only the four approved files.

## Concerns

- None affecting implementation or acceptance.
- The requested `superpowers:test-driven-development` skill file was absent from the current installed plugin cache; the exact brief RED/GREEN workflow was followed directly.
- Test output includes two pre-existing dependency deprecation warnings.

## Commit

- `00b0cf2 feat: define SmartHome FAE software ownership`

## Relevant workspace status

- Task changes committed on `main`.
- `.superpowers/` remains untracked/ignored task ledger/report content and was not committed.

## Rework — canonical SmartHome owner

- RED command: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/ui/test_tool_page.py -q -k "three_explicit_fae_departments"`
- RED result: exit 1; SmartHome `owner_account` was `chen.chen` instead of `fred.chen`.
- Existing account semantics inspected: `ToolBridge.build_tool_groups` and `AuthBridge.match_employee_profile` use trimmed exact account matching; the existing auth test explicitly rejects `CHAO.LI`. `employee_department` therefore remains case-sensitive, with `FRED.CHEN -> ""` covered.
- Canonical product-owner test was strengthened to expect Fred while preserving STB, TV, IPTV, and Wi-Fi owners.
- Focused command: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/ui/test_tool_page.py -q -k "personnel_declares_product_line_and_technical_center_owners or three_explicit_fae_departments"`
- Focused result: exit 0; 2 passed, 22 deselected.
- Full Task 1 command: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/ui/test_tool_page.py testing/self_tests/ui/test_auth_bridge_profile.py -q`
- Full Task 1 result: exit 0; 40 passed, 2 existing ldap3/pyasn1 deprecation warnings.
- `py_compile`: exit 0.
- `git diff --check`: exit 0.
- Rework commit: `f268e1c fix: assign SmartHome ownership to Fred Chen`.
- Rework concerns: none.
