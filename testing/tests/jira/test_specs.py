from jira.services.specs import browse_specs, detail_specs


def test_browse_specs_stay_lightweight() -> None:
    names = [spec if isinstance(spec, str) else spec.name for spec in browse_specs()]
    assert "comments" not in names
    assert "issuelinks" not in names
    assert "project" in names


def test_detail_specs_include_optional_heavy_fields() -> None:
    names = [
        spec if isinstance(spec, str) else spec.name
        for spec in detail_specs(include_comments=True, include_links=True)
    ]
    assert "comments" in names
    assert "issuelinks" in names
    assert "issueType" in names
