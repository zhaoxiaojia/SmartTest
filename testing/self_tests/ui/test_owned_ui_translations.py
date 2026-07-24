from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]

REQUIRED = {
    "ToolBridge": {
        "Jira Format Audit",
        "Review Jira issues against the FAE-QA format rules.",
    },
    "JiraAuditBridge": {
        "Ready to review Jira issues.",
        "Enter JQL or a Jira URL.",
        "Sign in with LDAP again to review Jira issues.",
        "Validating Jira input...",
        "Fetching Jira issues...",
        "Reviewing Jira issue formats...",
        "Jira format audit completed.",
        "Complete a Jira audit before exporting.",
        "Failed to export the Jira audit workbook.",
        "Jira audit workbook exported.",
        "The login changed. Start the Jira audit again.",
        "The Jira audit returned an invalid result.",
        "Jira audit failed.",
        "Jira URLs must use HTTP or HTTPS.",
        "The Jira URL is malformed.",
        "The Jira URL host must match the configured Jira host.",
        "The Jira issue URL contains an invalid issue key.",
        "Use a Jira issue, filter, or search URL.",
        "The Jira filter could not be loaded. Check its permissions.",
        "The Jira filter does not contain JQL.",
        "JQL validation failed. Check the query and Jira permissions.",
    },
    "JiraAuditWorkspace": {
        "JQL or Jira URL",
        "Paste JQL or a Jira issue, filter, or search URL.",
        "Start Audit",
        "Rules",
        "Audit Progress",
        "Results",
        "Total",
        "Passed",
        "Failed",
        "Violations",
        "No violations were found.",
        "Export XLSX",
        "Show in Folder",
        "Exported file",
        "No export has been created.",
    },
}


def _catalog(path: Path) -> dict[str, dict[str, ET.Element]]:
    contexts = {}
    for context in ET.parse(path).getroot().findall("context"):
        name = context.findtext("name") or ""
        contexts[name] = {
            message.findtext("source") or "": message.find("translation")
            for message in context.findall("message")
        }
    return contexts


def test_jira_audit_fixed_text_is_finished_in_both_catalogs():
    for filename in ("example_en_US.ts", "example_zh_CN.ts"):
        contexts = _catalog(ROOT / "ui/example" / filename)
        for context_name, sources in REQUIRED.items():
            assert context_name in contexts
            for source in sources:
                translation = contexts[context_name].get(source)
                assert translation is not None, f"{filename}: missing {context_name}/{source}"
                assert translation.get("type") != "unfinished"
                text = (translation.text or "").strip()
                assert text
                assert "\ufffd" not in text
                assert text not in {"?", "??", "???"}
