# OpenAPI, Swagger, and dynamic enum injection

The Remote Config capability makes Swagger show **live dropdowns** of the allowed coordinate values —
values that change at runtime as the poller refreshes them. This page explains how that works, starting
from OpenAPI/Swagger basics, because the mechanism is "patch the generated schema," not a FastAPI
feature.

## OpenAPI vs Swagger UI

Two different things people conflate:

- **OpenAPI** is a *document* — a JSON (or YAML) description of your API: its paths, each method's
  parameters / request body, and every shape described with **JSON Schema**. It's just data.
- **Swagger UI** is a *renderer* — a JavaScript app that reads an OpenAPI document and draws the
  interactive docs (the "Try it out" forms, dropdowns, the "Schemas" catalog at the bottom). It knows
  nothing about your Python code; it only knows the JSON.

FastAPI introspects your routes + Pydantic models and builds the OpenAPI dict via `get_openapi(...)`,
caching it on the app:

- `app.openapi()` — the callable that returns the document.
- `app.openapi_schema` — the cache. Set it to `None` and the next `app.openapi()` rebuilds.
- `/openapi.json` returns `app.openapi()`; Swagger UI at `/docs` fetches that and renders it.

## The shape that matters

```jsonc
{
  "paths": { "/config": { "get": {
      "parameters": [ { "name": "region", "in": "query",
                        "schema": { "type": "string" } } ],       // query/path params, inline
      "requestBody": { "content": { "application/json": {
                        "schema": { "$ref": "#/components/schemas/DNSRecordCreate" } } } } } } },
  "components": { "schemas": {                                     // every model, once, by name
      "DNSRecordCreate": { "properties": { "metadata": { "$ref": "#/components/schemas/InfraMetadata" } } },
      "InfraMetadata":   { "properties": { "region": { "anyOf": [{"type":"string"},{"type":"null"}] } } } } }
}
```

- **`enum`** is what Swagger turns into a **dropdown**. No `enum` → free-text box.
- **Query/path params** are written **inline** under each operation's `parameters`.
- **Bodies (and response models)** are *not* inlined: the schema is a **`$ref`** into the single shared
  `components.schemas` entry, and models nest by `$ref`-ing each other.
- **Optional/nullable** fields render as `{"anyOf": [{"type":"string"}, {"type":"null"}]}` — the string
  type is in a *branch*, not at the top level.

## Why we post-process the document

The valid coordinate values are dynamic (the poller refreshes `LIVE_ALLOWED_*` at runtime). A normal
Pydantic `Enum`/`Literal` is frozen at import, so it can't track them. Instead the library **patches the
generated OpenAPI document** every time it's built, writing the current allowlist values in as `enum`.
That's the injection.

## The mechanism (`make_config_openapi`)

`enable_remote_config_api` installs it: `app.openapi = make_config_openapi(app, coordinate_paths)`.

- **Wrap, don't replace.** It captures the previous `app.openapi` and calls it. This matters because
  `general_create_app` already wrapped `app.openapi` to add the Bearer "Authorize" scheme; wrapping
  composes (`enum wrapper → bearer wrapper → FastAPI`), replacing would drop the Authorize button.
- **Live values by reference.** It captures the `LIVE_ALLOWED_*` sets; the poller mutates them in place,
  so the captured references always see current values.
- **Regex path match.** Each `coordinate_paths` entry is a regex `fullmatch`ed against every route path.
- **`_inject`** is name-matched: only fields *named* after a coordinate (`space`/`network`/…) get an
  `enum`, and only when that allowlist is non-empty. It places the enum **inside the `anyOf` string
  branch** for Optional fields (where Swagger's model renderer looks) and top-level for flat ones.
- **Recursion.** For bodies it descends through nested `$ref` components (so `DNSRecordCreate → metadata:
  InfraMetadata → region` works), with a visited-set cycle guard.
- **Refresh.** The poller nulls `app.openapi_schema` each cycle, so the next `/openapi.json` request
  rebuilds + re-patches with the latest values — no restart.
- **Log.** One INFO line names the routes that received values (once per change), which doubles as a
  "did my `coordinate_paths` match?" check.

## Why query params and bodies behave differently (the subtle bit)

OpenAPI represents the two kinds of input differently, and it shows up in Swagger:

- A **body / response model** is a single object in `components.schemas`, referenced by `$ref`. The
  "Try it out" body form **and** the bottom "Schemas" section both render that same object. Patch it once
  → both show the enums.
- **Query params** are **inlined copies** of each field into the operation's `parameters` list — there
  is no shared component for "a bag of query params." Patching the inlined copy makes the dropdown work,
  but the standalone `InfraMetadata` component (present because response models `$ref` it) is a
  *different* object the params don't point to.

So for query-param usage the injector patches the inlined params (dropdown works), and additionally
patches the **shared component** for the dynamic models (`InfraMetadata` / `RequiredInfraMetadata`) so the
"Schemas" section shows the options too. That component pass is scoped **by name** — the static
`MetadataRequest` shares the field names but is intentionally not dynamic, so it's left untouched.

## Caveats

- **Name-matched and additive.** A field must be *named* after a coordinate to get a dropdown; a mistyped
  path, non-coordinate field, or empty allowlist just yields nothing (hence the INFO log).
- **`coordinate_paths` is `fullmatch`ed.** Use `.*` for partials; a non-matching entry is a silent no-op.
- **Components are shared.** Patching a component (body/response models, and the named dynamic-model pass)
  shows the enums everywhere that component is `$ref`'d — one source of truth, not route-specific.

## See also

- [Enable the Remote Config API](../how-to/enable-remote-config-api.md) — wiring, `coordinate_paths`, the
  seed/poller.
- [Dynamic config validation](dynamic-config-validation.md) — where each coordinate check lives (model
  validators vs a dependency).
