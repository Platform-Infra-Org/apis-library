"""Public auth error types for the FastAPI template.

Re-exported from the private ``_internal.security.errors`` module so consumers
import them from a stable public location (mirroring ``connectors/errors.py``):

    from tashtiot_apis_library.fastapi_template.errors import TokenError
"""

from ._internal.security.errors import AuthConfigError, SSOError, TokenError

__all__ = ["AuthConfigError", "TokenError", "SSOError"]
