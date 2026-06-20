"""Inbound authentication for the FastAPI Template.

This package's submodules (``verifier``, ``keygen``, ``sso``) pull in PyJWT /
cryptography. To keep those off the default import path, this ``__init__`` is
intentionally empty -- importing the ``security`` package does **not** import its
heavy submodules. Consumers reach the pieces they need by their full submodule
path (e.g. ``from ._internal.security.verifier import JWTVerifier``), and the
public facades (``fastapi_template.auth`` / ``.security`` / ``.errors``) re-export
them lazily so apps with auth disabled never trigger the PyJWT import.
"""
