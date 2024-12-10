class NoAvailableInstances(RuntimeError):
    pass


class InvalidCommand(Exception):
    pass


class CombinedError(Exception):
    """
    This is an special error, when using max_retries policy in request/service/task process
    there can be more than 1 exception raised during process
    this error class will record all these exceptions and provide an unify interface for error handling
    Error util will recognize this class and derive it's children errors (along with there traceback)
    so developer can do a much better logging and self-defined handling in error hooks
    """

    def __init__(self, *errors: Exception):
        self.errors = []
        messages = []
        for err in errors:
            if not isinstance(err, Exception):
                continue
            if isinstance(err, CombinedError):
                self.errors.extend(err.errors)
                continue
            if str(err) not in messages:
                messages.append(str(err))
                self.errors.append(err)
        self.message = ";".join(messages)
        super().__init__(self.message)

    def __str__(self):
        return self.message
