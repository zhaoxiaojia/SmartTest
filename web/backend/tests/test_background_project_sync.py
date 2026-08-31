from smarttest_web.background_refresh import BackgroundFactsRefresh


def test_scoped_detail_job_is_single_flight_reports_revision_and_can_cancel():
    submitted = []
    refresh = BackgroundFactsRefresh(submit=submitted.append)

    class Owner:
        def sync_details(self, username, password, *, filters, search, cancelled=None, progress=None):
            progress(1, 2)
            assert not cancelled()
            return {"revision": 7}

    assert refresh.start_details(Owner(), "coco", "secret", filters={"stage": ["3"]}, search="")
    assert not refresh.start_details(Owner(), "coco", "secret", filters={}, search="")
    assert refresh.status_for("coco") == {"state": "loading", "completed": 0, "total": 0, "revision": 0}
    submitted.pop()()
    assert refresh.status_for("coco") == {"state": "ready", "completed": 1, "total": 2, "revision": 7}

    assert refresh.start_details(Owner(), "coco", "secret", filters={}, search="")
    assert refresh.cancel("coco")
    assert refresh.status_for("coco")["state"] == "cancelled"
