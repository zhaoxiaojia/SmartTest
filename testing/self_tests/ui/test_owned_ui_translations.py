from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from subprocess import run

from PySide6.QtCore import QTranslator

from support.scripts import env


ROOT = Path(__file__).resolve().parents[3]

REQUIRED = {
    "AISettingsBridge": {
        "Company Intranet Kimi",
        "Public DeepSeek",
        "Unable to select the AI model. Try again.",
        "Enter an API key.",
        "Unable to save the API key. Check the key and try again.",
        "Unable to clear the API key. Try again.",
    },
    "T_Settings": {
        "AI Model Configuration",
        "Configured",
        "Not configured",
        "Enter API key",
        "Save",
        "Clear",
    },
}

JIRA_AUDIT_REQUIRED = {
    "JiraAuditBridge": {
        "Ready to review Jira issues.",
        "No AI review was required.",
        "Enter JQL or a Jira URL.",
        "Sign in with LDAP again to review Jira issues.",
        "Validating Jira input...",
        "Jira audit confirmed. Export is ready.",
        "Failed to export the Jira audit workbook.",
        "Jira audit workbook exported.",
        "The login changed. Start the Jira audit again.",
        "Reviewing ambiguous results with AI...",
        "Finalizing Jira audit results...",
        "Jira audit completed. Confirm the audit before exporting.",
        "Complete a Jira audit before confirming it.",
        "Confirm the Jira audit before exporting.",
        "AI review is unavailable. Character-rule results were retained.",
        "AI review completed.",
        "Jira input is invalid. Enter JQL or a Jira issue, filter, or search URL.",
        "Jira audit failed. Review the input and sign-in, then try again.",
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
        "AI Review",
        "Confirm Audit",
        "Export XLSX",
        "Show in Folder",
        "Exported file",
        "No export has been created.",
    },
}


def _catalog(path: Path) -> dict[str, dict[str, ET.Element]]:
    contexts = {}
    for context in ET.parse(path).getroot().findall("context"):
        contexts[context.findtext("name") or ""] = {
            message.findtext("source") or "": message.find("translation")
            for message in context.findall("message")
        }
    return contexts


def test_ai_settings_fixed_text_is_finished_in_both_catalogs():
    for filename in ("example_en_US.ts", "example_zh_CN.ts"):
        contexts = _catalog(ROOT / "ui/example" / filename)
        for context_name, sources in REQUIRED.items():
            assert context_name in contexts
            for source in sources:
                translation = contexts[context_name].get(source)
                assert translation is not None, f"{filename}: missing {context_name}/{source}"
                assert translation.get("type") != "unfinished"
                text = (translation.text or "").strip()
                assert text and "\ufffd" not in text and text not in {"?", "??", "???"}


def test_jira_audit_fixed_text_is_finished_in_both_catalogs():
    for filename in ("example_en_US.ts", "example_zh_CN.ts"):
        contexts = _catalog(ROOT / "ui/example" / filename)
        for context_name, sources in JIRA_AUDIT_REQUIRED.items():
            assert context_name in contexts
            for source in sources:
                translation = contexts[context_name].get(source)
                assert translation is not None, f"{filename}: missing {context_name}/{source}"
                assert translation.get("type") != "unfinished"
                assert translation.get("type") != "vanished"
                text = (translation.text or "").strip()
                assert text and "\ufffd" not in text and text not in {"?", "??", "???"}


def test_jira_audit_runtime_qm_translations_are_active_and_readable():
    for locale in ("en_US", "zh_CN"):
        translator = QTranslator()
        qm_path = ROOT / "ui/example/imports/example/i18n" / f"example_{locale}.qm"
        assert translator.load(str(qm_path)), f"failed to load {qm_path}"
        for context_name, sources in JIRA_AUDIT_REQUIRED.items():
            for source in sources:
                text = translator.translate(context_name, source).strip()
                assert text and "\ufffd" not in text and text not in {"?", "??", "???"}


def test_lupdate_keeps_ai_settings_bridge_text_active(tmp_path):
    generated_catalog = tmp_path / "example_en_US.ts"

    run(
        [
            env.pyside6_lupdate(),
            str(ROOT / "ui/example/imports/resource.qrc"),
            str(ROOT / "ui/example/bridge/AISettingsBridge.py"),
            str(ROOT / "ui/example/bridge/JiraAuditBridge.py"),
            "-ts",
            str(generated_catalog),
        ],
        check=True,
        cwd=ROOT,
    )

    bridge_messages = _catalog(generated_catalog)["AISettingsBridge"]
    for source in REQUIRED["AISettingsBridge"]:
        translation = bridge_messages.get(source)
        assert translation is not None, f"lupdate omitted {source}"
        assert translation.get("type") not in {"vanished", "obsolete"}

    jira_messages = _catalog(generated_catalog)["JiraAuditBridge"]
    for source in JIRA_AUDIT_REQUIRED["JiraAuditBridge"]:
        translation = jira_messages.get(source)
        assert translation is not None, f"lupdate omitted {source}"
        assert translation.get("type") not in {"vanished", "obsolete"}
