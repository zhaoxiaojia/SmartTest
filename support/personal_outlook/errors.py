class PersonalOutlookError(RuntimeError):
    """A personal new-Outlook delivery could not be completed safely."""

    def __init__(self, message, *, stage=None, operation_id=None):
        super().__init__(message)
        self.stage = stage
        self.operation_id = operation_id
