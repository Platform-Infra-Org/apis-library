"""Exception handlers used by the FastAPI Template application."""

from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    logger.opt(exception=exc).info(f"HTTP error {exc.status_code}: {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


def safe_validation_errors(errors) -> list:
    """Keep only where and why validation failed: ``loc``, ``msg`` and ``type``.

    Pydantic error dicts also carry ``input`` (the raw submitted value) and ``ctx``, either of
    which can hold a password or token from the request body, so neither is logged nor returned.
    ``str(exc)`` embeds them too, which is why the exception itself isn't attached to the log record.
    """
    return [{key: err.get(key) for key in ("loc", "msg", "type")} for err in errors]


def validation_error_response(errors) -> JSONResponse:
    """FastAPI's standard 422 body (``{"detail": [...]}``) without submitted values."""
    return JSONResponse(
        status_code=422, content={"detail": jsonable_encoder(safe_validation_errors(errors))}
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger.info(
        "Validation error on {} {}: {}",
        request.method,
        request.url.path,
        safe_validation_errors(exc.errors()),
    )
    return validation_error_response(exc.errors())


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.opt(exception=exc).warning(f"Unhandled error: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


# (exception class, handler) pairs registered via app.add_exception_handler.
handlers = [
    (HTTPException, http_exception_handler),
    (RequestValidationError, validation_exception_handler),
    (Exception, unhandled_exception_handler),
]
