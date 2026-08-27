from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.confluence.client import ConfluenceClient
from core.confluence.models import ConfluenceClientConfig


class FakeConfluence:
    def __init__(self):
        self.calls = []

    def cql(self, cql, start=0, limit=100, expand=None):
        self.calls.append((cql, start, limit, expand))
        rows = [
            {
                "content": {
                    "id": str(index),
                    "title": f"Page {index}",
                    "_links": {"webui": f"/pages/{index}"},
                    "version": {"number": 2, "when": "2026-07-28T01:02:03.000Z"},
                    "body": {
                        "storage": {"value": f"<ac:structured-macro>{index}</ac:structured-macro>"},
                        "view": {"value": f'<p><a href="/rendered/{index}">{index}</a></p>'},
                    },
                }
            }
            for index in range(start, min(start + limit, 3))
        ]
        return {"results": rows, "totalSize": 3}

    def get_page_by_id(self, page_id, expand=None):
        assert expand == "body.storage,body.view,version"
        if expand == "version":
            return {"id": page_id, "version": {"number": 3}}
        return {
            "id": page_id, "title": "Status Report",
            "body": {
                "storage": {"value": "<ac:task><ac:task-status>complete</ac:task-status></ac:task>"},
                "view": {"value": '<p><a href="/jira/BUG-1">weekly</a></p>'},
            },
            "version": {"number": 3, "when": "2026-07-28T01:02:03.000Z"},
            "_links": {"webui": "/display/ABC/status"},
        }

    def get_page_id(self, space, title):
        assert (space, title) == ("M314", "Muffin314 Project Home")
        return "home-1"

    def get_page_ancestors(self, page_id):
        assert page_id == "671973853"
        return [
            {"id": "root", "title": "Space root"},
            {"id": "671973851", "title": "Muffin314 Project Home"},
        ]

    def get_page_child_by_type(self, page_id, type="page", start=0, limit=100, expand=None):
        assert expand == "version"
        return {"results": [{"id": "c1", "title": "Test Plan", "_links": {"webui": "/c1"}}],
                "size": 1}

def test_search_pages_paginates_and_normalizes():
    api = FakeConfluence()
    client = ConfluenceClient(ConfluenceClientConfig("https://confluence.example"), "u", "secret", api=api)
    pages = client.search_pages("label=pm-summary", limit=2)
    assert [page.id for page in pages] == ["0", "1", "2"]
    assert pages[0].body == "<ac:structured-macro>0</ac:structured-macro>"
    assert pages[0].view_body == '<p><a href="/rendered/0">0</a></p>'
    assert pages[0].url == "https://confluence.example/pages/0"
    assert [call[1] for call in api.calls] == [0, 2]
    assert all(call[3] == "body.storage,body.view,version" for call in api.calls)


def test_page_and_children_are_normalized():
    api = FakeConfluence()
    client = ConfluenceClient(ConfluenceClientConfig("https://confluence.example"), "u", "secret", api=api)
    page = client.get_page("10")
    children = client.get_children("10")
    assert (page.title, page.version) == ("Status Report", 3)
    assert children[0].title == "Test Plan"


def test_user_display_name_reuses_atlassian_user_lookup():
    class UserApi(FakeConfluence):
        def get_user_details_by_userkey(self, user_key):
            assert user_key == "2c93-user-key"
            return {"userKey": user_key, "displayName": "Alice Chen"}

    client = ConfluenceClient(
        ConfluenceClientConfig("https://confluence.example"), "u", "secret", api=UserApi(),
    )
    assert client.get_user_display_name("2c93-user-key") == "Alice Chen"


def test_page_by_url_prefers_static_export_view_for_macro_catalogs():
    class ExportViewApi:
        def get_page_id(self, space, title):
            assert (space, title) == ("DOPL", "Project Space")
            return "catalog"

        def get_page_by_id(self, page_id, expand=None):
            assert page_id == "catalog"
            assert expand == "body.storage,body.view,body.export_view,version"
            return {
                "id": page_id,
                "title": "Project Space",
                "_links": {"webui": "/display/DOPL/Project+Space"},
                "body": {
                    "storage": {"value": "<ac:structured-macro />"},
                    "view": {"value": '<div class="table-filter-shell"></div>'},
                    "export_view": {"value": "<table><tr><th>页面</th></tr></table>"},
                },
            }

    client = ConfluenceClient(
        ConfluenceClientConfig("https://confluence.example"),
        "u", "secret", api=ExportViewApi(),
    )

    page = client.get_page_by_url(
        "https://confluence.example/display/DOPL/Project+Space",
        prefer_export=True,
    )

    assert page.view_body == "<table><tr><th>页面</th></tr></table>"


def test_password_never_leaks_from_construction_failure(monkeypatch):
    class Broken:
        def __init__(self, **kwargs):
            raise RuntimeError(f"bad {kwargs['password']}")

    monkeypatch.setattr("core.confluence.client.Confluence", Broken)
    with pytest.raises(RuntimeError) as captured:
        ConfluenceClient(ConfluenceClientConfig("https://confluence.example"), "u", "top-secret")
    assert "top-secret" not in str(captured.value)


@pytest.mark.parametrize(
    ("url", "expected_id"),
    [
        ("https://confluence.example/pages/viewpage.action?pageId=671973851", "671973851"),
        ("https://confluence.example/display/M314/Muffin314+Project+Home", "home-1"),
    ],
)
def test_get_page_by_url_resolves_page_id_and_display_urls(url, expected_id):
    client = ConfluenceClient(
        ConfluenceClientConfig("https://confluence.example"), "u", "secret",
        api=FakeConfluence(),
    )
    assert client.get_page_by_url(url).id == expected_id


def test_get_page_by_url_rejects_foreign_hosts():
    client = ConfluenceClient(
        ConfluenceClientConfig("https://confluence.example"), "u", "secret",
        api=FakeConfluence(),
    )
    with pytest.raises(ValueError):
        client.get_page_by_url("https://evil.example/pages/viewpage.action?pageId=1")


def test_get_historical_page_version_reuses_page_mapping():
    class HistoricalApi(FakeConfluence):
        def get_page_by_id(
            self, page_id, expand=None, status=None, version=None,
        ):
            assert (page_id, expand, status, version) == (
                "page-7", "body.storage,body.view,version", "historical", 3,
            )
            return {
                "id": page_id,
                "title": "Status Report",
                "body": {
                    "storage": {"value": "<h2>Highlights</h2><p>Old</p>"},
                    "view": {"value": "<h2>Highlights</h2><p>Old</p>"},
                },
                "version": {
                    "number": 3,
                    "when": "2026-08-03T01:02:03.000Z",
                },
                "_links": {"webui": "/pages/page-7"},
            }

    client = ConfluenceClient(
        ConfluenceClientConfig("https://confluence.example"),
        "u", "secret", api=HistoricalApi(),
    )

    page = client.get_page_version("page-7", 3)

    assert page.id == "page-7"
    assert page.version == 3
    assert page.body == "<h2>Highlights</h2><p>Old</p>"
    assert page.updated_at == datetime(2026, 8, 3, 1, 2, 3, tzinfo=timezone.utc)


def test_get_parent_page_uses_direct_parent_from_full_ancestor_chain():
    client = ConfluenceClient(
        ConfluenceClientConfig("https://confluence.example"), "u", "secret",
        api=FakeConfluence(),
    )
    parent = client.get_parent_page("671973853")
    assert parent.id == "671973851"
    assert parent.id != "671973853"


def test_get_page_children_paginates_and_preserves_page_metadata():
    class ChildApi:
        def __init__(self):
            self.calls = []

        def get_page_child_by_type(self, page_id, type="page", start=0, limit=100, expand=None):
            self.calls.append((page_id, start, limit, expand))
            rows = [
                {
                    "id": str(index),
                    "title": f"{2025 + index} Projects",
                    "_links": {"webui": f"/pages/{index}"},
                    "version": {"number": index + 3, "when": f"2026-07-2{index + 1}T01:02:03.000Z"},
                    "body": {"storage": {"value": f"<p>{index}</p>"}, "view": {"value": ""}},
                }
                for index in range(start, min(start + limit, 3))
            ]
            return {"results": rows, "totalSize": 3, "start": start, "limit": limit}

    api = ChildApi()
    client = ConfluenceClient(
        ConfluenceClientConfig("https://confluence.example"), "u", "secret", api=api,
    )
    pages = client.get_page_children("space", limit=2)
    assert [page.id for page in pages] == ["0", "1", "2"]
    assert pages[0].url == "https://confluence.example/pages/0"
    assert pages[0].version == 3
    assert pages[0].updated_at == datetime(2026, 7, 21, 1, 2, 3, tzinfo=timezone.utc)
    assert [call[1] for call in api.calls] == [0, 2]
    assert all(call[3] == "version" for call in api.calls)
    assert all(page.body == "" and page.view_body == "" for page in pages)


def test_get_page_children_accepts_atlassian_list_response():
    class ChildApi:
        def get_page_child_by_type(
            self, page_id, type="page", start=0, limit=100, expand=None,
        ):
            assert (page_id, type, start, limit, expand) == (
                "space", "page", 0, 100, "version",
            )
            return [{
                "id": "2026",
                "title": "2026 Projects",
                "_links": {"webui": "/pages/2026"},
                "version": {"number": 1, "when": "2026-07-21T01:02:03.000Z"},
            }]

    client = ConfluenceClient(
        ConfluenceClientConfig("https://confluence.example"), "u", "secret",
        api=ChildApi(),
    )

    pages = client.get_page_children("space")

    assert [page.title for page in pages] == ["2026 Projects"]


def test_get_page_children_paginates_atlassian_list_response():
    class ChildApi:
        def __init__(self):
            self.starts = []

        def get_page_child_by_type(
            self, page_id, type="page", start=0, limit=100, expand=None,
        ):
            self.starts.append(start)
            return [
                {"id": str(index), "title": f"Page {index}"}
                for index in range(start, min(start + limit, 101))
            ]

    api = ChildApi()
    client = ConfluenceClient(
        ConfluenceClientConfig("https://confluence.example"), "u", "secret",
        api=api,
    )

    pages = client.get_page_children("space")

    assert len(pages) == 101
    assert api.starts == [0, 100]


def test_get_page_children_rejects_repeated_list_page_when_start_is_ignored():
    rows = [{"id": str(index), "title": f"Page {index}"} for index in range(100)]

    class ChildApi:
        def get_page_child_by_type(self, *_args, **_kwargs):
            return rows

    client = ConfluenceClient(
        ConfluenceClientConfig("https://confluence.example"), "u", "secret",
        api=ChildApi(),
    )

    try:
        client.get_page_children("space")
    except RuntimeError as exc:
        assert "repeated" in str(exc).casefold()
    else:
        raise AssertionError("A list API that ignores start must fail safely")
