"""Exception handlers used by the FastAPI Template application."""

from fastapi import HTTPException, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    logger.opt(exception=exc).info(f"HTTP error {exc.status_code}: {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger.opt(exception=exc).info(f"Validation error: {exc.errors()}")
    return await request_validation_exception_handler(request, exc)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.opt(exception=exc).warning(f"Unhandled error: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


# (exception class, handler) pairs registered via app.add_exception_handler.
handlers = [
    (HTTPException, http_exception_handler),
    (RequestValidationError, validation_exception_handler),
    (Exception, unhandled_exception_handler),
]
