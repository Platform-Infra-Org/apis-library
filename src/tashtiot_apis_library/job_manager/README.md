# Job manager

A general-purpose **async job runner** for long-running operations Ansible can't drive — on *any*
system (SSH, cloud CLIs, kubectl, custom scripts). Built on **Dramatiq + Redis**: the API enqueues,
a separate **worker** process executes, and a Redis-backed `JobRepository` is the **sole source of
truth** for status / result / history.

- AWX-mirrored client: `launch_job` · `get_job_status` · `wait_for_job_completion` · `cancel_job` · `get_logs`
- per-target serialization (a lock keyed by `target`), cooperative + abort-middleware cancellation
- `max_retries=0` by default (operations are non-idempotent)
- pluggable `Executor` (the generic `CommandExecutor` ships in the box; bring your own for anything else)

> Optional: everything here lives behind the `[job-manager]` extra. The base package imports without
> it; install it where you run the API and the worker.

```bash
pip install "tashtiot-apis-library[job-manager]"     # dramatiq[redis] + dramatiq-abort[redis]
```

## How to implement

### 1. Mount the API onto your app

API replicas only *enqueue* and read the repository — no executor here.

```python
from tashtiot_apis_library import general_create_app, enable_job_manager

app = general_create_app()
# adds: POST /jobs, GET /jobs, GET /jobs/{id}, /status, /logs, POST /{id}/cancel
enable_job_manager(app, prefix="/api/v1", known_operations={"drain_node", "scale"})
```

`known_operations` is optional; when set, an unknown operation is rejected at launch with `422`
instead of failing later in the worker.

### 2. Run a worker (separate process/deployment)

The default `CommandExecutor` maps each operation to a command via `JM_COMMAND_MAP`
(`{operation: argv}`); every `{name}` token is filled from the request's `params` (other braces —
jsonpath, Go templates — pass through). argv form (no shell) is the default.

```bash
export REDIS_URL=redis://localhost:6379/0
export JM_COMMAND_MAP='{
  "drain_node": ["ssh", "{host}", "kubectl", "drain", "{node}"],
  "scale":      ["kubectl", "scale", "--replicas={n}", "deploy/{name}"]
}'
dramatiq tashtiot_apis_library.job_manager.tasks --processes 2 --threads 4
```

### 3. Launch & track

```bash
curl -X POST localhost:8000/api/v1/jobs \
  -d '{"target": "host-1", "operation": "drain_node", "params": {"host": "host-1", "node": "n1"}}'
# 202 {"job_id": "...", "status": "pending"}

curl localhost:8000/api/v1/jobs/<id>/status   # {"status": "running"|"succeeded"|...}
curl localhost:8000/api/v1/jobs/<id>/logs     # captured stdout (once terminal)
curl -X POST localhost:8000/api/v1/jobs/<id>/cancel
```

`target` is both what the op acts on **and** the serialization key — two jobs with the same `target`
never run concurrently. Pass `idempotency_key` to dedupe retried launches.

### Custom backend (not a shell command)

Implement the `Executor` protocol and register it in your own worker module — routes and status
tracking are unchanged:

```python
# myapp/worker.py  ->  dramatiq myapp.worker --processes 2 --threads 4
from tashtiot_apis_library.job_manager import Executor, tasks

class MyExecutor:                       # satisfies Executor structurally
    async def run(self, operation, params):
        ...                             # do the work
        yield "some output line"        # streamed -> stored as the job's logs/result

tasks.set_executor(MyExecutor())
from tashtiot_apis_library.job_manager.tasks import run_job  # noqa: F401 - registers the actor
```

## Settings (env / `.env`)

`REDIS_URL`, `REDIS_MAX_CONNECTIONS`, `REDIS_SOCKET_TIMEOUT`, `JM_JOB_TTL`, `JM_TARGET_LOCK_TIMEOUT`,
`JM_TARGET_LOCK_WAIT`, `JM_ACTOR_TIME_LIMIT_MS`, `JM_MAX_RETRIES`, `JM_ABORT_TTL`, `JM_COMMAND_MAP`,
`JM_COMMAND_SHELL`. See [docs/reference/job-manager.md](../../../docs/reference/job-manager.md).

## Trade-offs (know these)

- **Ephemeral history** — records live for `JM_JOB_TTL`, then expire (Redis). Implement the
  `JobRepository` protocol against a durable store for audit history.
- **Final-only logs** — the captured stdout is available once the job is terminal; no live tail.
- **No monitoring UI** — Dramatiq ships none; observe via `/jobs*` and the Prometheus `jm_*` metrics.
- **Cancellation** is reliable for executors that emit output (checked between chunks) or `await` at
  cancellable points; a fully-blocking, no-output job isn't interrupted until it does.

Deeper design notes: [docs/explanation/job-manager.md](../../../docs/explanation/job-manager.md).
