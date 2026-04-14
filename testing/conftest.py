from __future__ import annotations

import json
import os
from pathlib import Path


def _infer_case_type(item) -> str:
    case_type_marker = item.get_closest_marker("case_type")
    if case_type_marker and case_type_marker.args:
        value = str(case_type_marker.args[0]).strip()
        if value:
            return value

    # Fallback: allow simple marker names as types, e.g. @pytest.mark.stress
    marker_names = {m.name for m in item.iter_markers()}
    for candidate in ("stress", "performance", "regression", "smoke"):
        if candidate in marker_names:
            return candidate

    return "default"


def pytest_collection_modifyitems(session, config, items):
    session._smarttest_collected_items = items  # noqa: SLF001


def pytest_sessionfinish(session, exitstatus):
    """
    Export collected test items (nodeid + markers + case_type) for the SmartTest UI.

    This is enabled only when SMARTTEST_PYTEST_COLLECT_OUT is set.
    """
    out_path = os.environ.get("SMARTTEST_PYTEST_COLLECT_OUT")
    if not out_path:
        return

    items = getattr(session, "_smarttest_collected_items", [])
    payload = []
    for item in items:
        markers = sorted({m.name for m in item.iter_markers()})
        nodeid = item.nodeid
        file_part = nodeid.split("::", 1)[0]
        name = nodeid.split("::")[-1] if "::" in nodeid else nodeid
        payload.append(
            {
                "nodeid": nodeid,
                "file": file_part,
                "name": name,
                "markers": markers,
                "case_type": _infer_case_type(item),
            }
        )

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

