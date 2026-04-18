class JiraError(RuntimeError):
    """Base class for Jira integration failures."""


class JiraRequestError(JiraError):
    """Raised when Jira REST returns a non-success response."""


class JiraConfigurationError(JiraError):
    """Raised when required client configuration is missing or invalid."""
