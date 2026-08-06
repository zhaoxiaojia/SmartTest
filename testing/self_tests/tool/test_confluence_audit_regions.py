import pytest

from support.confluence_integration.models import ConfluencePage
from tool.common.project_weekly_audit.models import UPDATE_MATRIX_POINTS
from tool.common.project_weekly_audit.regions import (
    extract_page_region,
    extract_project_owner,
    extract_region,
)


@pytest.mark.parametrize(
    ("point", "heading_name"),
    [
        (point, heading_name)
        for point in UPDATE_MATRIX_POINTS
        for heading_name in point.heading_names
    ],
)
def test_confirmed_heading_names_locate_the_same_audit_point(point, heading_name):
    body = f"<h2>{heading_name}</h2><p>Region value</p><h2>Next</h2><p>Other</p>"

    assert extract_region(body, point).content.startswith("Region value")


def test_numbered_template_heading_is_matched_exactly_after_decoration_normalization():
    point = next(row for row in UPDATE_MATRIX_POINTS if row.rule_id == "test.tasks")
    body = (
        "<h2>IV. Task Arrangement of Important Test :</h2>"
        "<p>Regression complete</p><h2>V. History :</h2><p>Old</p>"
    )

    assert extract_region(body, point).content == "Regression complete"


def test_inline_summary_field_is_split_from_its_value():
    point = next(row for row in UPDATE_MATRIX_POINTS if row.rule_id == "test.summary")
    body = "<table><tr><td>项目整体状态Summary : DVT testing complete</td></tr></table>"

    assert extract_region(body, point).content == "DVT testing complete"


def test_phase_status_field_locates_weekly_status():
    point = next(row for row in UPDATE_MATRIX_POINTS if row.rule_id == "test.weekly")
    body = (
        "<table><tr><th>Phase（当前阶段）</th><td>FC</td>"
        "<th>Phase Status（当前阶段测试状态）</th><td>Yellow</td></tr></table>"
    )

    assert extract_region(body, point).content == "Yellow"


def test_summary_field_still_extracts_its_value_not_the_whole_table():
    point = next(row for row in UPDATE_MATRIX_POINTS if row.rule_id == "test.summary")
    body = (
        "<table><tr><th>项目整体状态Summary</th><td>DVT complete</td></tr>"
        "<tr><td>Unrelated</td><td>Other content</td></tr></table>"
    )

    assert extract_region(body, point).content == "DVT complete"


def test_test_plan_uses_category_field_instead_of_whole_page():
    point = next(row for row in UPDATE_MATRIX_POINTS if row.rule_id == "plan.test")
    body = (
        "<table><tr><th>Category</th><th>Sub-Item</th><th>August</th></tr>"
        "<tr><td>Function</td><td>Weekly regression</td><td>Done</td></tr></table>"
    )

    assert extract_region(body, point).content == "Function Weekly regression Done"
    assert extract_region("<p>Unstructured plan</p>", point).found is False
    assert extract_region(
        "<table><tr><th>Category</th><th>Sub-Item</th><th>August</th></tr></table>",
        point,
    ).content == ""


def test_environment_setup_uses_confirmed_combined_heading_content():
    point = next(row for row in UPDATE_MATRIX_POINTS if row.rule_id == "environment.setup")
    body = "<h3>测试环境搭建以及注意事项</h3><p>Connect the customer board.</p>"

    assert extract_region(body, point).content == "Connect the customer board."


def test_empty_experience_page_is_present_empty_content():
    body = "<h3>经验总结与典型案例</h3>"
    point = next(row for row in UPDATE_MATRIX_POINTS if row.rule_id == "experience.page")

    assert extract_region(body, point).content == ""


def test_experience_page_does_not_require_an_internal_matching_heading():
    point = next(row for row in UPDATE_MATRIX_POINTS if row.rule_id == "experience.page")

    assert extract_region("<p>Use the validated USB procedure.</p>", point).content == (
        "Use the validated USB procedure."
    )


def test_experience_page_uses_all_content_after_confirmed_heading():
    body = "<h3>经验总结与典型案例</h3><p>1. U盘读写速度测试</p>"
    point = next(row for row in UPDATE_MATRIX_POINTS if row.rule_id == "experience.page")

    assert extract_region(body, point).content == "1. U盘读写速度测试"


def test_highlights_locator_does_not_include_a_different_status_field():
    point = next(row for row in UPDATE_MATRIX_POINTS if row.rule_id == "status.highlights")

    assert point.heading_names == ("Highlights",)
    assert extract_region(
        "<h2>Key Target and Completeness（Development Stage）</h2><p>Done</p>",
        point,
    ).found is False


def test_empty_heading_is_structurally_found():
    point = next(row for row in UPDATE_MATRIX_POINTS if row.rule_id == "test.blocking")

    result = extract_region("<h2>III. Blocking QA Testing Items：</h2>", point)

    assert result.found is True
    assert result.content == ""
    assert result.element_type == "heading"


def test_missing_heading_is_not_found():
    point = next(row for row in UPDATE_MATRIX_POINTS if row.rule_id == "test.blocking")

    assert extract_region("<h2>Other field</h2>", point).found is False


@pytest.mark.parametrize("tag", ["p", "span"])
def test_plain_label_is_found_independent_of_style(tag):
    point = next(row for row in UPDATE_MATRIX_POINTS if row.rule_id == "status.highlights")
    body = (
        f'<{tag} style="font-size: 17px; color: red"><b>• Highlights</b></{tag}>'
        "<p>No content found.</p><h2>Impact issues</h2>"
    )

    result = extract_region(body, point)

    assert result.found is True
    assert result.content == ""
    assert result.element_type == tag


def test_heading_inline_value_is_region_content():
    point = next(row for row in UPDATE_MATRIX_POINTS if row.rule_id == "test.weekly")

    result = extract_region(
        "<h2>I. Software Testing Status : Yellow IN PROGRESS</h2>", point,
    )

    assert result.found is True
    assert result.content == "Yellow IN PROGRESS"
    assert result.boundary == "heading_sibling"


def test_environment_page_boundary_includes_nested_higher_level_sections():
    point = next(row for row in UPDATE_MATRIX_POINTS if row.rule_id == "environment.setup")
    body = (
        "<h3>测试环境搭建以及注意事项</h3>"
        "<h2>一、烧录流程</h2><p>adb reboot update</p>"
        "<h2>二、版本下载</h2><p>Download the validated build.</p>"
    )

    result = extract_region(body, point)

    assert result.found is True
    assert "adb reboot update" in result.content
    assert result.boundary == "page_end"


@pytest.mark.parametrize("rule_id", ["experience.page", "report.weekly"])
def test_required_child_page_is_found_even_when_body_is_empty(rule_id):
    point = next(row for row in UPDATE_MATRIX_POINTS if row.rule_id == rule_id)

    result = extract_region("", point)

    assert result.found is True
    assert result.content == ""
    assert result.element_type == "page"


def test_page_body_locator_falls_back_to_storage_when_view_is_unavailable():
    point = next(row for row in UPDATE_MATRIX_POINTS if row.rule_id == "experience.page")
    page = ConfluencePage(
        "1", "Summary of Experience and Typical Cases", "https://c/1",
        body="<p>Validated case</p>", view_body="",
    )

    result = extract_page_region(page, point)

    assert result.found is True
    assert result.content == "Validated case"
    assert result.source == "storage"


def test_table_field_value_is_the_audit_region():
    point = next(
        row for row in UPDATE_MATRIX_POINTS if row.rule_id == "test.tasks"
    )
    body = (
        "<table><tr><th>Task Arrangement of Important Test（Must give ETA）</th>"
        "<td><p>Task A complete</p></td></tr></table>"
    )

    assert extract_region(body, point).content == "Task A complete"


def test_confluence_macro_title_locates_its_body_region():
    point = next(
        row for row in UPDATE_MATRIX_POINTS if row.rule_id == "test.blocking"
    )
    body = (
        '<ac:structured-macro ac:name="panel">'
        '<ac:parameter ac:name="title">Blocking QA Testing Items</ac:parameter>'
        "<ac:rich-text-body><p>No blockers</p></ac:rich-text-body>"
        "</ac:structured-macro>"
    )

    assert extract_region(body, point).content == "No blockers"


def test_project_owner_extracts_all_qa_names_in_order_without_mentions():
    page = ConfluencePage(
        "status", "Project Status Report", "https://c/status",
        body=(
            "<table><tr><th>Window(Major FAE SW/HW/QA)</th>"
            "<td>Major FAE: @Lead SW/HW: @Developer QA: @Alice @Bob</td>"
            "</tr></table>"
        ),
    )

    assert extract_project_owner(page) == "Alice Bob"


@pytest.mark.parametrize(
    "body",
    [
        "<table><tr><th>Other</th><td>QA: @Alice</td></tr></table>",
        "<table><tr><th>Window(Major FAE SW/HW/QA)</th><td>SW: @Dev</td></tr></table>",
        "<table><tr><th>Window(Major FAE SW/HW/QA)</th><td>QA: @ </td></tr></table>",
    ],
)
def test_project_owner_reports_missing_qa_for_missing_field_marker_or_value(body):
    page = ConfluencePage(
        "status", "Project Status Report", "https://c/status", body=body,
    )

    assert extract_project_owner(page) == "格式有误：查询不到QA"
