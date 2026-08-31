from __future__ import annotations

import pytest

from core.domain.detail import DetailSection, DetailState


def test_detail_section_distinguishes_unloaded_from_loaded_empty() -> None:
    unloaded = DetailSection[tuple[str, ...]]()
    loaded_empty = DetailSection.loaded(())

    assert unloaded.state is DetailState.UNLOADED
    assert unloaded.value is None
    assert loaded_empty.state is DetailState.LOADED
    assert loaded_empty.value == ()


def test_stale_and_failed_sections_keep_last_successful_value() -> None:
    stale = DetailSection.stale(("kept",), source_revision="8")
    failed = DetailSection.failed("jira_comments_unavailable", value=("kept",))

    assert stale.state is DetailState.STALE
    assert stale.value == ("kept",)
    assert failed.state is DetailState.FAILED
    assert failed.value == ("kept",)
    assert failed.error_code == "jira_comments_unavailable"


@pytest.mark.parametrize(
    "factory",
    [
        lambda: DetailSection(state=DetailState.UNLOADED, value=()),
        lambda: DetailSection(state=DetailState.STALE),
        lambda: DetailSection(state=DetailState.FAILED),
    ],
)
def test_detail_section_rejects_state_that_loses_its_meaning(factory) -> None:
    with pytest.raises(ValueError):
        factory()
