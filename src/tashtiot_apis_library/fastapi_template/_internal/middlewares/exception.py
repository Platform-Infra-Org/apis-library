"""Exception handlers used by the FastAPI Template application."""

from fastapi import HTTPException, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger

from ..models import ExceptionHandlerConfig


def _http_exception_message(exc: HTTPException) -> dict:
    return {"detail": exc.detail}


def _validation_exception_message(exc: RequestValidationError) -> dict:
    return {"detail": exc.errors()}


def _unhandled_exception_message() -> dict:
    return {"detail": "Internal Server Error"}


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    logger.opt(exception=exc).info(f"HTTP error {exc.status_code}: {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content=_http_exception_message(exc))


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger.opt(exception=exc).info(f"Validation error: {exc.errors()}")
    return await request_validation_exception_handler(request, exc)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.opt(exception=exc).warning(f"Unhandled error: {exc}")
    return JSONResponse(status_code=500, content=_unhandled_exception_message())


handlers = [
    ExceptionHandlerConfig(exception_class=HTTPException, handler=http_exception_handler),
    ExceptionHandlerConfig(
        exception_class=RequestValidationError, handler=validation_exception_handler
    ),
    ExceptionHandlerConfig(exception_class=Exception, handler=unhandled_exception_handler),
]
