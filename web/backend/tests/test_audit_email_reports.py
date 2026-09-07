from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from core.confluence.audit import previous_business_week
from core.confluence.audit.models import AuditBatch, AuditFinding, AuditStatus, ProjectAudit
from core.confluence.audit.rules import UPDATE_MATRIX_POINTS
from core.confluence.project import Project, ProjectIdentity, ProductSpaceRef, ConfluencePageRef
from core.jira.audit import input as jira_input

from core.email.audit_report import render_history_report, summarize_audit
from core.jira.audit.models import AuditReport, IssueAuditResult, JiraAuditScope


def test_report_counts_issues_once_and_escapes_content_and_unsafe_links():
    issue = IssueAuditResult('SH-1', 'javascript:alert(1)', '', '<script>owner</script>', False, ())
    report = AuditReport(JiraAuditScope('jql', '', 'project="<SH>"'), datetime.now(), (), (issue, issue))
    summary = summarize_audit('jira', report)
    assert summary['total'] == 1 and summary['failed'] == 1
    rendered = render_history_report('jira', [{'id': 'run', 'label': 'today', 'summary': summary}], current=True)['html']
    assert '<script>' not in rendered
    assert 'javascript:' not in rendered
    assert '&lt;script&gt;owner&lt;/script&gt;' in rendered
    assert 'SH-1' in rendered


def test_zero_issue_report_has_no_invented_pass_rate():
    summary = summarize_audit('jira', AuditReport(JiraAuditScope('jql', '', 'project=SH'), datetime.now(), (), ()))
    assert summary['rate'] == '—'
    assert summary['total'] == 0


@pytest.mark.parametrize('now,start,end', [(datetime(2026, 9, 7), '2026-08-31', '2026-09-07'),
                                         (datetime(2027, 1, 4), '2026-12-28', '2027-01-04')])
def test_saved_created_bounds_roll_with_business_week_without_changing_other_conditions(now, start, end):
    period = previous_business_week(now.replace(tzinfo=ZoneInfo('Asia/Shanghai')))
    template = 'project in (SH, TV, IPTV, OTT,RK) AND issuetype in (Bug, Sub-bug) AND created >=2026-08-28 AND created <=2026-09-4 order by updated DESC'
    expected = f'project in (SH, TV, IPTV, OTT,RK) AND issuetype in (Bug, Sub-bug) AND created >="{start}" AND created <"{end}" order by updated DESC'
    assert jira_input.weekly_audit_jql(template, period) == expected


def test_jql_without_created_comparisons_is_unchanged_including_quoted_text():
    query = 'project=SH AND summary ~ "created >=2026-08-28" ORDER BY created DESC'
    assert jira_input.weekly_audit_jql(query, previous_business_week()) == query


def test_confluence_denominator_counts_all_actual_update_point_statuses_by_product_line():
    period = previous_business_week()
    project = Project(ProjectIdentity('1', 'P1'), 'Project', ProductSpaceRef('TV'), ConfluencePageRef('1'))
    states = [AuditStatus.UPDATED, AuditStatus.NOT_UPDATED, AuditStatus.INVALID_FORMAT, AuditStatus.FAILED,
              AuditStatus.UNKNOWN, AuditStatus.UPDATED, AuditStatus.NOT_UPDATED, AuditStatus.NOT_UPDATED]
    findings = tuple(AuditFinding('P1', 'Test', point.rule_id, status, '')
                     for point, status in zip(UPDATE_MATRIX_POINTS, states))
    findings += (AuditFinding('P1', 'Test', 'role.major_fae_qa', AuditStatus.UNKNOWN, ''),)
    summary = summarize_audit('confluence', AuditBatch('batch', period, datetime.now(), (ProjectAudit(project, findings),)))
    assert summary['TV'] == [2, 8]
    assert summary['DOPL'] == [0, 0]
    html = render_history_report('confluence', [{'id': 'run', 'label': 'today', 'summary': summary}], current=True)['html']
    assert '2 / 8' in html
    assert '待确认' not in html and '尚未确认' not in html
    # Old real runs retain their frozen body; new comparisons use their saved actual counts.
    summary['TV'][1] = None
    comparison = render_history_report('confluence', [{'id': 'old', 'label': 'old', 'summary': summary}])['html']
    assert '2 / 8' in comparison
