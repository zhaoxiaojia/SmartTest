from __future__ import annotations

from pathlib import Path
import hashlib
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
        "Global (DUT / Environment)",
        "Special Params (by Case Type)",
    },
    "T_Run": {
        "Run",
        "Run Tests",
        "Start",
        "Stop",
        "Execution output and progress will appear here.",
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
        "Suggested Queries",
        "AI Conversation",
        "Structured Results",
        "Selected Issue",
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
