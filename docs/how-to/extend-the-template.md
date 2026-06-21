# Extend the FastAPI template

`general_create_app()` returns a plain `FastAPI` instance, so as a **consumer** you can add your own
routes and middleware to it directly — no library changes needed:

```python
app = general_create_app()

@app.get("/custom")
def custom():
    return {"ok": True}
```

This guide is for **contributors** adding a *built-in* piece to the template — one that ships behind
an `enable_*` flag on the factory. The factory wires each built-in through small registration helpers
under `_internal/`, toggled by a keyword argument.

## Add a built-in middleware

1. Create it under `_internal/middlewares/`:

   ```python
   # _internal/middlewares/my_middleware.py
   from fastapi import Request
   from loguru import logger
   from starlette.middleware.base import BaseHTTPMiddleware

   class MyMiddleware(BaseHTTPMiddleware):
       async def dispatch(self, request: Request, call_next):
           logger.debug("before {}", request.url.path)
           response = await call_next(request)
           return response
   ```

2. Register it in `add_middlewares` (`_internal/middlewares/__init__.py`) behind a flag:

   ```python
   def add_middlewares(app, *, enable_my_middleware: bool = True, ...):
       if enable_my_middleware:
           app.add_middleware(MyMiddleware)
   ```

   Mind ordering: Starlette applies middleware LIFO, so auth/logging/timing are registered in a
   specific order — add yours where it belongs in that chain.

3. Thread the flag through `general_create_app` (`_internal/__init__.py`), passing it into
   `add_middlewares(app, enable_my_middleware=enable_my_middleware, ...)`.

## Add a built-in route

1. Create a router under `_internal/routes/`:

   ```python
   # _internal/routes/my_route.py
   from fastapi import APIRouter

   router = APIRouter(prefix="/my-feature", tags=["My Feature"])

   @router.get("/status")
   async def status():
       return {"status": "ok"}
   ```

2. Register it in `add_routers` (`_internal/routes/__init__.py`) behind a flag:

   ```python
   def add_routers(app, *, enable_my_route: bool = True, ...):
       if enable_my_route:
           app.include_router(router)   # add include_in_schema=False to hide from /docs
   ```

3. Thread an `enable_my_route` flag through `general_create_app`.

## Add a shared utility

Put reusable internals under `_internal/utils/` (or `_internal/database/` for HTTP). To make a
utility **public**, re-export it from the matching public module — `fastapi_template/utils.py`
(infra), `auth.py` (inbound JWT), `security.py` (outbound SSO), or `errors.py` — and add it to that
module's `__all__`. Keep heavy dependencies lazy where the existing modules do (see
[Architecture](../explanation/architecture.md)).

## Checklist

- New code uses **relative imports** and logs via `from loguru import logger` at the
  [standard levels](../explanation/logging.md).
- Every built-in is **opt-out-able** via an `enable_*` flag (default chosen sensibly).
- Public symbols land on the narrow public surface; implementation stays under `_internal/`.
- Tests added under `tests/fastapi_template/`.

## See also

- [Add a new connector](add-a-connector.md)
- [Architecture](../explanation/architecture.md)
- [Development workflow](../contributing/development.md)
