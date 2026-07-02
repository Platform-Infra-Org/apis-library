# Job manager reference

General-purpose async job manager for operations Ansible can't drive (any
system). Dramatiq + Redis dispatches; a Redis-backed `JobRepository` is the sole
source of truth for status/result/history; plus a per-target lock and a pluggable
executor. Install via the `job-manager` extra.

## Endpoints

The router (mounted by [`enable_job_manager`][tashtiot_apis_library.job_manager.enable_job_manager],
default prefix `""`):

| Method | Path | Description |
|---|---|---|
| `POST` | `/jobs` | Launch a job. `202` + `{job_id, status}`; sets `Location: /jobs/{id}`. |
| `GET` | `/jobs` | List/history. Filters: `?status=`, `?target=`, `?limit=`, `?offset=`. |
| `GET` | `/jobs/{id}` | Full `JobRecord` (status is a field). |
| `GET` | `/jobs/{id}/status` | Lightweight `{status}` for cheap polling. |
| `GET` | `/jobs/{id}/logs` | Captured stdout (`text/plain`, the job result), once terminal. |
| `POST` | `/jobs/{id}/cancel` | Request a cooperative abort (`202`). |

Pass `known_operations=` to `enable_job_manager` (the set the worker's executor
handles) to reject unknown operations at launch with `422` instead of failing at
execution.

Health/readiness stay in the template's existing probes.

## Status vocabulary

`JobStatus`: `pending`, `running`, `succeeded`, `failed`, `cancelled`. The actor
writes every transition to the `JobRepository`, which is the only place status is
read from (Dramatiq itself tracks no status).

## Executors

Execution is behind the `Executor` Protocol (`run(operation, params) ->
AsyncIterator[str]`):

- **`CommandExecutor`** — runs a command per operation via `asyncio` subprocess,
  streaming stdout lines. `command_for` maps operation → argv list (or string);
  each token is `{param}`-expanded. No extra dependency.

Write your own `Executor` (a remoting client, an API call) for anything else;
the task and routes don't change.

## Public client (`JobManager`)

Mirrors the `AWX` connector:

- `launch_job(request) -> JobOperationResponse` — with an `idempotency_key`,
  a repeat launch **reuses** the existing job while it is `pending`/`running`
  (202 with the current status, nothing enqueued) and **creates a new run under
  the same id** once it is terminal; without a key every launch is a new job.
- `get_job(job_id) -> JobRecord`
- `get_job_status(job_id) -> JobStatusResponse`
- `list_jobs(*, target=None, status=None, limit=50, offset=0) -> list[JobRecord]`
  (full records; the HTTP route filters them to `JobSummary` rows via its
  `response_model`)
- `cancel_job(job_id) -> JobOperationResponse`
- `get_logs(job_id) -> str`  (the job result / captured stdout)
- `wait_for_job_completion(job_id, timeout=300, poll_interval=5) -> JobRecord`

## Settings

Added to `ApplicationSettings` (env / `.env`):

| Setting | Default | Purpose |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` | Broker, abort backend, lock, and record store. |
| `REDIS_MAX_CONNECTIONS` | `10` | Record-store Redis pool size. |
| `REDIS_SOCKET_TIMEOUT` | `5.0` | Record-store Redis socket timeout (s). |
| `JM_JOB_TTL` | `86400` | Seconds the JobRecord (status/result/history) is retained. Keep it well above the longest job runtime, or the record can expire mid-job and the terminal write is dropped (logged as a worker warning). |
| `JM_TARGET_LOCK_TIMEOUT` | `900.0` | Per-target lock auto-expiry (s); keep ≥ the actor time limit. |
| `JM_TARGET_LOCK_WAIT` | `30.0` | How long a job waits for the lock before failing (`status: failed`, counted under the `lock_timeout` metric label). |
| `JM_ACTOR_TIME_LIMIT_MS` | `600000` | Dramatiq actor time limit (ms); worker aborts longer jobs. |
| `JM_MAX_RETRIES` | `0` | Dramatiq retries per job (Dramatiq's own default of 20 is unsafe for non-idempotent jobs). |
| `JM_ABORT_TTL` | `90000` | Milliseconds an abort request is retained. |
| `JM_COMMAND_MAP` | `None` | JSON `{operation: argv}` for the command executor. |
| `JM_COMMAND_SHELL` | `false` | Run command ops via the shell (default argv, no shell). |

## Worker

```bash
dramatiq tashtiot_apis_library.job_manager.tasks --processes N --threads M
```

For a custom executor, write your own worker module that calls
`tasks.set_executor(...)` before importing the actor, and point Dramatiq at it.

!!! warning "No monitoring UI"
    Unlike SAQ, Dramatiq ships no official web UI. Observe jobs via this
    capability's own surface (`GET /jobs`, `/status`, `/logs`) and the Prometheus
    `jm_*` metrics on `/metrics`.
