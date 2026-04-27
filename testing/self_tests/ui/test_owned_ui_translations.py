from __future__ import annotations

from pathlib import Path
import hashlib
import re
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[3]
UI_DIR = ROOT / "ui" / "example"
QRC_I18N_DIR = UI_DIR / "imports" / "example" / "i18n"

TRANSLATION_FILES = {
    "en_US": UI_DIR / "example_en_US.ts",
    "zh_CN": UI_DIR / "example_zh_CN.ts",
}

REQUIRED_TRANSLATIONS = {
    "ItemsFooter": {
        "Account",
        "Settings",
    },
    "ItemsOriginal": {
        "Home",
        "Test",
        "Run",
        "Report",
        "Debug",
        "Jira",
    },
    "LoginWindow": {
        "Account",
        "Login",
        "Logout",
        "Signed in as %1",
        "LDAP Server: %1",
        "Please enter the account",
        "Please enter your password",
        "Signed out",
    },
    "T_TestConfig": {
        "Test",
        "Global",
        "Shared by Case Type",
        "Per Case",
        "Test Cases",
        "Filter by file...",
        "Selected (%1)",
        "Case Parameters (%1)",
        "Select one or more test files to inspect the required parameters for each case.",
        "No configurable parameters are required for this case.",
        "Enabled",
        "Disabled",
        "DUT",
    },
    "T_Run": {
        "Run",
        "Start",
        "Stop",
        "Steps",
        "Logs",
    },
    "RunBridge": {
        "No selected test cases to run.",
        "Failed to start pytest run. {detail}",
    },
    "T_Report": {
        "Report",
        "Reports",
        "Browse historical runs and export reports.",
    },
    "T_Debug": {
        "Debug",
        "Debug Tools",
        "Diagnostics, logs, and utilities go here.",
    },
    "T_Jira": {
        "Jira",
        "Jira AI Workspace",
        "Connection",
        "Search Scope",
        "Common Jira Filters",
        "Projects",
        "Workflow Preset",
        "Time Window",
        "Statuses",
        "Priorities",
        "Issue Types",
        "Keyword text",
        "Assignee",
        "Reporter",
        "Labels",
        "No options in current result set",
        "Not limited",
        "JQL Filter",
        "Paste a Jira filter, for example: project = TV ORDER BY created DESC",
        "When this field is filled, SmartTest uses this JQL directly and skips the common Jira filters below.",
        "My Filters",
        "Loading your Jira filters...",
        "No favourite filters were found for this account.",
        "Click to apply this filter to the current JQL box.",
        "Suggested Queries",
        "AI Conversation",
        "Structured Results",
        "Selected Issue",
        "Click to collapse",
        "Click to expand",
        "Bug Status",
        "Type",
        "Priority",
        "Status",
        "Resolution",
        "Description",
        "Comments",
        "No comments yet.",
        "AI Summary",
        "Suggested Next Actions",
    },
    "AuthBridge": {
        "Account or password cannot be empty.",
        "ldap3 is not installed in the current Python environment.",
        "LDAP sign-in failed. {detail}",
        "LDAP sign-in failed. Please check your account or password.",
        "Sign-in successful. Welcome, {username}",
    },
    "TestPageBridge": {
        "DUT",
    },
    "JiraBridge": {
        "Ready",
        "Run a Jira query to get a live AI summary.",
        "Signed-in Jira access is ready. Ask in natural language to search issues and summarize risk.",
        "Workspace ready",
        "Session cleared. Ask a new Jira question when ready.",
        "Reset",
        "Jira request failed. Check the connection message above and sign in again if needed.",
        "Error",
        "All Supported Projects",
        "Open Work",
        "Ready for Test",
        "Closed Bugs",
        "Last 7 Days",
        "Last 30 Days",
        "Last 90 Days",
        "This Year",
        "Open",
        "In Progress",
        "Verified",
        "Resolved",
        "Closed",
        "Highest",
        "Critical",
        "High",
        "Medium",
        "Low",
        "Bug",
        "Task",
        "Story",
        "Improvement",
        "Unassigned",
        "LDAP session is missing Jira credentials. Please sign in again.",
        "Connected to {base_url} | loaded {loaded} of {total}",
        "Loaded {loaded} of {total} issues for browsing. Select an issue or ask a question for deeper analysis.",
        "Connected to {base_url} | analyzed {returned} of {total}",
        "Just now",
        "Sign in to load Jira data.",
        "Sign in with LDAP first, then Jira results and AI analysis will load here.",
        "Loading Jira results...",
        "Analyzing Jira request...",
        "Sign in again to restore Jira access.",
        "Signed out",
        "Unknown Jira error",
        "Jira request failed: {message}",
        "Matched",
        "{displayed} displayed in the current view",
        "High Priority",
        "Highest, critical, or high in the current result set",
        "Blocked",
        "Blocked items from the displayed Jira scope",
        "Projects",
        "Workflow Preset",
        "Time Window",
        "Statuses",
        "Priorities",
        "Issue Types",
        "Keyword text",
        "Assignee",
        "Reporter",
        "Labels",
        "Not limited",
        "Current user",
        "JQL",
        "My Filters",
        "Loading your Jira filters...",
        "No favourite filters were found for this account.",
        "Click to apply this filter to the current JQL box.",
        "Useful candidates for the next regression batch",
        "Comments",
        "No Jira issues matched the current scope.",
        "{total} Jira issues matched the current scope. Top issue: {key} ({status}, {priority}) - {summary}",
    },
}


def _load_translations(ts_path: Path) -> dict[str, dict[str, tuple[str, str | None]]]:
    tree = ET.parse(ts_path)
    root = tree.getroot()
    payload: dict[str, dict[str, tuple[str, str | None]]] = {}
    for context in root.findall("context"):
        name_node = context.find("name")
        if name_node is None or not name_node.text:
            continue
        context_name = name_node.text.strip()
        context_messages: dict[str, tuple[str, str | None]] = {}
        for message in context.findall("message"):
            source_node = message.find("source")
            translation_node = message.find("translation")
            if source_node is None or translation_node is None or source_node.text is None:
                continue
            source_text = source_node.text
            if message.get("type") == "obsolete" or translation_node.get("type") == "obsolete":
                continue
            translation_text = "".join(translation_node.itertext()).strip()
            context_messages[source_text] = (translation_text, translation_node.get("type"))
        payload[context_name] = context_messages
    return payload


def _looks_like_mojibake(text: str) -> bool:
    if not text:
        return False
    if any("\u4e00" <= ch <= "\u9fff" for ch in text):
        return False
    try:
        repaired = text.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return False
    return any("\u4e00" <= ch <= "\u9fff" for ch in repaired)


def test_owned_ui_translations_are_complete() -> None:
    missing: list[str] = []

    for locale, ts_path in TRANSLATION_FILES.items():
        translations = _load_translations(ts_path)
        for context_name, sources in REQUIRED_TRANSLATIONS.items():
            context_messages = translations.get(context_name, {})
            for source_text in sorted(sources):
                translation_text, translation_type = context_messages.get(source_text, ("", None))
                if not translation_text:
                    missing.append(f"{locale}: missing translation text for {context_name} -> {source_text}")
                    continue
                if translation_type == "unfinished":
                    missing.append(f"{locale}: unfinished translation for {context_name} -> {source_text}")
                    continue
                if locale == "zh_CN":
                    normalized_text = re.sub(r"%\d+|%n|\{[^}]+\}", "", translation_text).strip()
                    if "?" in normalized_text or "？" in normalized_text:
                        missing.append(f"{locale}: suspicious placeholder translation for {context_name} -> {source_text}: {translation_text}")
                        continue
                    if _looks_like_mojibake(translation_text):
                        missing.append(f"{locale}: mojibake translation for {context_name} -> {source_text}: {translation_text}")

    assert not missing, "Owned UI translation audit failed:\n" + "\n".join(missing)


def test_qrc_translation_payloads_match_generated_qm_files() -> None:
    mismatches: list[str] = []
    for locale in TRANSLATION_FILES:
        generated = UI_DIR / f"example_{locale}.qm"
        packaged = QRC_I18N_DIR / f"example_{locale}.qm"
        generated_hash = hashlib.sha256(generated.read_bytes()).hexdigest()
        packaged_hash = hashlib.sha256(packaged.read_bytes()).hexdigest()
        if generated_hash != packaged_hash:
            mismatches.append(
                f"{locale}: generated qm ({generated}) does not match packaged qm ({packaged})"
            )

    assert not mismatches, "QRC translation payloads are out of sync:\n" + "\n".join(mismatches)


def test_runtime_qrc_translations_are_readable() -> None:
    import sys
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine

    sys.path.insert(0, str(ROOT / "ui"))
    from example.imports import resource_rc  # noqa: F401
    from example.helper.TranslateHelper import TranslateHelper

    app = QGuiApplication.instance() or QGuiApplication([])
    engine = QQmlApplicationEngine()
    helper = TranslateHelper()
    helper.init(engine)
    helper.current = "zh_CN"

    expected = {
        ("T_Jira", "Common Jira Filters"): "常用 Jira 过滤条件",
        ("T_Jira", "My Filters"): "我的过滤器",
        ("JiraBridge", "Open"): "打开",
        ("JiraBridge", "Bug"): "缺陷",
    }
    failures: list[str] = []
    for (context_name, source_text), expected_text in expected.items():
        actual = QCoreApplication.translate(context_name, source_text)
        if actual != expected_text:
            failures.append(f"{context_name} -> {source_text}: expected {expected_text}, got {actual}")

    assert not failures, "Runtime QRC translation audit failed:\n" + "\n".join(failures)
