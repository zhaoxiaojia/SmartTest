class BrowserAutomationError(RuntimeError):
    """Safe browser automation boundary error."""


class SupportedBrowserNotInstalledError(BrowserAutomationError):
    """Neither Google Chrome nor Microsoft Edge is installed."""
