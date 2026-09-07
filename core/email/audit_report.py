"""Weekly audit email bodies; delivery stays with the existing Outlook owner."""

from html import escape

from core.confluence.project_discovery import PRODUCT_LINES
from core.confluence.audit.rules import UPDATE_MATRIX_POINTS


def summarize_audit(kind, report):
    if kind == 'jira':
        issues = {issue.key: issue for issue in report.issues}
        passed = sum(issue.passed for issue in issues.values())
        return {'total': len(issues), 'passed': passed, 'failed': len(issues) - passed,
                'rate': f'{passed / len(issues) * 100:.2f}%' if issues else '—',
                'issues': [{'key': issue.key, 'url': issue.url, 'creator': issue.creator,
                            'passed': issue.passed} for issue in issues.values()],
                'scope': report.resolved.jql}
    points = {point.rule_id for point in UPDATE_MATRIX_POINTS}
    result = {line.key: [0, 0] for line in PRODUCT_LINES}
    counts = {line.key: {status: 0 for status in ('updated', 'not_updated', 'invalid_format', 'failed', 'unknown')}
              for line in PRODUCT_LINES}
    for audit in report.projects:
        for finding in audit.findings:
            if finding.rule_id in points:
                counts[audit.project.product_space.key][finding.status.value] += 1
    for key, values in counts.items():
        result[key] = [values['updated'], sum(values.values())]
    result['counts'] = counts
    result['scope'] = f'{report.period.start.isoformat()} ≤ 更新时间 < {report.period.end.isoformat()}'
    return result


def render_history_report(kind: str, records: list[dict], *, current=False) -> dict:
    """Render only supplied, dated summaries; never promote previews to audits."""
    records = records[:4]
    if not records:
        return {"state": "unavailable", "html": "", "sourceIds": []}
    title = ("FAE QA JIRA描写不符合规范反馈" if kind == "jira"
             else "Confluence信息更新检查结果")
    labels = [row['label'] for row in records]
    if kind == "jira":
        rows = [(label, [row['summary'][key] for row in records]) for label, key in (
            ("问题总数", "total"), ("通过 Jira 数", "passed"),
            ("不通过 Jira 数", "failed"), ("通过率", "rate"),
        )]
        note = "Jira 年份未确认，保留截图月日标签。历史违规人员、Jira 明细及附件未提供。"
    else:
        rows = [(line.display_name, [
            f"{row['summary'][line.key][0]} / "
            f"{sum(row['summary']['counts'][line.key].values()) if 'counts' in row['summary'] else row['summary'][line.key][1]}"
            for row in records
        ]) for line in PRODUCT_LINES]
        note = "表内为截图原值：已更新点 / 需要更新点。历史明细及附件未提供。"
    border = "border:1px solid #bcc9da;padding:10px;text-align:left;"
    table = '<table style="border-collapse:collapse;width:100%;font-size:14px"><thead><tr>'
    table += f'<th scope="col" style="{border}background:#dbeafe">指标 / 产品线</th>'
    for index, label in enumerate(labels):
        color = '#fff2cc' if index == 0 else '#dbeafe'
        table += f'<th scope="col" style="{border}background:{color}">{escape(label)}</th>'
    table += '</tr></thead><tbody>'
    for label, values in rows:
        table += f'<tr><th scope="row" style="{border}">{escape(label)}</th>'
        for index, value in enumerate(values):
            color = '#fff2cc' if index == 0 else '#ffffff'
            table += f'<td style="{border}background:{color}">{escape(str(value))}</td>'
        table += '</tr>'
    table += '</tbody></table>'
    details = ''
    if current:
        summary = records[0]['summary']
        note = f"实际审查范围：{summary['scope']}。旧期列为已保存历史，截图未提供历史明细或附件。"
        if kind == 'jira':
            from urllib.parse import urlsplit
            groups = {}
            for issue in summary['issues']:
                if not issue['passed']:
                    groups.setdefault(issue['creator'] or '未知创建人', []).append(issue)
            details = '<h3>当期违规 Jira</h3><table style="border-collapse:collapse;width:100%"><tr>'
            details += ''.join(f'<th style="{border}background:#dbeafe">{label}</th>' for label in ('创建人', '违规 Jira 数量', '违规 Jira 号')) + '</tr>'
            for creator, issues in sorted(groups.items()):
                links = []
                for issue in issues:
                    key, url = escape(issue['key']), issue['url']
                    links.append(f'<a href="{escape(url, quote=True)}">{key}</a>' if urlsplit(url).scheme in {'http', 'https'} else key)
                details += f'<tr><td style="{border}">{escape(creator)}</td><td style="{border}">{len(issues)}</td><td style="{border}">{", ".join(links)}</td></tr>'
            details += '</table>' if groups else '</table><p>本次无违规 Jira。</p>'
        else:
            note += ' 需要更新点为实际受审查的更新点总数，包含已更新、未更新、格式有误、失败和未知。'
            details = '<h3>当期实际状态计数</h3><table style="border-collapse:collapse;width:100%"><tr>'
            details += ''.join(f'<th style="{border}background:#dbeafe">{label}</th>' for label in ('产品线', '已更新', '未更新', '格式有误', '失败', '未知')) + '</tr>'
            for line in PRODUCT_LINES:
                values = summary['counts'][line.key]
                details += '<tr>' + ''.join(f'<td style="{border}">{escape(str(value))}</td>' for value in [line.display_name, *values.values()]) + '</tr>'
            details += '</table>'
    subject = f'{title} {labels[0]}' + ('' if current else '（历史预览）')
    introduction = ('本次已执行审查，报告已保存。' if current else
                    '历史预览：以下数据来自已提供的截图汇总，本次未重新执行审查，未发送邮件。')
    body = (
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
        '<body style="font-family:Arial,Microsoft YaHei,sans-serif;color:#172b4d;background:white;padding:20px">'
        f'<h2>{escape(subject)}</h2><p>Hi all,</p>'
        f'<p>{introduction}</p>{table}<p>{escape(note)}</p>{details}</body></html>'
    )
    return {"state": "completed" if current else "historical_preview", "subject": subject, "html": body,
            "sourceIds": [row['id'] for row in records]}
