# Job manager architecture

Ansible can't drive every operation we need — some targets have no usable
SSH/WinRM module, some workflows need imperative, stateful control. The job
manager is an AWX-like async execution layer for exactly those: general-purpose
(any system reachable by a command or a remoting protocol), async-native, thin
(no Kafka/RabbitMQ), and horizontally scalable.

## Dispatch: Dramatiq + Redis

A [Dramatiq](https://dramatiq.io) `RedisBroker` handles enqueue and execution.
Dramatiq is fire-and-forget — `run_job.send(...)` drops a message and returns;
the worker picks it up. The `Abortable` middleware (backed by Redis) carries
cancellation. All of it — broker, abort backend, lock, record store — points at
the one `REDIS_URL`.

- **API replicas** call `launch_job`, which writes a `pending` record **then**
  `send`s the message (so the worker can never start before the record exists).
  They never block on results.
- **Worker replicas** (a separate Deployment, HPA'd on OpenShift) run the actor.
  Scale the two independently with `dramatiq ... --processes N --threads M`.

## Execution: a pluggable `Executor`

Execution sits behind the `Executor` Protocol, so the manager is not bound to
any one system:

- **`CommandExecutor`** runs a command per operation via `asyncio` subprocess
  and streams stdout lines. That covers anything you can invoke from a command:
  `ssh`, `kubectl`, cloud CLIs, scripts, remoting clients — with **no extra
  dependency**. argv form (no shell) is the default, so params can't inject
  shell syntax.
- Anything bespoke (a remoting protocol, an API client) is a small class
  implementing `run(operation, params)`.

## State: the JobRepository is the sole source of truth

Dramatiq tracks **no** status — it's fire-and-forget. So the `JobRepository`
(Redis-backed by default) is the only place job state lives, and the **actor
writes every transition**: `pending` (at launch) → `running` (actor start) →
`succeeded` / `failed` / `cancelled` (terminal). Two edge writes happen on the
service side instead, because the actor never runs for them: a failed enqueue
marks the record `failed`, and cancelling a still-queued job marks it
`cancelled`. Routes read **only** from the repository; they never inspect
Dramatiq.

- **Reads** (`GET /jobs/{id}`, `/status`, `cancel`, `wait`) → `repository.get`.
- **Listing** (`GET /jobs`) → `repository.list`, filtered by target/status.
- **Logs** → the actor returns its stdout; the repository stores it as the
  record's `result`; `GET /jobs/{id}/logs` returns it.
- **Cancel** → the record stores the Dramatiq `message_id`; `cancel_job` maps
  `job_id → message_id` and calls `dramatiq_abort.abort(...)`. If the job is
  still queued the actor never runs (the middleware skips the message), so
  `cancel_job` writes the terminal `cancelled` itself.

**Trade-offs, stated plainly:**

- This is the cost of leaving SAQ: SAQ persisted status/result for free, so the
  repository (record store + index + status writes) had to be **rebuilt**.
- History is **ephemeral** — the record lives for `JM_JOB_TTL`, then expires.
  Implement the `JobRepository` Protocol against a durable store for audit history.
- Logs are the **final** stdout, available once terminal — no live tail.
- Filtering a listing scans the index and filters in Python — fine at the
  expected (TTL-bounded) volume.

## Per-target serialization

Every job runs under `async with target_lock(redis, target):` — a thin wrapper
over `redis.asyncio`'s native `Lock` (no custom Redlock). Two operations on the
same target never overlap, across any number of workers. `target` is whatever
identifies the resource (a host, a cluster, an account).

The lock auto-expires (`JM_TARGET_LOCK_TIMEOUT`, default 900s) so a crashed
worker can't wedge a target forever; keep it **≥ the actor time limit**
(`JM_ACTOR_TIME_LIMIT_MS`, default 600s) so it can never lapse while a job is
still running (which would let a second worker in). A job waits
`JM_TARGET_LOCK_WAIT` seconds to acquire the lock; if a target is busy longer
than that, the waiting job ends `failed` (with the error "could not acquire
target lock") and is counted under the distinct `lock_timeout` metric label,
rather than queueing indefinitely. Size `JM_TARGET_LOCK_WAIT` for your expected
per-target burst.

## Retries and cancellation

Operations are generally **non-idempotent**, so the actor sets `max_retries=0`
(`JM_MAX_RETRIES`) — Dramatiq's own default of 20 would silently re-run a job.
Raise it only for provably idempotent operations.

Cancellation uses **two paths**: the actor polls `abort_requested(message_id)`
**between output chunks** (cooperative — reliable for a streaming executor), and
the `Abortable` middleware also interrupts the running async actor (raising
`Abort` / cancelling the task) for jobs blocked mid-`await`. Either way the actor
tears the work down (the `CommandExecutor` kills its child process via a
`finally`) and writes `cancelled`, shielding that write from the task
cancellation. **Caveat:** a fully-blocking executor that produces no output and
never `await`s a cancellable point can't be interrupted until it does — verified
in the e2e that a chunk-emitting job cancels promptly.

## Observability

Prometheus metrics register on the default registry and surface on the
template's existing `/metrics`: `jm_jobs_total{status}` (counter),
`jm_jobs_inflight` (gauge), `jm_job_duration_seconds` (histogram). Every job log
binds `job_id` into the Loguru context.

## Scaling & HA

API replicas enqueue; worker replicas execute. For broker HA, run Redis
**Sentinel** or **Cluster** behind `REDIS_URL`.
