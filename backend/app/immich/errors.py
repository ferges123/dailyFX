class ImmichError(Exception):
    pass


class ImmichConfigurationError(ImmichError):
    pass


class ImmichAuthenticationError(ImmichError):
    pass


class ImmichPermissionError(ImmichError):
    pass


class ImmichConnectionError(ImmichError):
    pass


class ImmichUnexpectedResponseError(ImmichError):
    pass
