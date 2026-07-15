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


import logging
from contextlib import contextmanager

from fastapi import HTTPException

from app.utils.safe_logging import redact_sensitive

logger = logging.getLogger(__name__)


@contextmanager
def handle_immich_errors():
    try:
        yield
    except ImmichConfigurationError as exc:
        logger.error("Immich configuration error: %s", redact_sensitive(exc))
        raise HTTPException(status_code=400, detail="Immich configuration error") from exc
    except ImmichAuthenticationError as exc:
        logger.error("Immich authentication failed: %s", redact_sensitive(exc))
        raise HTTPException(status_code=401, detail="Immich authentication failed") from exc
    except ImmichPermissionError as exc:
        logger.error("Permission denied by Immich: %s", redact_sensitive(exc))
        raise HTTPException(status_code=403, detail="Permission denied by Immich") from exc
    except ImmichConnectionError as exc:
        logger.error("Failed to connect to Immich: %s", redact_sensitive(exc))
        raise HTTPException(status_code=502, detail="Failed to connect to Immich") from exc
    except ImmichUnexpectedResponseError as exc:
        logger.error("Unexpected response from Immich: %s", redact_sensitive(exc))
        raise HTTPException(status_code=502, detail="Unexpected response from Immich") from exc
