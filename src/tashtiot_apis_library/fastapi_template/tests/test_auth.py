"""Tests for inbound JWT authentication (verifier modes + middleware enforcement)."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Request
from httpx import ASGITransport, AsyncClient

from ..utils import settings
from .._internal import general_create_app
from .._internal.security import verifier as verifier_mod
from .._internal.security.errors import AuthConfigError, TokenError
from .._internal.security.verifier import AuthMode, JWTVerifier

# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #

HS256_SECRET = "unit-test-secret"


@pytest.fixture(autouse=True)
def _reset_auth_settings(monkeypatch):
    """Reset the shared settings singleton + verifier cache around each test."""
    verifier_mod._verifier_cache.clear()
    for name, value in {
        "AUTH_ENABLED": False,
        "AUTH_HEADER_NAME": "Authorization",
        "AUTH_HS256_SECRET": None,
        "AUTH_JWKS_URL": None,
        "AUTH_PUBLIC_KEY_PEM": None,
        "AUTH_PUBLIC_KEY_PATH": None,
        "AUTH_ALGORITHMS": ["RS256"],
        "AUTH_AUDIENCE": None,
        "AUTH_ISSUER": None,
    }.items():
        monkeypatch.setattr(settings, name, value)
    yield
    verifier_mod._verifier_cache.clear()


@pytest.fixture(scope="module")
def rsa_keys():
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    pub_pem = priv.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return priv_pem, pub_pem


def _claims(**extra):
    base = {"sub": "user-1", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    base.update(extra)
    return base


def _hs256(secret=HS256_SECRET, **extra):
    return jwt.encode(_claims(**extra), secret, algorithm="HS256")


def _rs256(priv_pem, kid="test-kid", **extra):
    return jwt.encode(_claims(**extra), priv_pem, algorithm="RS256", headers={"kid": kid})


# --------------------------------------------------------------------------- #
# Verifier unit tests — HS256
# --------------------------------------------------------------------------- #


def test_hs256_valid_token(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_HS256_SECRET", HS256_SECRET)
    v = JWTVerifier(settings)
    assert v.mode is AuthMode.HS256
    claims = v.verify(_hs256())
    assert claims["sub"] == "user-1"


def test_hs256_wrong_secret(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_HS256_SECRET", HS256_SECRET)
    v = JWTVerifier(settings)
    with pytest.raises(TokenError, match="Invalid token"):
        v.verify(_hs256(secret="not-the-secret"))


def test_hs256_expired(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_HS256_SECRET", HS256_SECRET)
    v = JWTVerifier(settings)
    expired = _hs256(exp=datetime.now(timezone.utc) - timedelta(minutes=1))
    with pytest.raises(TokenError, match="Token has expired"):
        v.verify(expired)


def test_hs256_rejects_rs256_token(monkeypatch, rsa_keys):
    priv_pem, _ = rsa_keys
    monkeypatch.setattr(settings, "AUTH_HS256_SECRET", HS256_SECRET)
    v = JWTVerifier(settings)
    assert v._algorithms == ["HS256"]
    with pytest.raises(TokenError, match="Invalid token"):
        v.verify(_rs256(priv_pem))


# --------------------------------------------------------------------------- #
# Verifier unit tests — local public key
# --------------------------------------------------------------------------- #


def test_local_pubkey_pem_valid(monkeypatch, rsa_keys):
    priv_pem, pub_pem = rsa_keys
    monkeypatch.setattr(settings, "AUTH_PUBLIC_KEY_PEM", pub_pem)
    v = JWTVerifier(settings)
    assert v.mode is AuthMode.LOCAL_PUBKEY
    assert v.verify(_rs256(priv_pem))["sub"] == "user-1"


def test_local_pubkey_wrong_key(monkeypatch, rsa_keys):
    _, pub_pem = rsa_keys
    other_priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_priv_pem = other_priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    monkeypatch.setattr(settings, "AUTH_PUBLIC_KEY_PEM", pub_pem)
    v = JWTVerifier(settings)
    with pytest.raises(TokenError, match="Invalid token"):
        v.verify(_rs256(other_priv_pem))


def test_local_pubkey_from_path(monkeypatch, rsa_keys, tmp_path):
    priv_pem, pub_pem = rsa_keys
    key_file = tmp_path / "pub.pem"
    key_file.write_text(pub_pem)
    monkeypatch.setattr(settings, "AUTH_PUBLIC_KEY_PATH", str(key_file))
    v = JWTVerifier(settings)
    assert v.mode is AuthMode.LOCAL_PUBKEY
    assert v.verify(_rs256(priv_pem))["sub"] == "user-1"


def test_local_pubkey_unreadable_path(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_PUBLIC_KEY_PATH", "/no/such/key.pem")
    with pytest.raises(AuthConfigError, match="Unable to read"):
        JWTVerifier(settings)


# --------------------------------------------------------------------------- #
# Verifier unit tests — JWKS (key client injected, no network)
# --------------------------------------------------------------------------- #


def _jwks_verifier(monkeypatch, signing_key=None, raises=None):
    monkeypatch.setattr(settings, "AUTH_JWKS_URL", "https://idp.example.com/jwks.json")
    v = JWTVerifier(settings)
    assert v.mode is AuthMode.JWKS

    def _get(token):
        if raises is not None:
            raise raises
        return SimpleNamespace(key=signing_key)

    v._jwks_client = SimpleNamespace(get_signing_key_from_jwt=_get)
    return v


def test_jwks_valid_token(monkeypatch, rsa_keys):
    priv_pem, pub_pem = rsa_keys
    v = _jwks_verifier(monkeypatch, signing_key=pub_pem)
    assert v.verify(_rs256(priv_pem))["sub"] == "user-1"


def test_jwks_unknown_kid(monkeypatch, rsa_keys):
    priv_pem, _ = rsa_keys
    v = _jwks_verifier(monkeypatch, raises=jwt.PyJWKClientError("kid not found"))
    with pytest.raises(TokenError, match="Unable to verify token"):
        v.verify(_rs256(priv_pem))


# --------------------------------------------------------------------------- #
# Verifier unit tests — audience / issuer
# --------------------------------------------------------------------------- #


def test_audience_match_and_mismatch(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_HS256_SECRET", HS256_SECRET)
    monkeypatch.setattr(settings, "AUTH_AUDIENCE", "my-api")
    v = JWTVerifier(settings)
    assert v.verify(_hs256(aud="my-api"))["aud"] == "my-api"
    with pytest.raises(TokenError, match="Invalid token audience"):
        v.verify(_hs256(aud="other-api"))


def test_issuer_mismatch(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_HS256_SECRET", HS256_SECRET)
    monkeypatch.setattr(settings, "AUTH_ISSUER", "https://idp.example.com/")
    v = JWTVerifier(settings)
    with pytest.raises(TokenError, match="Invalid token issuer"):
        v.verify(_hs256(iss="https://evil.example.com/"))


def test_unconfigured_aud_iss_ignored(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_HS256_SECRET", HS256_SECRET)
    v = JWTVerifier(settings)
    # Arbitrary aud/iss accepted when not configured.
    assert v.verify(_hs256(aud="whatever", iss="anyone"))["sub"] == "user-1"


# --------------------------------------------------------------------------- #
# Verifier unit tests — mode selection / config validation
# --------------------------------------------------------------------------- #


def test_no_material_raises():
    with pytest.raises(AuthConfigError, match="no verification material"):
        JWTVerifier(settings)


def test_ambiguous_material_raises(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_HS256_SECRET", HS256_SECRET)
    monkeypatch.setattr(settings, "AUTH_JWKS_URL", "https://idp.example.com/jwks.json")
    with pytest.raises(AuthConfigError, match="Ambiguous"):
        JWTVerifier(settings)


# --------------------------------------------------------------------------- #
# Middleware integration tests
# --------------------------------------------------------------------------- #


def _auth_app(monkeypatch, **route_kwargs):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "AUTH_HS256_SECRET", HS256_SECRET)
    app = general_create_app(enable_auth=True)

    @app.get("/protected")
    async def protected(request: Request):
        return {"user": request.state.user}

    return app


async def _get(app, path, headers=None):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        return await ac.get(path, headers=headers)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path", ["/metrics", "/liveness", "/readiness", "/docs", "/openapi.json"]
)
async def test_excluded_paths_pass_without_token(monkeypatch, path):
    app = _auth_app(monkeypatch)
    resp = await _get(app, path)
    assert resp.status_code != 401


@pytest.mark.asyncio
async def test_root_is_protected_by_default(monkeypatch):
    # "/" cannot be a prefix-exclude (it matches every path), so the welcome
    # root is protected when auth is enabled -- secure by default.
    app = _auth_app(monkeypatch)
    resp = await _get(app, "/")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_no_header_401(monkeypatch):
    app = _auth_app(monkeypatch)
    resp = await _get(app, "/protected")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Not authenticated"}
    assert resp.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.asyncio
@pytest.mark.parametrize("header", ["token-without-scheme", "Bearer", "Basic abc"])
async def test_protected_malformed_header_401(monkeypatch, header):
    app = _auth_app(monkeypatch)
    resp = await _get(app, "/protected", headers={"Authorization": header})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_invalid_token_401(monkeypatch):
    app = _auth_app(monkeypatch)
    resp = await _get(app, "/protected", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid token"}


@pytest.mark.asyncio
async def test_protected_expired_token_401(monkeypatch):
    app = _auth_app(monkeypatch)
    token = _hs256(exp=datetime.now(timezone.utc) - timedelta(minutes=1))
    resp = await _get(app, "/protected", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Token has expired"}


@pytest.mark.asyncio
async def test_protected_valid_token_200(monkeypatch):
    app = _auth_app(monkeypatch)
    token = _hs256()
    resp = await _get(app, "/protected", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["user"]["sub"] == "user-1"


@pytest.mark.asyncio
async def test_401_is_still_timed(monkeypatch):
    """Proves middleware ordering: timing wraps auth, so 401s carry the header."""
    app = _auth_app(monkeypatch)
    resp = await _get(app, "/protected")
    assert resp.status_code == 401
    assert settings.PROCESS_TIME_HEADER in resp.headers


@pytest.mark.asyncio
async def test_dual_gate_disabled_when_auth_env_off(monkeypatch):
    # Code flag on, but runtime master switch off -> middleware not registered.
    monkeypatch.setattr(settings, "AUTH_ENABLED", False)
    monkeypatch.setattr(settings, "AUTH_HS256_SECRET", HS256_SECRET)
    app = general_create_app(enable_auth=True)

    @app.get("/protected")
    async def protected(request: Request):
        return {"ok": True}

    resp = await _get(app, "/protected")
    assert resp.status_code == 200
