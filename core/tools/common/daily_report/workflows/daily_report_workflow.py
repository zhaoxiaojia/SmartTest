"""Standalone A9 Yocto daily-report workflow for the workbench."""

from collections import Counter
from datetime import date, datetime, timedelta
from html import escape
import base64
import json
import re


_EMAIL = re.compile(r"^[^\s@,;]+@[^\s@,;]+\.[^\s@,;]+$")


def _named(value):
    if isinstance(value, dict):
        return str(value.get("displayName") or value.get("name") or value.get("value") or "")
    return "" if value is None else str(value)


def _names(value):
    if value is None:
        return ()
    if isinstance(value, str):
        value = value.split(",")
    elif isinstance(value, dict):
        value = (value,)
    return tuple(
        name
        for item in value
        if (name := _named(item).strip()) and name.casefold() != "none"
    )


def _timestamp(value):
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    if len(text) >= 5 and text[-5] in "+-" and text[-4:].isdigit():
        text = text[:-2] + ":" + text[-2:]
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _records(result):
    if isinstance(result, dict):
        result = result.get("issues", result.get("values", []))
    if not isinstance(result, (list, tuple)):
        return ()
    normalized = {}
    for record in result:
        if not isinstance(record, dict):
            continue
        fields = record.get("fields") if isinstance(record.get("fields"), dict) else record
        key = str(record.get("key") or fields.get("key") or "").strip()
        if not key:
            continue
        normalized[key] = {
            "key": key,
            "summary": _named(fields.get("summary")),
            "status": _named(fields.get("status")),
            "assignee": _named(fields.get("assignee")),
            "priority": _named(fields.get("priority")),
            "components": _names(fields.get("components")),
            "created": _timestamp(fields.get("created")),
            "updated": _timestamp(fields.get("updated")),
            "url": _named(record.get("url") or record.get("self")),
        }
    return tuple(normalized.values())


def _history_jql(day, jql):
    historical_status = (
        f'status WAS NOT IN (Closed, Done, Verified) ON "{day.isoformat()}"'
    )
    status_filter = re.compile(
        r"\bstatus\s+(?:was\s+)?not\s+in\s*\([^)]*\)(?:\s+on\s+\"[^\"]+\")?",
        re.IGNORECASE,
    )
    if status_filter.search(jql):
        return status_filter.sub(historical_status, jql, count=1)
    return f"{historical_status} AND ({jql})"


def _metric_jql(jql, condition):
    return f"({jql.strip()}) AND {condition}"


def _jql_string(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _search_issues(wf, jql):
    response = wf.call_tool("jira_search_issues", jql=jql)
    if isinstance(response, (dict, list, tuple)):
        return _records(response)
    if not isinstance(response, str):
        raise ValueError("unexpected Jira search response")
    if re.search(r"(?:未找到|没有找到|\bno\s+(?:matching\s+)?issues?\b|\b0\s*个问题)", response, re.IGNORECASE):
        return ()
    search_match = re.search(r"search_id\s*[:：]\s*([A-Za-z0-9_-]+)", response, re.IGNORECASE)
    pages_match = re.search(r"分为\s*(\d+)\s*页", response)
    if not search_match:
        raise ValueError(
            f"unexpected Jira search response for JQL {jql!r}: {response}"
        )
    page_count = int(pages_match.group(1)) if pages_match else 1
    if page_count < 1:
        raise ValueError("unexpected Jira search response")
    search_id = search_match.group(1)
    issues = []
    for page_num in range(1, page_count + 1):
        page = wf.read_file(f"jira/{search_id}/page_{page_num}.json")
        if isinstance(page, str):
            try:
                page = json.loads(page)
            except json.JSONDecodeError as exc:
                raise ValueError("invalid Jira search page JSON") from exc
        if not isinstance(page, dict) or not isinstance(page.get("issues"), list):
            raise ValueError("invalid Jira search page payload")
        issues.extend(page["issues"])
    return _records(issues)


def _server_component_counts(wf, jql, issues):
    candidates = tuple(dict.fromkeys(
        component
        for issue in issues
        for component in issue.get("components", ())
        if component
    ))
    counts = []
    for component in candidates:
        scoped_jql = _metric_jql(
            jql, 'component = "{}"'.format(_jql_string(component))
        )
        counts.append((component, len(_search_issues(wf, scoped_jql))))
    return sorted(counts, key=lambda item: item[1], reverse=True)


def _email_list(value, name, *, required):
    if isinstance(value, str):
        items = re.split(r"[,;]", value)
    elif isinstance(value, (list, tuple)):
        items = value
    else:
        raise ValueError(f"{name} must be an email list")
    result = tuple(dict.fromkeys(str(item).strip() for item in items if str(item).strip()))
    if required and not result:
        raise ValueError(f"{name} must not be empty")
    if any(not _EMAIL.fullmatch(item) for item in result):
        raise ValueError(f"{name} contains an invalid email address")
    return result


def _integer(value, name, minimum, maximum):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    if not isinstance(value, int) and not (
        isinstance(value, str) and re.fullmatch(r"[+-]?\d+", value.strip())
    ):
        raise ValueError(f"{name} must be an integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= result <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return result


def _boolean(value, name):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    raise ValueError(f"{name} must be a boolean")


def _validated_config(wf):
    config = {
        "project_name": wf.input("project_name", "", description="项目名称"),
        "jql": wf.input(
            "jql",
            "status not in (Closed, Done, Verified) AND labels = Linux-A9_Yocto",
            description="当前未关闭 Issue 的 Jira JQL",
        ),
        "recipients": wf.input(
            "recipients", "chao.li@amlogic.com", description="收件人列表"
        ),
        "cc": wf.input(
            "cc",
            "ping.xiong@amlogic.com,xiuyue.zhang@amlogic.com",
            description="抄送人列表",
        ),
        "subject": wf.input(
            "subject", "[A9 Yocto] 公版状态日报", description="邮件主题"
        ),
        "detail_priorities": wf.input(
            "detail_priorities", "P0,P1", description="明细优先级，多个值用逗号分隔"
        ),
        "trend_days": wf.input("trend_days", 14, description="趋势天数，范围 2 到 365"),
        "stale_days": wf.input("stale_days", 7, description="停滞判定天数，范围 1 到 365"),
        "send_email": wf.input("send_email", True, description="是否发送邮件"),
    }
    for name in ("project_name", "jql", "subject"):
        value = config[name]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must not be empty")
        config[name] = value.strip()
    config["recipients"] = _email_list(config["recipients"], "recipients", required=True)
    config["cc"] = _email_list(config["cc"], "cc", required=False)
    if isinstance(config["detail_priorities"], str):
        raw_priorities = config["detail_priorities"].split(",")
    elif isinstance(config["detail_priorities"], (list, tuple)):
        raw_priorities = config["detail_priorities"]
    else:
        raise ValueError("detail_priorities must be a list")
    config["detail_priorities"] = tuple(
        dict.fromkeys(str(item).strip().upper() for item in raw_priorities if str(item).strip())
    )
    if not config["detail_priorities"]:
        raise ValueError("detail_priorities must not be empty")
    config["trend_days"] = _integer(config["trend_days"], "trend_days", 2, 365)
    config["stale_days"] = _integer(config["stale_days"], "stale_days", 1, 365)
    config["send_email"] = _boolean(config["send_email"], "send_email")
    return config


def _bar_rows(values):
    values = list(values)
    maximum = max((count for _, count in values), default=0)
    return "".join(
        '<tr><td class="bar-label">{}</td><td><div class="bar-track"><div class="bar-fill" style="width:{}%"></div></div></td><td class="bar-count">{}</td></tr>'.format(
            escape(name or "未设置"), round(count * 100 / maximum) if maximum else 0, count
        )
        for name, count in values
    ) or '<tr><td class="muted">—</td></tr>'


CHART_COLORS = (
    "#5470c6",
    "#91cc75",
    "#fac858",
    "#ee6666",
    "#73c0de",
    "#3ba272",
)


def _status_legend(values):
    values = list(values)[:6]
    total = sum(count for _, count in values)
    rows = []
    for index, (name, count) in enumerate(values):
        rows.append(
            '<tr class="status-legend-item"><td><span class="legend-swatch" style="background:{}"></span></td>'
            '<td class="status-name">{}</td><td class="status-percentage">{:.1f}%</td></tr>'.format(
                CHART_COLORS[index],
                escape(name or "未设置"),
                count * 100 / total if total else 0,
            )
        )
    return '<table class="status-legend" role="presentation">{}</table>'.format(
        "".join(rows) or '<tr><td class="muted">暂无状态数据</td></tr>'
    )


def _decoded_png(payload):
    if not payload or re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", payload) is None:
        return False
    try:
        decoded = base64.b64decode(payload, validate=True)
    except Exception:
        return False
    return decoded.hex().startswith("89504e470d0a1a0a")


def _png_summary(content):
    signature = content.hex().startswith("89504e470d0a1a0a")
    width = None
    height = None
    if signature and len(content) >= 24 and content[12:16].hex() == "49484452":
        width = sum(content[16 + index] << (24 - index * 8) for index in range(4))
        height = sum(content[20 + index] << (24 - index * 8) for index in range(4))
    return len(content), signature, width, height


def _chart_data_uri(wf, tool_name, arguments):
    response = wf.call_tool(tool_name, **arguments)
    match = re.search(r"Success: .* saved to (charts/[A-Za-z0-9_.-]+\.png)(?:\s|$)", str(response))
    if not match:
        raise RuntimeError(f"{tool_name} did not return a safe PNG path")
    path = match.group(1)
    content = wf.read_file(path)
    content_is_text = isinstance(content, str)
    if content_is_text:
        if content.startswith("data:image/png;base64,"):
            payload = "".join(content.split(",", 1)[1].split())
            if not _decoded_png(payload):
                raise RuntimeError(f"{tool_name} returned an invalid PNG data URI")
            encoded = payload
        else:
            compact = "".join(content.split())
            if _decoded_png(compact):
                encoded = compact
            else:
                try:
                    raw = content.encode("latin-1")
                except UnicodeEncodeError as error:
                    raise RuntimeError(
                        f"{tool_name} returned text that cannot represent PNG binary"
                    ) from error
                if not raw.hex().startswith("89504e470d0a1a0a"):
                    raise RuntimeError(f"{tool_name} returned text without a PNG signature")
                encoded = base64.b64encode(raw).decode("ascii")
    else:
        encoded = base64.b64encode(content).decode("ascii")
    decoded = base64.b64decode(encoded, validate=True)
    if not _png_summary(decoded)[1]:
        raise RuntimeError(f"{tool_name} returned data without a PNG signature")
    return "data:image/png;base64," + encoded


def _render_html(
    config, issues, trend, today, status_image, trend_image, *,
    created_today_keys=None, updated_today_keys=None, stale_keys=None,
    component_counts=None,
):
    trend = list(trend)
    priorities = Counter(issue["priority"] or "未设置" for issue in issues)
    statuses = Counter(issue["status"] or "未设置" for issue in issues)
    modules = Counter(
        component for issue in issues for component in (issue["components"] or ("未设置",))
    ) if component_counts is None else Counter(dict(component_counts))
    created_today = len(created_today_keys) if created_today_keys is not None else sum(
        bool(issue["created"] and issue["created"].date() == today) for issue in issues
    )
    updated_today = len(updated_today_keys) if updated_today_keys is not None else sum(
        bool(issue["updated"] and issue["updated"].date() == today) for issue in issues
    )
    stale = set(stale_keys) if stale_keys is not None else {
        issue["key"] for issue in issues
        if issue["updated"] is not None
        and (today - issue["updated"].date()).days >= config["stale_days"]
    }
    selected = {item.casefold() for item in config["detail_priorities"]}
    details = "".join(
        "<tr><td style='padding:6px'><a href='{}'>{}</a></td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            escape(issue["url"], quote=True), escape(issue["key"]), escape(issue["summary"] or "未设置"),
            escape(issue["status"] or "未设置"), escape(issue["priority"] or "未设置"),
            escape(issue["assignee"] or "未设置"), "是" if issue["key"] in stale else "否",
        )
        for issue in issues if issue["priority"].casefold() in selected
    ) or "<tr><td colspan='7'>当前无 Issue</td></tr>"
    def metric(label, value, note, identity):
        return (
            '<td width="25%" class="metric-cell"><div class="metric-card" data-metric="{}">'
            '<div class="metric-label">{}</div><div class="metric-value">{}</div>'
            '<div class="metric-note">{}</div></div></td>'
        ).format(identity, escape(label), value, escape(note))

    shown_priorities = escape(", ".join(config["detail_priorities"]))
    p0 = priorities.get("P0", 0)
    p1 = priorities.get("P1", 0)
    p2 = priorities.get("P2", 0)
    metric_rows = "".join((
        metric("今日创建", created_today, "本地日期", "created"),
        metric("今日更新", updated_today, "本地日期", "updated"),
        metric("P0 / 高优先级", p0, "需优先关注", "p0"),
        metric(f"停滞 ≥ {config['stale_days']} 天", len(stale), "最后更新时间", "stale"),
    ))
    priority_rows = _bar_rows((("P0", p0), ("P1", p1), ("P2", p2), (f"停滞 ≥ {config['stale_days']} 天", len(stale))))
    status_chart = (
        '<div class="status-chart-crop" style="width:200px;height:200px;overflow:hidden;margin:auto">'
        '<img data-chart="status-composition" src="{}" alt="状态 分布" '
        'style="display:block;height:200px;width:auto;max-width:none"></div>{}'
    ).format(
        status_image,
        _status_legend(statuses.most_common(6)),
    )
    trend_chart = '<img data-chart="unclosed-trend" width="640" height="320" src="{}" alt="每日未关闭趋势" style="display:block;width:640px;height:320px;max-width:100%;margin:auto">'.format(
        trend_image
    )
    trend_note = "缺失日期不进行推测或插值。"
    rich_styles = """body{margin:0;background:#eef1f5;font-family:Arial,'Microsoft YaHei',sans-serif;color:#172b4d}.report-canvas{width:860px;max-width:calc(100% - 28px);margin:16px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 8px 28px rgba(9,30,66,.10)}.section{padding:24px 28px;border-bottom:1px solid #e4e7ec}.section-title{font-size:18px;font-weight:bold;margin-bottom:14px}.metric-table,.paired-row{table-layout:fixed;border-spacing:6px}.metric-cell,.paired-cell{vertical-align:top}.metric-card,.panel{background:#fff;border:1px solid #dfe3e8;border-radius:10px;box-sizing:border-box}.metric-card{height:118px;padding:18px 15px}.metric-label,.metric-note,.muted{font-size:12px;color:#667085}.metric-value{font-size:34px;font-weight:bold;margin:7px 0}.panel{height:300px;padding:13px;overflow:hidden}.row-a .panel{height:380px}.row-b .panel{height:225px}.panel h3{margin:0 0 12px;font-size:14px}.bar-table{border-collapse:collapse;font-size:11px}.bar-table td{padding:7px 3px}.bar-label{width:42%}.bar-track{height:7px;background:#edf1f5;border-radius:5px}.bar-fill{height:7px;background:#0c66e4;border-radius:5px}.bar-count{width:42px;text-align:right;font-weight:bold}.status-legend{width:100%;border-collapse:collapse;font-size:11px}.status-legend td{padding:4px 3px}.legend-swatch{width:13px;height:9px;display:inline-block}.trend-panel{height:auto;margin-top:8px}.detail{border-collapse:separate;border-spacing:0;font-size:11px}.detail th{background:#f2f4f7;text-align:left}.detail th,.detail td{padding:7px;border-bottom:1px solid #e4e7ec}a{color:#0c66e4}"""
    styles = rich_styles
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{styles}</style></head><body><div class="report-canvas">
<table data-section="report-header" role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="#132f5f" style="width:100%;background:#132f5f;color:#ffffff;font-family:Arial,'Microsoft YaHei',sans-serif"><tr><td valign="middle" style="padding:25px 34px;color:#ffffff;font-family:Arial,'Microsoft YaHei',sans-serif"><div style="font-size:11px;line-height:16px;letter-spacing:2px;color:#d6e4fa">DAILY PROJECT INTELLIGENCE · {escape(config['project_name'].upper())}</div><div style="padding-top:8px;font-size:27px;line-height:34px;font-weight:bold;color:#ffffff">{escape(config['project_name'])} 公版状态日报</div><div style="padding-top:4px;font-size:12px;line-height:18px;color:#ffffff">{today.isoformat()}</div><div style="font-size:12px;line-height:18px;color:#d6e4fa">{escape(config['jql'])}</div></td><td width="150" align="right" valign="middle" style="width:150px;padding:25px 34px 25px 10px;color:#ffffff;font-family:Arial,'Microsoft YaHei',sans-serif"><div style="font-size:38px;line-height:42px;font-weight:bold;color:#ffffff">{len(issues)}</div><div style="font-size:12px;line-height:18px;color:#ffffff">当前未关闭</div></td></tr></table>
<div class="section"><div class="section-title">01 数据全景</div><table class="metric-table" role="presentation" width="100%"><tr>{metric_rows}</tr></table>
<table class="paired-row row-a" role="presentation" width="100%"><tr><td class="paired-cell" width="50%"><div class="panel"><h3>优先级/停滞 分布</h3><table class="bar-table" width="100%">{priority_rows}</table></div></td><td class="paired-cell" width="50%"><div class="panel"><h3>状态 分布</h3>{status_chart}</div></td></tr></table>
<table class="paired-row row-b" role="presentation" width="100%"><tr><td class="paired-cell" width="100%"><div class="panel"><h3>模块分布 · Top 5</h3><table class="bar-table" width="100%">{_bar_rows(modules.most_common(5))}</table></div></td></tr></table>
<div class="panel trend-panel"><h3>每日未关闭趋势 · 近 {config['trend_days']} 日未关闭趋势</h3>{trend_chart}<div class="muted">{trend_note}</div></div></div>
<div class="section"><div class="section-title">02 Issue 明细 · {sum(issue['priority'].casefold() in selected for issue in issues)} 条</div><div class="muted">展示优先级：{shown_priorities}</div><table class="detail" width="100%"><tr><th>Key</th><th>Summary</th><th>Status</th><th>Priority</th><th>Assignee</th><th>停滞</th></tr>{details}</table></div>
<div class="section"><div class="section-title">03 口径与附件</div><p>当前值为配置 JQL 返回的唯一 Issue 数，仅按查询条件排除状态。</p><p>今日创建/更新按本地日期；停滞为最后更新时间距今日至少 {config['stale_days']} 个日历日。本工作流生成 HTML 报告文件，不生成附件。</p></div>
</div></body></html>"""


def main(wf):
    with wf.step("n0", "读取并校验配置"):
        config = _validated_config(wf)
    today = date.today()
    with wf.step("n1", "查询当前 Jira Issue"):
        current = _search_issues(wf, config["jql"])
        created_today = _search_issues(
            wf, _metric_jql(config["jql"], "created >= startOfDay()")
        )
        updated_today = _search_issues(
            wf, _metric_jql(config["jql"], "updated >= startOfDay()")
        )
        stale_boundary = config["stale_days"] - 1
        stale = _search_issues(
            wf,
            _metric_jql(
                config["jql"], f"updated < startOfDay(-{stale_boundary}d)"
            ),
        )
        component_counts = _server_component_counts(wf, config["jql"], current)
    trend = [(today, len(current))]
    with wf.step("n2", "查询历史趋势"):
        for offset in range(1, config["trend_days"]):
            day = today - timedelta(days=offset)
            try:
                history = _search_issues(wf, _history_jql(day, config["jql"]))
            except Exception:
                trend.append((day, None))
            else:
                trend.append((day, len(history)))
    chronological_trend = list(reversed(trend))
    artifact = "a9-yocto-daily-report.html"
    with wf.step("n3", "生成并发布 HTML 日报"):
        statuses = Counter(issue["status"] or "未设置" for issue in current)
        segments = [
            {"label": label, "value": value}
            for label, value in statuses.most_common(6)
            if value > 0
        ] or [{"label": "暂无数据", "value": 1}]
        status_image = _chart_data_uri(
            wf, "chart_render_pie", {"segments": segments}
        )
        values = [value for _, value in chronological_trend if value is not None]
        trend_image = _chart_data_uri(
            wf,
            "chart_render_line",
            {"series": [{"label": "未关闭 Issue", "values": values}]},
        )
        report_html = _render_html(
            config,
            current,
            chronological_trend,
            today,
            status_image,
            trend_image,
            created_today_keys={issue["key"] for issue in created_today},
            updated_today_keys={issue["key"] for issue in updated_today},
            stale_keys={issue["key"] for issue in stale},
            component_counts=component_counts,
        )
        wf.write_file(artifact, report_html)
        wf.emit_artifact(artifact)
        wf.set_output("report_path", artifact)
        wf.set_output("total", len(current))
    if config["send_email"]:
        with wf.step("n4", "发送 HTML 日报"):
            arguments = {
                "recipients": ",".join(config["recipients"]),
                "subject": config["subject"],
                "file_path": artifact,
                "add_footer": False,
            }
            if config["cc"]:
                arguments["cc_addresses"] = ",".join(config["cc"])
            wf.call_tool("email_send_html", **arguments)
    return artifact
