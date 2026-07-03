# Dynamic config validation

The Remote Config capability validates a request's coordinates against values that change at runtime
(the poller refreshes them from the upstream). Those checks live in two different places — some in the
Pydantic model, some in a route dependency — and the split is deliberate. This page explains where each
kind of check belongs and, in particular, **why a field whose allowed values come from the resolved
config must be validated in a dependency, not a Pydantic validator**.

## Coordinate checks live in Pydantic validators

The coordinate values and their hierarchy are validated **inside `InfraMetadata`**, because everything
they need is held in memory:

- Each coordinate is checked against its live allowlist (`LIVE_ALLOWED_*`) by a `field_validator`.
- The parent/child *combination* is checked against the live coordinate tree
  (`LIVE_COORDINATE_TREE`) by a `model_validator` — e.g. an `island` must sit under the chosen
  `region`.

Both read module-level state that the background poller repopulates in place. They're **cheap,
synchronous, and side-effect-free**, so a Pydantic validator is the natural home: the model can't be
constructed with an invalid coordinate, anywhere it's constructed.

## Config-dependent fields do not

Some fields aren't validated against a fixed allowlist at all — their valid values depend on the
**config resolved for the request's own coordinates**. For example, the OS templates available to a VM
differ at every leaf of the enterprise config; the allowed set for `os_template` is whatever that
specific leaf configures.

That check **cannot** be a Pydantic validator, for three concrete reasons:

1. **It needs async I/O.** Resolving the value means `await provider.resolve_infra_config(...)`, an
   upstream HTTP call. Pydantic v2 validators are **synchronous** — there is no async validation hook
   during model construction.
2. **It needs the provider.** A validator has no handle on the `RemoteConfigProvider`, and FastAPI
   passes no context into model validation when it parses a request, so the provider can't reach the
   validator.
3. **Validation should stay pure.** Models are constructed in tests, in serialization round-trips, and
   in internal code paths — none of which should trigger a network call. Keeping I/O out of validation
   keeps the model cheap and predictable.

So this kind of check belongs at the **request boundary** — a small FastAPI dependency (or a check in
the route body) that the application writes, running after the model's own validators and resolving
the config once per request.

The rule of thumb: **validate against in-memory data in the model; validate against resolved config in
a dependency.**

## See also

- [Constrain a field by resolved config](../how-to/constrain-field-by-config.md) — the app-side recipe.
- [Enable the Remote Config API](../how-to/enable-remote-config-api.md) — the coordinate allowlists and
  hierarchy in context.
- [OpenAPI & Swagger injection](openapi-swagger-injection.md) — how the live values become Swagger
  dropdowns.
