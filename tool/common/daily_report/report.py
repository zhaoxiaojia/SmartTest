"""Render the fixed four-project Daily Report artifacts."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from html import escape
import math
from pathlib import Path

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties

from support.report import LineSeries, render_line_chart, write_xlsx_table
from support.report.image.line import _cjk_font_family
from .analyzer import analyze_daily_report
from .models import DailyReportAnalysis, DailyReportIssue

PROJECT_NAME = "BDS IFPD"
JQL = "status not in (Closed, Done, Verified) AND labels = BDS_IFPD"
YOCTO_DEBIAN_TO = (
    "Daozai.Ye@amlogic.com", "rongqi.wang@amlogic.com",
    "kang.jiang@amlogic.com", "subing.xu@amlogic.com",
    "chen.chen@amlogic.com",
)
COMMON_CC = (
    "gordon.pan@amlogic.com", "xiuyue.zhang@amlogic.com",
    "ping.xiong@amlogic.com", "Fred.chen@amlogic.com",
)
ISSUE_FIELDS = (
    "key",
    "summary",
    "status",
    "assignee",
    "priority",
    "labels",
    "components",
    "created",
    "updated",
)


@dataclass(frozen=True)
class ProjectConfig:
    safe_id: str
    name: str
    label: str
    jql: str
    to: tuple[str, ...]
    cc: tuple[str, ...]
    enabled: bool = True
    subject: str = ""

    def __post_init__(self):
        if not self.subject.strip():
            object.__setattr__(self, "subject", f"[{self.name}] 公版状态日报")


PROJECTS = (
    ProjectConfig(
        "a9-yocto",
        "A9 Yocto",
        "Linux-A9_Yocto",
        "status not in (Closed, Done, Verified) AND labels = Linux-A9_Yocto",
        YOCTO_DEBIAN_TO,
        COMMON_CC,
    ),
    ProjectConfig(
        "a9-debian",
        "A9 Debian",
        "Linux-A9_Armbian",
        "status not in (Closed, Done, Verified) AND labels = Linux-A9_Armbian",
        YOCTO_DEBIAN_TO,
        COMMON_CC,
    ),
    ProjectConfig(
        "a9-android16-ifpd",
        "A9 Android 16 IFPD",
        "BDS_IFPD",
        "status not in (Closed, Done, Verified) AND labels = BDS_IFPD",
        (
            "Daozai.Ye@amlogic.com", "subing.xu@amlogic.com",
            "weiting.feng@amlogic.com", "xin.wang@amlogic.com",
            "qiang.zhang@amlogic.com", "zhengshuai.zhu@amlogic.com",
            "yong.su@amlogic.com", "chen.chen@amlogic.com",
        ),
        COMMON_CC,
    ),
    ProjectConfig(
        "a9-gaming-box",
        "A9 Gaming Box",
        "BDS_Gaming_Box",
        "status not in (Closed, Done, Verified) AND labels = BDS_Gaming_Box",
        (
            "junjie.li@amlogic.com", "chenghua.liu@amlogic.com",
            "terence.shen@amlogic.com", "hengzhou.xie@amlogic.com",
            "peng.shi@amlogic.com", "chen.chen@amlogic.com",
        ),
        (
            "gordon.pan@amlogic.com", "xiuyue.zhang@amlogic.com",
            "zhiheng.cao@amlogic.com", "fred.chen@amlogic.com",
            "daozai.ye@amlogic.com", "ping.xiong@amlogic.com",
        ),
    ),
)


@dataclass(frozen=True)
class DailyReportArtifacts:
    html_path: Path
    chart_path: Path
    status_chart_path: Path
    excel_path: Path


def build_historical_jql(day: date, label: str = "BDS_IFPD") -> str:
    return f'status WAS NOT IN (Closed, Done, Verified) ON "{day.isoformat()}" AND labels = {label}'


def _named(value) -> str:
    if isinstance(value, dict):
        return str(
            value.get("displayName") or value.get("name") or value.get("value") or ""
        )
    return "" if value is None else str(value)


def _names(value) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, dict)):
        value = (value,)
    return tuple(name for item in value if (name := _named(item)))


def _datetime(value) -> datetime | None:
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


def records_to_issues(
    records, jira_base_url: str = "https://jira.amlogic.com"
) -> tuple[DailyReportIssue, ...]:
    issues = {}
    for record in records:
        fields = record.fields
        key = str(record.key)
        issues[key] = DailyReportIssue(
            key,
            _named(fields.get("summary")),
            _named(fields.get("status")),
            _named(fields.get("assignee")),
            _named(fields.get("priority")),
            _names(fields.get("components")),
            _names(fields.get("labels")),
            _datetime(fields.get("created")),
            _datetime(fields.get("updated")),
            f"{jira_base_url.rstrip('/')}/browse/{key}",
        )
    return tuple(issues.values())


def _compact_values(values, limit=5):
    values = list(values)
    head = values[:limit]
    remainder = sum(count for _, count in values[limit:])
    return head + ([("其他", remainder)] if remainder else [])


def _bar_panel(title: str, values, *, compact=False) -> str:
    values = _compact_values(values) if compact else list(values)
    maximum = max((count for _, count in values), default=0)
    rows = "".join(
        f'<tr><td class="bar-label">{escape(name or "未设置")}</td><td><div class="bar-track"><div class="bar-fill" style="width:{round(count * 100 / maximum) if maximum else 0}%"></div></div></td><td class="bar-count">{count}</td></tr>'
        for name, count in values
    )
    return f'<div class="panel compact-panel"><h3>{escape(title)}</h3><table class="bar-table" width="100%">{rows or "<tr><td>—</td></tr>"}</table></div>'


def render_status_composition(values, output_path: Path) -> Path:
    figure = Figure(figsize=(7.0, 4.0), dpi=180, facecolor="white")
    canvas = FigureCanvasAgg(figure)
    axis = figure.add_axes((0.01, 0.02, 0.62, 0.96))
    labels = [name or "未设置" for name, _ in values]
    counts = [count for _, count in values]
    colors = ("#0c66e4", "#36b37e", "#ffab00", "#6554c0", "#de350b", "#6b778c")
    if counts:
        wedges, _ = axis.pie(
            counts,
            radius=1.2,
            startangle=90,
            colors=colors[: len(counts)],
            wedgeprops={"width": 0.34, "edgecolor": "white"},
        )
        family = _cjk_font_family()
        figure.legend(
            wedges,
            [f"{label}  {count}" for label, count in zip(labels, counts)],
            loc="center left",
            bbox_to_anchor=(0.63, 0.5),
            frameon=False,
            prop=FontProperties(family=family, size=11) if family else FontProperties(size=11),
            handlelength=1.8,
            handleheight=1.2,
            labelspacing=0.9,
        )
        axis.text(
            0,
            0,
            str(sum(counts)),
            ha="center",
            va="center",
            fontsize=22,
            fontweight="bold",
            color="#172b4d",
        )
    else:
        axis.text(0.5, 0.5, "—", ha="center", va="center", transform=axis.transAxes)
    axis.set_aspect("equal")
    axis.axis("off")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.print_png(output_path)
    return output_path


def _metric(label: str, value, note: str = "") -> str:
    shown = "—" if value is None else str(value)
    return f'<td width="20%" style="padding:6px"><div class="metric-card" style="height:118px;padding:18px 15px;box-sizing:border-box"><div class="metric-label" style="font-size:14px;line-height:20px;color:#59636e">{escape(label)}</div><div class="metric-value" style="font-size:34px;line-height:38px;font-weight:bold;margin:7px 0">{escape(shown)}</div><div class="metric-note" style="font-size:13px;line-height:18px;color:#667085">{escape(note)}</div></div></td>'


def build_intelligence_html(
    analysis: DailyReportAnalysis,
    trend,
    chart_path: Path,
    status_chart_path: Path,
    *,
    project_name=PROJECT_NAME,
    jql=JQL,
    current_keys=None,
    previous_keys=None,
) -> str:
    p0 = sum(issue.priority.casefold() == "p0" for issue in analysis.issues)
    p1 = sum(issue.priority.casefold() == "p1" for issue in analysis.issues)
    yesterday = next(
        (value for day, value in reversed(trend[:-1]) if value is not None), None
    )
    delta = analysis.total - yesterday if yesterday is not None else None
    delta_text = "" if delta is None else f"{delta:+d} vs 昨日"
    metrics = (
        ("当前未关闭", analysis.total, "当前 JQL"),
        ("今日创建", len(analysis.created_today), "本地日期"),
        ("今日更新", len(analysis.updated_today), "本地日期"),
        ("P0 / 高优先级", p0, "需优先关注"),
        ("停滞 ≥ 7 天", len(analysis.stale), "最后更新时间"),
    )
    metric_rows = f"<tr>{''.join(_metric(*item) for item in metrics)}</tr>"
    status = Counter(
        issue.status or "未设置" for issue in analysis.issues
    ).most_common()
    modules = Counter(
        component
        for issue in analysis.issues
        for component in (issue.components or ("未设置",))
    ).most_common()
    priorities = Counter(
        issue.priority or "未设置" for issue in analysis.issues
    ).most_common()
    detail_rows = "".join(
        f'<tr class="issue-row"><td><a href="{escape(issue.url, quote=True)}">{escape(issue.key)}</a></td><td>{escape(issue.summary or "未设置")}</td><td>{escape(issue.status or "未设置")}</td><td>{escape(issue.priority or "未设置")}</td><td>{escape(issue.assignee or "未设置")}</td><td>{"是" if issue.key in analysis.stale else "否"}</td></tr>'
        for issue in analysis.issues
    )
    if yesterday is None:
        yesterday_content = '<div class="muted">暂无可用历史基线</div>'
    else:
        rows = [("昨日未关闭", yesterday), ("净变化", f"{delta:+d} vs 昨日")]
        if current_keys is not None and previous_keys is not None:
            rows.extend((("进入当前集合", len(set(current_keys) - set(previous_keys))), ("离开当前集合", len(set(previous_keys) - set(current_keys)))))
        yesterday_content = '<table class="bar-table" width="100%">' + "".join(f'<tr><td>{label}</td><td class="bar-count nowrap">{value}</td></tr>' for label, value in rows) + "</table>"
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;background:#eef1f5;font-family:Arial,'Microsoft YaHei',sans-serif;color:#172b4d}} .report-canvas{{width:860px;max-width:calc(100% - 32px);margin:24px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 8px 28px rgba(9,30,66,.10)}} .hero{{padding:28px 34px;background:#102a56;background:linear-gradient(135deg,#102a56,#0c66e4);color:#fff}} .eyebrow{{font-size:11px;letter-spacing:2px;opacity:.78}} .hero-title{{font-size:27px;font-weight:bold;margin:8px 0 4px}} .hero-subtitle{{font-size:12px;opacity:.78}} .hero-total{{font-size:38px;font-weight:bold;line-height:1}} .section{{padding:24px 28px;border-bottom:1px solid #e4e7ec}} .section-title{{font-size:18px;font-weight:bold;margin-bottom:14px}} .metric-card,.panel{{background:#fff;border:1px solid #dfe3e8;border-radius:10px;padding:13px}} .metric-card{{height:92px;box-sizing:border-box;vertical-align:middle}} .metric-label,.metric-note,.muted{{font-size:12px;line-height:1.35;color:#667085}} .metric-value{{font-size:30px;line-height:1;font-weight:bold;margin:8px 0}} .paired-row{{table-layout:fixed;border-spacing:6px}} .paired-cell{{vertical-align:top}} .paired-cell>.panel{{height:220px;box-sizing:border-box;margin:0}} .row-b .paired-cell>.panel{{height:225px}} .compact-panel{{overflow:hidden}} .bar-table{{border-collapse:collapse;font-size:11px}} .bar-table td{{padding:6px 3px}} .bar-label{{width:42%;white-space:nowrap;overflow:hidden}} .bar-track{{height:7px;background:#edf1f5;border-radius:5px}} .bar-fill{{height:7px;background:#0c66e4;border-radius:5px}} .bar-count{{width:90px;text-align:right;font-weight:bold}} .nowrap{{white-space:nowrap}} .status-img{{display:block;width:100%;height:165px;object-fit:contain}} .detail{{border-collapse:separate;border-spacing:0;font-size:11px}} .detail th{{background:#f2f4f7;text-align:left}} .detail th,.detail td{{padding:7px;border-bottom:1px solid #e4e7ec}} h3{{margin:0 0 8px;font-size:14px}} a{{color:#0c66e4}}
.row-a .paired-cell>.panel{{height:300px}}.status-img{{height:245px}}
</style></head><body><div class="report-canvas">
<div class="hero"><div class="eyebrow">DAILY PROJECT INTELLIGENCE · {escape(project_name.upper())}</div><table role="presentation" width="100%" cellspacing="0"><tr><td><div class="hero-title">{escape(project_name)} 公版状态日报</div><div>{analysis.day.isoformat()}</div><div class="hero-subtitle">{escape(jql)}</div></td><td width="150" align="right"><div class="hero-total">{analysis.total}</div><div>当前未关闭</div>{f'<div class="nowrap">{delta_text}</div>' if delta_text else ''}</td></tr></table></div>
<div class="section"><div class="section-title">01 数据全景</div><table class="kpi-row" role="presentation" width="100%" cellspacing="5">{metric_rows}</table><table class="paired-row row-a" role="presentation" width="100%" cellspacing="6"><tr><td class="paired-cell" width="50%"><div class="panel"><h3>昨日对比</h3>{yesterday_content}</div></td><td class="paired-cell" width="50%"><div class="panel"><h3>状态构成</h3><img class="status-img" src="{escape(status_chart_path.name)}"></div></td></tr></table><table class="paired-row row-b" role="presentation" width="100%" cellspacing="6"><tr><td class="paired-cell" width="50%">{_bar_panel('模块分布 · Top 5', modules, compact=True)}</td><td class="paired-cell" width="50%">{_bar_panel('优先级 / 停滞', [('P0', p0), ('P1', p1), ('P2', dict(priorities).get('P2', 0)), ('停滞 ≥ 7 天', len(analysis.stale))])}</td></tr></table><div class="panel" style="margin-top:8px"><h3>每日未关闭趋势</h3><img src="{escape(chart_path.name)}" style="display:block;width:100%;max-height:360px;object-fit:contain"><div class="muted">缺失日期以断点表示，不进行推测或插值。</div></div></div>
<div class="section"><div class="section-title">02 Issue 明细 · {len(analysis.issues)} 条</div><div class="muted" style="margin-bottom:10px">当前 JQL 返回的全部唯一 Issue</div><table class="detail" width="100%" cellspacing="0" cellpadding="0"><tr><th>Key</th><th>Summary</th><th>Status</th><th>Priority</th><th>Assignee</th><th>停滞</th></tr>{detail_rows or '<tr><td colspan="6">当前无 Issue</td></tr>'}</table></div>
<div class="section"><div class="section-title">03 口径与附件</div><p>当前值为固定 JQL 返回的唯一 Issue 数，包含 Resolved，仅排除 Closed、Done、Verified。</p><p>今日创建/更新按本地日期；停滞为最后更新时间距今日至少 7 个日历日。附件包含完整 Issue Excel。</p></div>
</div></body></html>"""


def generate_artifacts(
    issues, trend, output_dir: Path, day: date, *, project: ProjectConfig,
    previous_keys=None,
) -> DailyReportArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    analysis = analyze_daily_report(tuple(issues), day=day, previous=None)
    chart_path = output_dir / "unclosed-trend.png"
    render_line_chart(
        tuple(item_day.strftime("%m-%d") for item_day, _ in trend),
        (
            LineSeries(
                "未关闭 Issue",
                tuple(
                    float(total) if total is not None else math.nan
                    for _, total in trend
                ),
                fill=False,
            ),
        ),
        chart_path,
        title="近 14 日未关闭 Issue 趋势",
        highlight_series="未关闭 Issue",
    )
    status_chart_path = output_dir / "status-composition.png"
    render_status_composition(
        Counter(issue.status or "未设置" for issue in issues).most_common(6),
        status_chart_path,
    )
    excel_path = output_dir / "issues.xlsx"
    headers = (
        "Key",
        "Summary",
        "Status",
        "Assignee",
        "Priority",
        "Components",
        "Labels",
        "Created",
        "Updated",
        "URL",
    )
    rows = tuple(
        (
            issue.key,
            issue.summary,
            issue.status,
            issue.assignee,
            issue.priority,
            ", ".join(issue.components),
            ", ".join(issue.labels),
            issue.created.isoformat() if issue.created else "",
            issue.updated.isoformat() if issue.updated else "",
            issue.url,
        )
        for issue in issues
    )
    write_xlsx_table(
        excel_path,
        sheet_name="Issues",
        headers=headers,
        rows=rows,
        hyperlinks={
            (index + 2, 1): issue.url for index, issue in enumerate(issues) if issue.url
        },
    )
    html_path = output_dir / "daily-project-intelligence.html"
    html_path.write_text(
        build_intelligence_html(
            analysis,
            trend,
            chart_path,
            status_chart_path,
            project_name=project.name,
            jql=project.jql,
            current_keys={issue.key for issue in issues},
            previous_keys=previous_keys,
        ),
        encoding="utf-8",
    )
    return DailyReportArtifacts(
        html_path, chart_path, status_chart_path, excel_path
    )
