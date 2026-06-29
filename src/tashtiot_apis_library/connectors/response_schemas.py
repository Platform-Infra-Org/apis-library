"""Base operation response schema for all connectors.

This module provides the base OperationResponse class that connector-specific
response schemas extend. Connector-specific schemas are defined in their
respective connector models.py files.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

__all__ = [
    "OperationResponse",
]


class OperationResponse(BaseModel):
    """Base response schema for operations.

    Attributes:
        status: Operation status - typically "successful", a response from external service, or "failed"
        status_code: HTTP status code if applicable
        return_code: Process return code if applicable
        stdout: Standard output from the operation
    """

    status: str = Field(
        ..., description='Operation status: "successful", external service response, or "failed"'
    )
    status_code: Optional[int] = Field(
        default=None, description="HTTP status code from external service"
    )
    return_code: Optional[int] = Field(default=None, description="Process return code")
    stdout: str = Field(default="", description="Standard output from the operation")
