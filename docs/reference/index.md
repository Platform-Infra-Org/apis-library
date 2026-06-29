# Reference

Reference material is **information-oriented**: the dry, authoritative facts. It describes the
machinery without teaching or persuading — look here when you need to confirm a name, a default, or a
signature.

- **[Configuration](configuration.md)** — every environment variable the FastAPI template reads, with
  defaults: core settings, inbound auth (`AUTH_*`), outbound SSO (`AUTH_SSO_*`), and Remote Config
  (`CONFIG_REMOTE_*`).
- **[CLI (`gen-auth-material`)](cli.md)** — the full option table for the key/token generator.

## API reference

Auto-generated from the package's docstrings:

- **[Connectors](api/connectors.md)** — `AWX`, `ArgoCD`, `Git`, `Vault` and their response models.
- **[FastAPI app](api/fastapi-app.md)** — `general_create_app`, `BaseAPI`, `settings`.
- **[Auth (inbound JWT)](api/auth.md)** — `get_current_claims`, `verify_token`, `JWTVerifier`, keygen.
- **[Security (outbound SSO)](api/security.md)** — `sso_authenticated_api`, `SSOConfig`, `StaticBearerAuth`.
- **[Remote Config API](api/config-api.md)** — `enable_remote_config_api`, `RemoteConfigProvider`.
- **[Errors](api/errors.md)** — connector and auth exception types.
- **[Schemas](api/schemas.md)** — shared request/response models.
