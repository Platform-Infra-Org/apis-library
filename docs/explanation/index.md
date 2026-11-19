# Explanation

Explanation is **understanding-oriented**: it discusses the *why* behind the library — the design
decisions, the structure, and the trade-offs. Read these when you want context, not a step-by-step
(that's the [How-to guides](../how-to/index.md)) or a lookup (that's the
[Reference](../reference/index.md)).

- **[Architecture](architecture.md)** — the two independent toolsets, the three-layer connector
  pattern, and the public-surface / `_internal` boundary.
- **[Authentication design](authentication.md)** — the dual-gate, the three verification modes plus
  OIDC discovery, inbound vs outbound, and why PyJWT is imported lazily.
- **[Dynamic config validation](dynamic-config-validation.md)** — where each coordinate/config check
  lives, and why config-dependent fields are validated in a dependency, not a Pydantic validator.
- **[OpenAPI & Swagger injection](openapi-swagger-injection.md)** — OpenAPI/Swagger basics and how the
  library patches the generated schema so Swagger shows live coordinate dropdowns.
- **[Logging](logging.md)** — how a single global Loguru logger is configured once at import and
  shared everywhere.
- **[Async and the event loop](async.md)** — what async is, why the library uses it instead of a
  sync design, and why blocking calls are banned.
- **[Job queues & long-running work](job-queues.md)** — the job-queue concept, why AWX already is
  one, and the options when your API needs its own.
- **[Cloud-native APIs & multiple replicas](cloud-native.md)** — what running several identical
  pods means for state, idempotency, background tasks, shutdown, rollouts and observability.
