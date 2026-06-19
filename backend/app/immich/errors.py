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


from contextlib import contextmanager

from fastapi import HTTPException


@contextmanager
def handle_immich_errors():
    try:
        yield
    except ImmichConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ImmichAuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ImmichPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ImmichConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ImmichUnexpectedResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
