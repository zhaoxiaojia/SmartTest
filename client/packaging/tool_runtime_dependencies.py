from __future__ import annotations


PYWIN32_RUNTIME_MODULES = (
    "pythoncom",
    "pywintypes",
    "win32com",
    "win32com.client",
    "win32cred",
    "win32timezone",
)

TOOL_HIDDEN_IMPORTS = PYWIN32_RUNTIME_MODULES + (
    "atlassian",
    "atlassian.confluence",
    "ldap3",
    "FluentUI.FluentUI",
    "Crypto.Hash.MD4",
    "core.tools.common.project_weekly_audit.command",
    "core.tools.common.project_weekly_audit.scheduler",
)

TOOL_SMOKE_MODULES = (
    "openpyxl",
    "atlassian.confluence",
    "win32com.client",
    "win32cred",
    "win32timezone",
    "ldap3",
    "qrcode",
    "core.reporting.excel",
    "core.tools.common.project_weekly_audit.report",
    "core.tools.common.project_weekly_audit.command",
    "core.tools.common.project_weekly_audit.scheduler",
)
