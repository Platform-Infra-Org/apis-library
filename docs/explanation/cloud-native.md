# Cloud-native APIs and multiple replicas

Our APIs run on Kubernetes (OpenShift) as **several identical replicas** of the same container.
This page explains what that means for how an API is written, and why the
[API standards](../reference/api-standards.md#multiple-replicas) insist on stateless,
idempotent code.

## What a replica is

A Deployment runs **N pods** from the same image. A Service in front of them spreads incoming
requests across the pods:

```
                         ┌──▶ pod A  (uvicorn, one event loop, own memory)
client ──▶ Service / LB ─┼──▶ pod B  (uvicorn, one event loop, own memory)
                         └──▶ pod C  (uvicorn, one event loop, own memory)
```

The platform runs several replicas for:

- **Availability:** a pod can die, be evicted or be rescheduled to another node at any moment, and
  the others keep serving.
- **Zero-downtime deploys:** a rolling update replaces pods one at a time, so for a while **the old
  and new versions run side by side**.
- **Scale:** more load means more pods, either set by hand or by an autoscaler.

The key fact: **pods share nothing.** Each has its own memory, its own event loop, its own
filesystem and its own background tasks. Two consecutive requests from the same client can land on
different pods.

## Consequences for API code

### Keep state out of the process

Anything stored in a Python variable is visible to **one** pod only, and only until that pod
restarts. So:

- **Don't keep the source of truth in memory.** This covers job status, "in progress" flags,
  sessions, counters and anything a later request needs. A `POST` on pod A followed by a
  `GET .../status` on pod B must work. Status comes from the system that owns it (AWX, ArgoCD, Git,
  Vault) or from a shared store, which is why the
  [job-queue page](job-queues.md#in-process-background-tasks-are-not-a-queue) derives status from
  the external system.
- **Caches are fine, as long as they are only caches.** The library caches SSO tokens, JWKS keys
  and Remote Config responses **per pod**. That is safe because a miss simply refetches. A cache
  must never hold the only copy of something.
- **The local filesystem is ephemeral and private to the pod.** Don't write files that another
  request or a restart needs. Mounted read-only secrets (for example the Git SSH key) are fine.

### Expect the same work to arrive twice, on different pods

Clients and proxies retry, users double-click, and a request can time out on pod A and be retried
on pod B. Two pods can also handle "create X" for the same name **at the same moment**.

- **Make operations idempotent:** a repeated create, update or delete has the same end result
  (see [API standards → Multi-step operations](../reference/api-standards.md#multi-step-operations)).
- **Use deterministic names**, derived from the request, so a retry targets the same resource.
- **Let the external system arbitrate.** An `asyncio.Lock` only serializes requests inside one
  pod, so it can't stop a race between two pods. Rely on the upstream's own conflict detection:
  the `Git` connector's `add_file` raises `GitError` with status 409 when the path already exists,
  and ArgoCD's `create_app` (with the default `upsert=False`) rejects an Application that already
  exists with a different spec. Translate those conflicts into `409`.
- **Check-then-write is a race across replicas.** "Read the secret, and if it is absent, write it"
  can interleave between two pods. Accept that, and keep the write itself idempotent, or move the
  guard into a system that offers an atomic operation.

### Background tasks run once per replica

Every coroutine in `general_create_app(async_background_tasks=[...])` starts on **every** pod.

- **Read-only, idempotent loops are fine.** The Remote Config allowlist poller runs N times, which
  just means N refreshes.
- **Work that must happen once** ("clean up expired X every hour", "send the daily report") must
  not be an in-process loop, or it runs N times. Use something that runs once by design: a
  Kubernetes CronJob, an AWX schedule, or a job queue with a single consumer.
- **A task started with `asyncio.create_task` dies with its pod.** A rolling update kills pods on
  purpose, so anything that must finish belongs in AWX or a job queue
  ([Job queues and long-running work](job-queues.md)).

### Start fast, stop cleanly

Pods are started and stopped all the time, so both have to be cheap and safe:

- **Startup:** configuration errors should fail fast, and they do: required settings and auth
  misconfiguration stop the app at creation. Heavy work doesn't belong at import time.
- **Shutdown:** Kubernetes sends `SIGTERM`, waits for the grace period (30 s by default), then
  kills the pod. uvicorn stops accepting connections and lets in-flight requests finish, and the
  library's lifespan cancels background tasks. Keep requests short (long work goes to a job), so
  they finish within the grace period.
- **Probes:** `/liveness` answers "is the process alive?", and `/readiness` answers "should this pod
  get traffic?". The library serves both and excludes them from auth and request logging. They
  report the process only, not the upstreams. Don't make liveness depend on AWX or Vault, or an
  upstream outage would make Kubernetes restart every pod at once.

### Two versions run at the same time

During a rolling update, pods of version *n* and *n+1* serve traffic together, and a client may hit
both within one workflow.

- Changes must be **backward compatible** for at least one release: new request fields are
  optional, and a response field isn't removed or renamed in place.
- Breaking changes go in a **new API version** (`/v2/...`) next to the old one
  ([API standards → Paths and versioning](../reference/api-standards.md#paths-and-versioning)).
- New background behaviour and new upstream writes must be safe while old pods are still running.

### Observability is per pod

- **Logs** go to stdout (the library configures Loguru that way). The platform collects them from
  every pod, so never write log files. Include identifiers (`job_id`, `app_name`,
  `metadata.project`) so one operation can be followed across pods.
- **Metrics** at `/metrics` describe **one pod**. Prometheus scrapes each pod separately, so
  dashboards aggregate across pods (`sum by (...)`), and a per-pod counter on its own is not the
  API's total.

### Scale with replicas, not processes

Run **one uvicorn process per pod** (as `example-api`'s `CMD` does) and let Kubernetes add pods.
Several worker processes inside one pod have the same no-shared-memory consequences as replicas,
while hiding them from the platform's scheduling, probes and resource limits.

## See also

- [API standards → Multiple replicas](../reference/api-standards.md#multiple-replicas): the rules.
- [Job queues and long-running work](job-queues.md): why durable work leaves the process.
- [Async and the event loop](async.md): concurrency inside one pod.
