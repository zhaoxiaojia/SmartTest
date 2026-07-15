# Account Profile Layout Design

## Goal

Replace the account footer and signed-in account window with the approved card layout, including a compact navigation presentation, dynamic personnel data, local avatar upload, and reporting-line data.

## Personnel data

- `config/personnel.json` remains the single source of employee profile fields.
- Each employee stores both `display_name` (for example `Chao Li`) and `account` (for example `chao.li`). `account` is the SmartTest/LDAP identity; `display_name` is the human/Jira identity.
- Add a root employee field `reports_to` whose value is another employee's exact `display_name`; an empty string means no recorded manager.
- `Chen Chen` is the product-line lead. `Kang Jiang`, `Weiting Feng`, `Zhuhui Zhang`, `Taoqing Miao`, and `Nannan Meng` report directly to `Chen Chen`.
- Preserve the stated grades: Kang Jiang I3, Weiting Feng I3, Zhuhui Zhang I2, Taoqing Miao I2, and Nannan Meng I3.
- Every existing employee whose grade is M3 or M4 reports directly to `Xiuyue Zhang`.
- Employee names, grades, organization values, product-line names, roles, and reporting names are dynamic values and render verbatim. They never pass through Qt translation.
- Fixed UI labels such as Account, Grade, Department, Product Line, Reports To, Upload Avatar, and Logout remain owned bilingual UI text.

## Identity matching

- LDAP authentication fetches `displayName` with the avatar lookup when available.
- The authenticated username is matched exactly, after domain/email normalization, against `employees[].account`; no inferred name matching is used.
- The account surface may show both formats: `display_name` as the person name and `account` as the signed-in account.
- If no employee record matches, the account surface keeps the authenticated identity but does not invent personnel fields.

## Avatar ownership

- Clicking the avatar opens a local image picker.
- The bridge validates the selected local image and copies it under the repository project directory at `config/avatars/` using a filesystem-safe deterministic filename.
- The uploaded avatar overrides the LDAP avatar for the matching employee on later source runs.
- Server upload is out of scope.
- If no uploaded or LDAP avatar exists, show initials derived from whitespace-separated display-name words, uppercased. `Xiaojia Zhao` becomes `XZ`; a single-word name uses its first uppercase character.

## Presentation

- Open navigation shows the employee avatar, display name, and concise role text in the account footer.
- Clicking the account footer opens the approved A-style account card with avatar, display name, authentication state, grade/title, department/team, product lines, manager, avatar upload, and logout.
- Compact navigation remains 50 px wide. Its account footer is taller than a standard navigation row, shows a 32 px avatar above the elided display name, and displays no other employee fields.
- The account-specific footer customization must not change ordinary navigation item sizing or introduce a second profile-data flow.

## Validation

- Unit-test reporting relationships, profile lookup, initials, avatar-path validation/copying, and uploaded-avatar precedence.
- Run focused QML/translation ownership tests and rebuild `resource_rc.py` when QRC-backed QML changes.
- Perform a bounded source startup check from the repository root.
- Do not rebuild the desktop package.
