# How-to guides

How-to guides are **task-oriented**: each one is a focused recipe for accomplishing a specific goal,
assuming you already know roughly what you want. If you're new, start with the
[Tutorials](../tutorials/index.md) instead.

## Connectors

- **[Read & write Bitbucket files](read-write-bitbucket.md)** — use the `Git` connector to read,
  add, modify, and delete files in a Bitbucket Server repo.
- **[Drive AWX, ArgoCD & Vault](use-awx-argocd-vault.md)** — launch and await AWX jobs, sync ArgoCD
  apps, and read/write Vault secrets.
- **[Add a new connector](add-a-connector.md)** — extend the library with your own service following
  the three-layer pattern.

## Authentication

- **[Verify a token outside a request](verify-a-token.md)** — check a JWT in a worker or script.
- **[Call other services with SSO](call-services-with-sso.md)** — attach auto-refreshing
  OAuth2 `client_credentials` tokens to outbound calls.
- **[Generate dev auth material](generate-auth-material.md)** — mint keys and tokens with the
  `gen-auth-material` CLI.

## Capabilities

- **[Enable the Remote Config API](enable-remote-config-api.md)** — wire an authenticated proxy to an
  upstream Config API with live Swagger enum dropdowns.
