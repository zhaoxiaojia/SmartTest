import json
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

import jira_handler


ROOT = Path(__file__).resolve().parents[3]
PERSONNEL_PATH = ROOT / "config" / "personnel.json"
EXPECTED_QA_USERNAMES = """xiuyue.zhang
junjie.li
mao.ma
changwen.dai
xiangqun.li
leping.lei
jianfan.ai
jinbo.du
shaojun.chen
kai.ni
shuangxiao.hu
chunyan.liu
xinying.yang
bo.ren
zhangxian.chen
zhenhua.xiao
zanbo.huang
lingguo.bu
haolin.li
chenghua.liu
yongqi.liang
menghui.liu
jianhua.huang
maoguo.xie
cong.zhang
jie.xiong
jianhui.peng
ling.chen
zhewu.tao
meng.wang
binbin.gao
jiajia.mu
zhendong.zhou
yanyan.deng
xiaoli.peng
xing.fan
zhaoqun.wang
zijie.chen
bo.meng
yu.zhang
yonghua.wu
jian.zhong
yan.wu
ping.xiong
lingling.yu
pan.xu
chen.chen
dan.chen
chao.lu
chao.li
nannan.meng
kang.jiang
yanqing.tang
weiting.feng
taoqing.miao
chuanyang.hu
qianyi.liu
zhuhui.zhang
jinhuan.yi
yifeng.xu
shouneng.chou
mennan.hu
hanpeng.su
haobo.ren
meiling.zhu
xiaofeng.li
qin.zhang
xuejiao.li
mingdong.wang
zongwu.ma
yunzhu.zhang
zhijie.yang
tianwei.xie
bing.song
qiaowei.tian""".splitlines()


def valid_issue(**field_overrides):
    fields = {"summary": "[Skyworth][S905X4][14.0][System]: Settings crashes after reboot,50%",
        "components": [{"name": "System"}],
        "description": """[Steps to reproduce]:
1. Reboot the device;
[Actual results]:
Settings crashes
[Expected results]:
Settings opens
[Reproducibility rate]:
1/2
[Comparision]:
Previous version 20260712 was normal; current version 20260713 is broken.
[Notes]:
HW info: S905X4 reference board
SW info: build 20260713
""", "labels": ["Regression", "project-custom"], "attachment": [{"filename": "screen.png", "size": 1024}]}
    fields.update(field_overrides)
    return {"key": "ST-1", "self": "https://jira.example/rest/api/2/issue/ST-1", "fields": fields}


def xlsx_parts(path):
    with ZipFile(path) as archive:
        names = set(archive.namelist())
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        details = ElementTree.fromstring(archive.read("xl/worksheets/sheet2.xml"))
    return names, workbook, details


def test_valid_minimum_and_maximum_summaries_pass():
    assert jira_handler.validate_issue(valid_issue())["overall_result"] == "PASS"
    maximum = "[SWPL-1][Skyworth][SKY-2][S905X4][14.0][System]: Settings crashes,1/2"
    assert jira_handler.validate_issue(valid_issue(summary=maximum))["overall_result"] == "PASS"


def test_summary_reports_actual_invalid_values():
    result = jira_handler.validate_issue(valid_issue(summary="[客户][s905x4][14.0][Unknown]: 设置崩溃,often"))
    values = {v["rule_id"]: v["jira_value"] for v in result["violations"]}
    assert values["SUMMARY.CUSTOMER_ENGLISH"] == "客户"
    assert values["SUMMARY.CHIP_UPPERCASE"] == "s905x4"
    assert values["SUMMARY.MODULE"] == "Unknown"
    assert values["SUMMARY.DESCRIPTION_ENGLISH"] == "设置崩溃"
    assert values["SUMMARY.PROBABILITY"] == "often"


def test_description_requires_ordered_steps_and_all_bracket_sections():
    assert jira_handler.validate_issue(valid_issue())["overall_result"] == "PASS"
    broken = valid_issue()["fields"]["description"].replace("1. Reboot the device;", "2. ;")
    rules = {v["rule_id"] for v in jira_handler.validate_issue(valid_issue(description=broken))["violations"]}
    assert "DESCRIPTION.STEPS_ORDERED" in rules


def test_empty_reproducibility_rate_reports_violation_instead_of_crashing():
    description = valid_issue()["fields"]["description"].replace(
        "[Reproducibility rate]:\n1/2", "[Reproducibility rate]:\n"
    )
    result = jira_handler.validate_issue(valid_issue(description=description))
    assert any(
        violation["rule_id"] == "DESCRIPTION.REPRODUCIBILITY_RATE"
        for violation in result["violations"]
    )


def test_markdown_headings_are_supported():
    description = valid_issue()["fields"]["description"]
    description = "\n".join(f"## {line[1:line.index(']')]}" if line.startswith("[") else line for line in description.splitlines())
    assert jira_handler.validate_issue(valid_issue(description=description))["overall_result"] == "PASS"


def test_project_custom_labels_allowed_and_known_conditionals_apply():
    assert not any(v["rule_id"].startswith("LABEL.") for v in jira_handler.validate_issue(valid_issue(labels=["anything-project-needs"]))["violations"])
    no_versions = valid_issue()["fields"]["description"].replace("Previous version 20260712 was normal; current version 20260713 is broken.", "Compared on the same build.")
    assert any(v["rule_id"] == "REGRESSION.EVIDENCE" for v in jira_handler.validate_issue(valid_issue(description=no_versions))["violations"])
    too_big = 10 * 1024 * 1024 + 1
    assert any(v["rule_id"] == "ATTACHMENT.MAX_SIZE" for v in jira_handler.validate_issue(valid_issue(attachment=[{"size": too_big}]))["violations"])


def test_actual_repository_markdown_contract():
    rules = jira_handler.load_markdown_rules(ROOT / "jira规范.md")
    assert len(rules["allowed_modules"]) == 22
    labels = {value for values in rules["label_tables"].values() for value in values}
    assert {"Regression", "HDMI_TX_Type1", "HDMI-Cert", "GTVS-Cert"} <= labels
    assert rules["unsupported_sections"] == []


def test_markdown_columns_are_located_by_header(tmp_path):
    spec = tmp_path / "rules.md"
    spec.write_text("# Rules\n## Module\n| No | Summary 模块名称 |\n|---|---|\n|1|Custom|\n## Labels\n| Note | Label |\n|---|---|\n|x|Special|\n", encoding="utf-8")
    rules = jira_handler.load_markdown_rules(spec)
    assert rules["allowed_modules"] == ["Custom"]
    assert "Special" in rules["label_tables"]["Labels"]


def test_workbook_is_two_sheet_standard_library_xlsx(tmp_path):
    output = jira_handler.export_xlsx(jira_handler.validate_issues([valid_issue(), valid_issue(summary="bad")]), tmp_path / "audit.xlsx")
    names, workbook, details = xlsx_parts(output)
    assert {"xl/worksheets/sheet1.xml", "xl/worksheets/sheet2.xml"} <= names
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    assert [node.attrib["name"] for node in workbook.findall("m:sheets/m:sheet", ns)] == ["汇总", "违规明细"]
    text = "".join(details.itertext())
    assert all(
        heading in text
        for heading in (
            "Issue Key",
            "Issue URL",
            "检查结果",
            "规则编号",
            "规范章节",
            "规范要求/标准格式",
            "Jira 字段",
            "当前 Jira 内容",
            "失败原因",
            "修改建议",
        )
    )
    assert "不符合" in text
    assert "[客户英文名][CHIP][系统版本][Bug模块]: 英文问题描述,复现概率" in text
    assert "bad" in text


def test_summary_sheet_uses_chinese_metrics(tmp_path):
    output = jira_handler.export_xlsx(
        jira_handler.validate_issues([valid_issue()]), tmp_path / "audit.xlsx"
    )
    with ZipFile(output) as archive:
        summary = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    text = "".join(summary.itertext())
    assert all(
        value in text
        for value in (
            "指标",
            "值",
            "生成时间",
            "JQL 查询条件",
            "问题总数",
            "通过 Jira 数",
            "不通过 Jira 数",
            "通过率",
            "报告人",
            "违规 Jira 数量",
            "违规 Jira 号",
        )
    )


def test_reporter_normalization_prefers_display_name_and_has_fallbacks():
    assert jira_handler.normalize_issue(
        valid_issue(reporter={"displayName": "张三", "name": "zhang"})
    )["reporter"] == "张三"
    assert jira_handler.normalize_issue(valid_issue(reporter={"name": "lisi"}))[
        "reporter"
    ] == "Lisi"
    assert jira_handler.normalize_issue(valid_issue(reporter={"key": "wang"}))[
        "reporter"
    ] == "Wang"
    assert jira_handler.normalize_issue(valid_issue(reporter=None))["reporter"] == "未知报告人"


def test_personnel_json_schema_and_embedded_qa_list_match():
    personnel = json.loads(PERSONNEL_PATH.read_text(encoding="utf-8"))
    employees = personnel["employees"]
    expected_names = [
        " ".join(part.capitalize() for part in username.split("."))
        for username in EXPECTED_QA_USERNAMES
    ]
    expected_grades = {
        "Chao Li": "I3",
        "Xiuyue Zhang": "M5",
        "Ping Xiong": "M4",
        "Jianfan Ai": "M3",
        "Zijie Chen": "M3",
        "Junjie Li": "M3",
        "Meiling Zhu": "M3",
    }
    expected_assignments = {
        "Junjie Li": [
            {"product_line_id": "STB", "primary": True, "responsibilities": []}
        ],
        "Chen Chen": [
            {
                "product_line_id": "SmartHome",
                "primary": True,
                "responsibilities": [],
            }
        ],
        "Jianfan Ai": [
            {"product_line_id": "TV", "primary": True, "responsibilities": []}
        ],
        "Lingling Yu": [
            {"product_line_id": "IPTV", "primary": True, "responsibilities": []}
        ],
    }

    assert len(EXPECTED_QA_USERNAMES) == len(set(EXPECTED_QA_USERNAMES))
    assert personnel["schema_version"] == 1
    assert personnel["career_levels"] == [
        {
            "grade": "I2",
            "career_track": "individual_contributor",
            "job_title": "QA Engineer",
        },
        {
            "grade": "I3",
            "career_track": "individual_contributor",
            "job_title": "Sr. QA Engineer",
        },
        {
            "grade": "I4",
            "career_track": "individual_contributor",
            "job_title": "Staff QA Engineer",
        },
        {"grade": "M1", "career_track": "management", "job_title": "QA Leader"},
        {
            "grade": "M2",
            "career_track": "management",
            "job_title": "QA Supervisor",
        },
        {
            "grade": "M3",
            "career_track": "management",
            "job_title": "QA Manager",
        },
        {
            "grade": "M4",
            "career_track": "management",
            "job_title": "Sr. QA Manager",
        },
        {
            "grade": "M5",
            "career_track": "management",
            "job_title": "QA Director",
        },
    ]
    assert personnel["product_lines"] == [
        {"id": "STB", "name": "STB", "active": True},
        {"id": "SmartHome", "name": "SmartHome", "active": True},
        {"id": "TV", "name": "TV", "active": True},
        {"id": "IPTV", "name": "IPTV", "active": True},
    ]
    assert [item["display_name"] for item in employees] == expected_names
    assert {item["display_name"] for item in employees} == jira_handler.QA_REPORTER_NAMES
    assert all(
        item == {
            "display_name": item["display_name"],
            "active": True,
            "organization": {
                "department": "FAE-QA",
                "team": "",
                "division": "",
            },
            "employment": {
                "grade": expected_grades.get(item["display_name"], ""),
                "job_title_override": "",
                "employee_type": "",
            },
            "assignments": expected_assignments.get(item["display_name"], []),
            "expertise_domains": (
                ["Wi-Fi"] if item["display_name"] == "Zijie Chen" else []
            ),
            "system_roles": ["user"],
        }
        for item in employees
    )


def test_reporter_username_prefers_name_and_normalizes_domain_and_email():
    issue = valid_issue(
        reporter={
            "displayName": "QA User",
            "name": "DOMAIN\\Xiuyue.Zhang@example.com",
            "key": "wrong.key",
            "accountId": "wrong-account",
        }
    )
    assert jira_handler.normalize_issue(issue)["reporter_username"] == "xiuyue.zhang"
    assert jira_handler.normalize_issue(
        valid_issue(reporter={"key": "JUNJIE.LI@example.com"})
    )["reporter_username"] == "junjie.li"
    assert jira_handler.normalize_issue(
        valid_issue(reporter={"accountId": "MA.CHENG"})
    )["reporter_username"] == "ma.cheng"
    assert jira_handler.normalize_issue(valid_issue(reporter=None))[
        "reporter_username"
    ] == ""


def test_run_filters_to_qa_reporters_before_validation(monkeypatch, tmp_path):
    qa_issue = valid_issue(reporter={"name": "DOMAIN\\XIUYUE.ZHANG"})
    non_qa_issue = valid_issue(reporter={"name": "developer.user"})
    missing_reporter = valid_issue(reporter=None)
    validated = []

    monkeypatch.setattr(
        jira_handler,
        "fetch_jira_issues",
        lambda *args: [qa_issue, non_qa_issue, missing_reporter],
    )
    monkeypatch.setattr(
        jira_handler,
        "validate_issues",
        lambda issues, **kwargs: validated.extend(issues) or [],
    )
    monkeypatch.setattr(jira_handler, "export_xlsx", lambda *args, **kwargs: None)

    original = jira_handler.ISSUE_LIST
    result = jira_handler.run(
        {
            "base_url": "https://jira.example",
            "username": "user",
            "password": "test-only",
            "jql": "project = ST",
            "jira_url": "",
            "issue_keys": [],
            "output": str(tmp_path / "audit.xlsx"),
        }
    )

    assert result == 0
    assert jira_handler.ISSUE_LIST is original
    assert jira_handler.ISSUE_LIST == [qa_issue]
    assert validated == [qa_issue]


def test_run_matches_normalized_display_name_nannan_and_username_fallback(
    monkeypatch, tmp_path
):
    spaced_name = valid_issue(reporter={"displayName": "  XIUYUE   zhang  "})
    nannan = valid_issue(reporter={"displayName": "Nannan Meng"})
    username_fallback = valid_issue(reporter={"name": "junjie.li"})
    non_qa = valid_issue(reporter={"displayName": "Developer User"})
    validated = []
    monkeypatch.setattr(
        jira_handler,
        "fetch_jira_issues",
        lambda *args: [spaced_name, nannan, username_fallback, non_qa],
    )
    monkeypatch.setattr(
        jira_handler,
        "validate_issues",
        lambda issues, **kwargs: validated.extend(issues) or [],
    )
    monkeypatch.setattr(jira_handler, "export_xlsx", lambda *args, **kwargs: None)

    jira_handler.run(
        {
            "base_url": "https://jira.example",
            "username": "user",
            "password": "test-only",
            "jql": "project = ST",
            "jira_url": "",
            "issue_keys": [],
            "output": str(tmp_path / "audit.xlsx"),
        }
    )

    assert validated == [spaced_name, nannan, username_fallback]


def test_summary_groups_failed_jira_by_reporter_with_unique_sorted_keys(tmp_path):
    first = valid_issue(summary="bad", components=[], reporter={"displayName": "Alice"})
    second = valid_issue(summary="bad", reporter={"displayName": "Alice"})
    second["key"] = "ST-2"
    third = valid_issue(summary="bad", reporter={"displayName": "Bob"})
    third["key"] = "ST-3"
    rows = jira_handler.validate_issues([first, first, second, third, valid_issue()])
    output = jira_handler.export_xlsx(rows, tmp_path / "audit.xlsx")
    with ZipFile(output) as archive:
        summary = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    text = "".join(summary.itertext())
    assert "Alice2ST-1、ST-2" in text
    assert "Bob1ST-3" in text
    assert "规则违规：" not in text
    assert "违规总数" not in text


def test_fetch_requests_reporter_field(monkeypatch):
    requested = []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self): return json.dumps({"issues": [], "total": 0}).encode()

    monkeypatch.setattr(
        jira_handler,
        "urlopen",
        lambda request, timeout: requested.append(request.full_url) or Response(),
    )
    jira_handler.fetch_jira_issues("https://jira.example", "project = ST", "u", "p")
    assert "reporter" in requested[0]


def test_workbook_has_readable_styles_widths_freeze_and_filter(tmp_path):
    output = jira_handler.export_xlsx(
        jira_handler.validate_issues([valid_issue(summary="bad")]),
        tmp_path / "audit.xlsx",
    )
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rel_ns = {
        "r": "http://schemas.openxmlformats.org/package/2006/relationships"
    }
    with ZipFile(output) as archive:
        assert "xl/styles.xml" in archive.namelist()
        styles = ElementTree.fromstring(archive.read("xl/styles.xml"))
        content_types = archive.read("[Content_Types].xml").decode("utf-8")
        relationships = ElementTree.fromstring(
            archive.read("xl/_rels/workbook.xml.rels")
        )
        summary = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        details = ElementTree.fromstring(archive.read("xl/worksheets/sheet2.xml"))

    assert 'PartName="/xl/styles.xml"' in content_types
    assert any(
        node.attrib.get("Target") == "styles.xml"
        for node in relationships.findall("r:Relationship", rel_ns)
    )
    assert styles.find("m:cellXfs", ns).attrib["count"] == "3"
    assert [float(node.attrib["width"]) for node in summary.findall("m:cols/m:col", ns)] == [28, 18, 85]
    assert [float(node.attrib["width"]) for node in details.findall("m:cols/m:col", ns)] == [14, 38, 10, 34, 18, 55, 22, 65, 38, 38]
    for sheet in (summary, details):
        pane = sheet.find("m:sheetViews/m:sheetView/m:pane", ns)
        assert pane.attrib == {
            "ySplit": "1",
            "topLeftCell": "A2",
            "activePane": "bottomLeft",
            "state": "frozen",
        }
        assert all(
            cell.attrib.get("s") == "1"
            for cell in sheet.findall("m:sheetData/m:row[@r='1']/m:c", ns)
        )
    assert all(
        cell.attrib.get("s") == "1"
        for cell in summary.findall("m:sheetData/m:row[@r='9']/m:c", ns)
    )
    assert details.find("m:autoFilter", ns).attrib["ref"].startswith("A1:J")


def configured(**overrides):
    config = dict(jira_handler.JIRA_CONFIG)
    config.update({"base_url": "https://jira.example", "username": "user", "password": "secret", "output": "audit.xlsx"})
    config.update(overrides)
    return config


def test_query_sources_support_keys_browse_search_and_direct_jql():
    assert jira_handler.resolve_jql(configured(issue_keys=["ST-1", "ST-2"])) == "key in (ST-1, ST-2)"
    assert jira_handler.resolve_jql(configured(issue_keys=[], jira_url="https://jira.example/browse/ST-3")) == 'key = "ST-3"'
    search = "https://jira.example/issues/?jql=project%20%3D%20ST%20AND%20status%20%3D%20Open"
    assert jira_handler.resolve_jql(configured(issue_keys=[], jira_url=search)) == "project = ST AND status = Open"
    assert jira_handler.resolve_jql(configured(issue_keys=[], jira_url="", jql="project = ST")) == "project = ST"


def test_filter_url_loads_jql_through_rest(monkeypatch):
    requested = []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self): return json.dumps({"jql": "project = FILTERED"}).encode()

    def fake_urlopen(request, timeout):
        requested.append((request, timeout))
        return Response()

    monkeypatch.setattr(jira_handler, "urlopen", fake_urlopen)
    value = jira_handler.resolve_jql(configured(issue_keys=[], jira_url="https://jira.example/issues/?filter=12345"))
    assert value == "project = FILTERED"
    assert requested[0][0].full_url == "https://jira.example/rest/api/2/filter/12345"
    assert "secret" not in repr(requested[0][0].headers)


def test_run_updates_global_issue_list_in_place_and_fetches_once(monkeypatch, tmp_path):
    original = jira_handler.ISSUE_LIST
    calls = []
    issue = valid_issue(reporter={"name": "xiuyue.zhang"})
    monkeypatch.setattr(
        jira_handler,
        "fetch_jira_issues",
        lambda *args: calls.append(args) or [issue],
    )
    monkeypatch.setattr(jira_handler, "export_xlsx", lambda results, output, **kwargs: list(results))
    assert jira_handler.run(configured(issue_keys=["ST-1"], output=str(tmp_path / "audit.xlsx"))) == 0
    assert jira_handler.ISSUE_LIST is original
    assert jira_handler.ISSUE_LIST == [issue]
    assert len(calls) == 1


def test_top_level_config_has_required_keys():
    assert set(jira_handler.JIRA_CONFIG) == {"base_url", "username", "password", "jql", "jira_url", "issue_keys", "output"}
