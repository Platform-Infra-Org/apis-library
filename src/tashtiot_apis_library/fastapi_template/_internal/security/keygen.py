"""Generate RSA key material and signed JWTs for exercising inbound auth.

This is the *signing* counterpart to :mod:`.verifier`. The verifier checks
incoming bearer tokens against configured material; in offline local-pubkey
mode (``AUTH_PUBLIC_KEY_PEM`` / ``AUTH_PUBLIC_KEY_PATH``) it verifies the
signature with a public key while tokens are signed with the matching private
key. The helpers here produce all three: the private key (sign side), the
public key (verify side), and a ready-to-use token.

Use it as a library::

    from tashtiot_apis_library.fastapi_template.auth import (
        generate_keypair, mint_token,
    )

    private_pem, public_pem = generate_keypair()
    token = mint_token(private_pem, subject="local-dev")

or as a CLI::

    python -m tashtiot_apis_library.fastapi_template._internal.security.keygen
    python -m ...keygen --sub svc --aud my-api --iss https://idp/
    python -m ...keygen --no-write            # print everything, write nothing
    python -m ...keygen --private-key jwt_private.pem   # reuse keys, mint a token
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

__all__ = [
    "generate_keypair",
    "derive_public_pem",
    "load_keypair",
    "mint_token",
    "main",
]


def derive_public_pem(private_pem: str) -> str:
    """Return the SubjectPublicKeyInfo PEM derived from a private key PEM."""
    private_key = serialization.load_pem_private_key(private_pem.encode(), password=None)
    return private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


def generate_keypair(key_size: int = 2048) -> Tuple[str, str]:
    """Generate a fresh RSA keypair, returned as ``(private_pem, public_pem)``."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return private_pem, derive_public_pem(private_pem)


def load_keypair(
    private_path: str, public_path: Optional[str] = None
) -> Tuple[str, str]:
    """Load an existing private key (required, used to sign) and its public key.

    The public key is read from ``public_path`` when given, otherwise derived
    from the private key -- so passing just the private key is enough.
    """
    private_pem = Path(private_path).read_text()
    if public_path is not None:
        public_pem = Path(public_path).read_text()
    else:
        public_pem = derive_public_pem(private_pem)
    return private_pem, public_pem


def mint_token(
    private_pem: str,
    *,
    subject: str,
    algorithm: str = "RS256",
    kid: str = "local-dev-key",
    expires_minutes: Optional[int] = None,
    audience: Optional[str] = None,
    issuer: Optional[str] = None,
) -> str:
    """Sign and return a JWT.

    Always includes ``iat``; includes ``exp`` only when ``expires_minutes`` is
    given. When it is ``None`` (the default) the token never expires and carries
    no ``exp`` claim -- the verifying service must then set ``AUTH_REQUIRE_EXP=false``
    to accept it, since the verifier requires ``exp`` by default. Adds ``aud`` /
    ``iss`` only when supplied, so they match the service's ``AUTH_AUDIENCE`` /
    ``AUTH_ISSUER`` when those are configured.
    """
    now = datetime.now(timezone.utc)
    claims = {
        "sub": subject,
        "iat": now,
    }
    if expires_minutes is not None:
        claims["exp"] = now + timedelta(minutes=expires_minutes)
    if audience is not None:
        claims["aud"] = audience
    if issuer is not None:
        claims["iss"] = issuer
    return jwt.encode(claims, private_pem, algorithm=algorithm, headers={"kid": kid})


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate RSA keys and a signed JWT for inbound auth."
    )
    parser.add_argument("--sub", default="local-dev", help="Token subject ('sub' claim).")
    parser.add_argument("--aud", default=None, help="Audience ('aud'); set to match AUTH_AUDIENCE.")
    parser.add_argument("--iss", default=None, help="Issuer ('iss'); set to match AUTH_ISSUER.")
    parser.add_argument("--algorithm", default="RS256", help="Signing algorithm (default: RS256).")
    parser.add_argument("--kid", default="local-dev-key", help="Key id placed in the JWT header.")
    parser.add_argument(
        "--expires-minutes",
        type=int,
        default=None,
        help=(
            "Token lifetime in minutes. Omit for a non-expiring token (the verifying "
            "service must set AUTH_REQUIRE_EXP=false to accept it)."
        ),
    )
    parser.add_argument("--key-size", type=int, default=2048, help="RSA key size in bits.")
    parser.add_argument("--out-dir", default=".", help="Directory for the .pem files.")
    parser.add_argument("--private-name", default="jwt_private.pem", help="Private key filename.")
    parser.add_argument("--public-name", default="jwt_public.pem", help="Public key filename.")
    parser.add_argument("--no-write", action="store_true", help="Print only; do not write key files.")
    parser.add_argument(
        "--private-key",
        default=None,
        help="Path to an existing private key PEM to sign with (skips key generation).",
    )
    parser.add_argument(
        "--public-key",
        default=None,
        help="Path to an existing public key PEM (optional; derived from --private-key if omitted).",
    )
    return parser


def main(argv: Optional[list] = None) -> None:
    """CLI entry point: generate/load keys, mint a token, print config hints."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.public_key is not None and args.private_key is None:
        parser.error("--public-key requires --private-key (the private key is needed to sign the JWT).")

    # Reuse existing keys when given, else generate a fresh pair. Existing keys
    # are never written back (they already live on disk); only generated keys are.
    using_existing = args.private_key is not None
    if using_existing:
        private_pem, public_pem = load_keypair(args.private_key, args.public_key)
    else:
        private_pem, public_pem = generate_keypair(args.key_size)

    token = mint_token(
        private_pem,
        subject=args.sub,
        algorithm=args.algorithm,
        kid=args.kid,
        expires_minutes=args.expires_minutes,
        audience=args.aud,
        issuer=args.iss,
    )

    # A filesystem path to advertise as AUTH_PUBLIC_KEY_PATH, when one exists.
    public_key_ref = args.public_key

    if using_existing:
        print(f"Using private key -> {args.private_key}  (signing)")
        if args.public_key is not None:
            print(f"Using public key  -> {args.public_key}  (verify)")
        else:
            print("Public key derived from the private key (no --public-key given).")
    elif not args.no_write:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        priv_path = out_dir / args.private_name
        pub_path = out_dir / args.public_name
        # Restrict the private key to the owner; it must never be committed.
        priv_path.write_text(private_pem)
        priv_path.chmod(0o600)
        pub_path.write_text(public_pem)
        public_key_ref = str(pub_path)
        print(f"Wrote private key -> {priv_path}  (keep secret; chmod 600)")
        print(f"Wrote public key  -> {pub_path}")

    # Show the public key inline whenever there is no file to point at, so the
    # user can paste it into AUTH_PUBLIC_KEY_PEM.
    if public_key_ref is None:
        print()
        print("===== PUBLIC KEY (verify side -- paste into AUTH_PUBLIC_KEY_PEM) =====")
        print(public_pem)

    # In print-only generate mode, also surface the private key (it was not written).
    if not using_existing and args.no_write:
        print("===== PRIVATE KEY (sign side -- keep secret) =====")
        print(private_pem)

    print()
    print("Configure the service (.env):")
    print("  AUTH_ENABLED=true")
    if public_key_ref is not None:
        print(f"  AUTH_PUBLIC_KEY_PATH={public_key_ref}")
    else:
        print("  AUTH_PUBLIC_KEY_PEM=<the PUBLIC KEY above>")
    if args.algorithm != "RS256":
        print(f'  AUTH_ALGORITHMS=["{args.algorithm}"]')
    if args.aud is not None:
        print(f"  AUTH_AUDIENCE={args.aud}")
    if args.iss is not None:
        print(f"  AUTH_ISSUER={args.iss}")
    if args.expires_minutes is None:
        # The token carries no `exp`; the verifier requires it unless told otherwise.
        print("  AUTH_REQUIRE_EXP=false   # the minted token never expires (no 'exp' claim)")
    print()

    print("===== BEARER TOKEN =====")
    print(token)
    print()
    print("Try it against a protected route:")
    print(f'  curl -H "Authorization: Bearer {token}" \\')
    print("       http://localhost:8000/<protected-route>")


if __name__ == "__main__":
    main()
