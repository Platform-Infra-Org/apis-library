from typing import Awaitable, Callable, Type, Union

from fastapi import HTTPException, Request
from fastapi.exceptions import ValidationException, WebSocketException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

exception_type = Union[
    Type[Exception], Type[HTTPException], Type[ValidationException], Type[WebSocketException]
]


class ExceptionHandlerConfig(BaseModel):
    exception_class: exception_type
    handler: Callable[[Request, exception_type], Awaitable[JSONResponse]]
