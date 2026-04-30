from pathlib import Path

from jira_tool.cache.metadata_cache import JiraFieldMetadataCache
from jira_tool.core.models import JiraFieldMetadata
from jira_tool.fields.registry import FieldRegistry


class FakeClient:
    def __init__(self, metadata_items):
        self._metadata_items = metadata_items
        self.fetch_count = 0

        class _Config:
            base_url = "https://jira.example.com"

        self.config = _Config()

    def fetch_fields_metadata(self):
        self.fetch_count += 1
        return list(self._metadata_items)


def test_metadata_cache_round_trip(tmp_path: Path) -> None:
    cache = JiraFieldMetadataCache(tmp_path / "jira_meta.db")
    metadata_items = [
        JiraFieldMetadata(
            field_id="customfield_50001",
            name="Domain",
            schema_type="string",
            custom=True,
            custom_id=50001,
        )
    ]

    cache.put(base_url="https://jira.example.com", metadata_items=metadata_items)
    loaded = cache.get(base_url="https://jira.example.com", ttl_seconds=60)

    assert loaded is not None
    assert loaded[0].field_id == "customfield_50001"
    assert loaded[0].name == "Domain"


def test_registry_bootstrap_uses_cache_before_client_fetch(tmp_path: Path) -> None:
    cache = JiraFieldMetadataCache(tmp_path / "jira_meta.db")
    metadata_items = [
        JiraFieldMetadata(
            field_id="customfield_50002",
            name="Wi-Fi Area",
            schema_type="string",
            custom=True,
            custom_id=50002,
        )
    ]
    cache.put(base_url="https://jira.example.com", metadata_items=metadata_items)

    client = FakeClient(
        [
            JiraFieldMetadata(
                field_id="customfield_99999",
                name="Should Not Be Used",
                schema_type="string",
                custom=True,
                custom_id=99999,
            )
        ]
    )

    registry = FieldRegistry.bootstrap_from_client(client, metadata_cache=cache, ttl_seconds=60)
    plan = registry.build_plan(["wifi_area"])

    assert client.fetch_count == 0
    assert plan.active_specs[0].name == "Wi-Fi Area"
