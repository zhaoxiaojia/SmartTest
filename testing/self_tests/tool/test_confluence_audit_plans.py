from dataclasses import replace
from datetime import datetime
import json
from zoneinfo import ZoneInfo

import pytest

from tool.common.project_weekly_audit.models import ProjectCollectionFilter
from tool.common.project_weekly_audit.plans import AuditPlan, AuditPlanStore
from tool.common.project_weekly_audit.discovery import UNIFIED_SOURCE


TZ = ZoneInfo("Asia/Shanghai")


def _plan(plan_id="plan_b", name="Plan B"):
    created = datetime(2026, 7, 29, 9, tzinfo=TZ)
    return AuditPlan(
        plan_id, name,
        ProjectCollectionFilter(
            UNIFIED_SOURCE, (2025, 2026), ("A",), ("Active",),
            (), (),
        ),
        True, f"cred-{plan_id}", f"SmartTest Project Audit {plan_id}",
        created, created,
    )


def test_plan_store_round_trips_schema_and_never_serializes_credentials(tmp_path):
    store = AuditPlanStore(tmp_path)
    source = _plan()
    path = store.save(source)
    assert store.load(source.plan_id) == source
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    serialized = json.dumps(payload).casefold()
    assert "username" not in serialized
    assert "password" not in serialized
    assert payload["credential_ref"] == "cred-plan_b"


def test_plan_store_lists_by_plan_id_deterministically(tmp_path):
    store = AuditPlanStore(tmp_path)
    store.save(_plan("plan_b", "First alphabetically"))
    store.save(_plan("plan_a", "Last alphabetically"))
    assert [plan.plan_id for plan in store.list()] == ["plan_a", "plan_b"]


@pytest.mark.parametrize("plan_id", ("../bad", "bad/name", r"bad\name", "bad name", ""))
def test_plan_store_rejects_unsafe_ids(tmp_path, plan_id):
    store = AuditPlanStore(tmp_path)
    with pytest.raises(ValueError):
        store.save(_plan(plan_id))
    with pytest.raises(ValueError):
        store.load(plan_id)


def test_plan_store_atomic_replace_failure_preserves_previous_file(tmp_path, monkeypatch):
    store = AuditPlanStore(tmp_path)
    original = _plan()
    store.save(original)

    def fail_replace(source, target):
        raise OSError("replace failed")

    monkeypatch.setattr("tool.common.project_weekly_audit.plans.Path.replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        store.save(replace(original, name="Changed"))
    assert store.load(original.plan_id) == original
    assert not list(tmp_path.glob("*.tmp"))


def test_plan_store_updates_result_without_changing_plan_definition(tmp_path):
    store = AuditPlanStore(tmp_path)
    source = _plan()
    store.save(source)
    run_at = datetime(2026, 8, 1, 0, 5, tzinfo=TZ)
    updated = store.update_result(
        source.plan_id, status="failed", report_path="reports/a.pdf", run_at=run_at,
    )
    assert updated == replace(
        source, last_run_at=run_at, last_status="failed",
        last_report_path="reports/a.pdf", updated_at=run_at,
    )
    assert store.load(source.plan_id) == updated


@pytest.mark.parametrize("schema_version", (None, 2, True))
def test_plan_store_rejects_missing_or_unsupported_schema(tmp_path, schema_version):
    store = AuditPlanStore(tmp_path)
    path = store.save(_plan())
    payload = json.loads(path.read_text(encoding="utf-8"))
    if schema_version is None:
        payload.pop("schema_version")
    else:
        payload["schema_version"] = schema_version
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="schema"):
        store.load("plan_b")


@pytest.mark.parametrize("payload_id", ("../illegal", "plan_a"))
def test_plan_store_rejects_illegal_or_mismatched_payload_plan_id(tmp_path, payload_id):
    store = AuditPlanStore(tmp_path)
    path = store.save(_plan())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["plan_id"] = payload_id
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="plan id"):
        store.load("plan_b")


def test_plan_store_rejects_numeric_payload_id_even_when_text_matches_filename(tmp_path):
    store = AuditPlanStore(tmp_path)
    path = store.save(_plan("123"))
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["plan_id"] = 123
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="plan id"):
        store.load("123")


def test_legacy_single_space_source_loads_as_unified_product_scope(tmp_path):
    store = AuditPlanStore(tmp_path)
    path = store.save(_plan())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["collection_filter"]["source_url"] = (
        "https://confluence.amlogic.com/display/DOPL/Project+Space"
    )
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = store.load("plan_b")

    assert loaded.collection_filter.source_url == UNIFIED_SOURCE
    assert loaded.collection_filter.current_stages == ()
