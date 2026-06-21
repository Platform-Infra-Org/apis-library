# Your first app

In this tutorial you'll build and run a FastAPI service using the library's application factory,
then explore the features it wires up for you out of the box. You need Python ≥ 3.9 and about five
minutes.

## 1. Install

```bash
pip install tashtiot-apis-library
# uvicorn comes as a dependency; install nothing else for this tutorial
```

## 2. Create the app

The factory `general_create_app()` returns a fully-configured `FastAPI` instance. Create a file
called `main.py`:

```python
from tashtiot_apis_library import general_create_app
from tashtiot_apis_library.fastapi_template.utils import settings

app = general_create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
```

That's the whole app. `general_create_app()` has already registered logging/timing middleware, an
exception handler, a root route, a Prometheus metrics endpoint, health probes, and a self-hosted
Swagger UI.

## 3. Run it

```bash
python main.py
# or: uvicorn main:app --port 8000
```

You should see structured Loguru output on stdout as the app starts.

## 4. Explore what you got

With the server running, open these in a browser or with `curl`:

| URL | What it is |
|---|---|
| `http://localhost:8000/` | The built-in root route |
| `http://localhost:8000/docs` | Swagger UI (served from bundled static assets) |
| `http://localhost:8000/redoc` | ReDoc |
| `http://localhost:8000/metrics` | Prometheus-format metrics |
| `http://localhost:8000/health/live` | Liveness probe (Kubernetes-ready) |
| `http://localhost:8000/health/ready` | Readiness probe |

Each request is logged with its method, path, and processing time.

## 5. Add your own route

The returned `app` is an ordinary `FastAPI` instance — add routes the usual way:

```python
@app.get("/hello")
def hello():
    return {"message": "hello from tashtiot-apis-library"}
```

Restart and visit `http://localhost:8000/hello`. It shows up in `/docs` automatically.

## 6. Configure via environment

Every built-in is configurable through environment variables (or a `.env` file). For example, to
change the port and log level:

```env
PORT=9000
LOG_LEVEL=DEBUG
APP_NAME=MyFirstApp
```

See the full list in the [Configuration reference](../reference/configuration.md).

## Next steps

- **[Secure your API](secure-your-api.md)** — add JWT bearer authentication.
- **[How-to guides](../how-to/index.md)** — connect to ArgoCD/AWX/Vault, call services with SSO, and
  more.
- **[Architecture](../explanation/architecture.md)** — understand how the factory and connectors are
  structured.
