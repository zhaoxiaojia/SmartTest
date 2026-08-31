---
name: smarttest-logging-workflow
description: Use when changing SmartTest logger, print, Logcat, FastAPI access logs, log fields, formatting, storage, or platform logging adapters.
---

# SmartTest Logging Workflow

## Owner and protocol

- Reuse `core.logging`; it is the only Python record, formatter, JSONL, readable-file, event, color, and output owner.
- Keep the fields `timestamp`, `platform`, `level`, `domain`, `source`, `message`, `request_id`, `case_nodeid`, `step_id`, and `extra`.
- Keep readable output as `<timestamp> [<platform>] [<domain>] [<LEVEL>] [<source>] <message>`.
- Use only `client`, `tool`, `web`, `runner`, or `mobile` for `platform`. Keep unavailable identity fields empty.

## Platform boundaries

- Python product code imports `core.logging`; do not create a private logger, formatter, file handler, transport, or compatibility shim.
- FastAPI emits one request record through `core.logging.smart_log`, with method, path, status, and duration. Do not log bodies, credentials, tokens, cookies, or database statements. Keep Uvicorn access logging disabled.
- Android business code uses `mobile/android/app/src/main/java/com/smarttest/mobile/logging/SmartTestLog.kt`. Only that thin adapter may call `android.util.Log`; it must not add a second model, level system, or file format.
- FluentUI may retain only the thin interface required by the third-party UI library.
- Product runtime uses public logging instead of temporary `print`. Build/CI command output and external firmware-log parsing remain stdout-oriented and are not product log owners.

## Verification

1. Run focused Python logging and affected runtime/UI tests.
2. For Web changes, assert one request record, safe fields, Uvicorn access-log suppression, and the backend suite.
3. For Android changes, search production Kotlin for direct `Log` outside `SmartTestLog`, run unit/static tests, build debug APK, and follow the Android workflow for signing when available.
4. Run `core/devtools/ci/test_check_product_boundaries.py`, `core/devtools/ci/check_product_boundaries.py`, a repository search for retired/private owners, and `git diff --check`.
