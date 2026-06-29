"""Public infrastructure utilities for the FastAPI template.

Inbound-JWT helpers now live in ``fastapi_template.auth`` and outbound SSO helpers
in ``fastapi_template.security`` -- they are no longer re-exported from here.
"""

from ._internal.database import BaseAPI
from ._internal.utils import settings

__all__ = ["BaseAPI", "settings"]
