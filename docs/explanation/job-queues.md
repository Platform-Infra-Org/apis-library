# Job queues and long-running work

Many of our operations take longer than an HTTP request should stay open: a playbook run, an ArgoCD
rollout, a multi-step change across Git, Vault and ArgoCD. This page explains the job-queue concept,
why AWX already gives you one, and what your options are when it doesn't fit. The resulting API
contract is listed in [API standards](../reference/api-standards.md#long-running-work).

## The concept

A **job queue** separates *accepting* work from *doing* work:

```
 client ──POST──▶ API ──enqueue(job)──▶ [ QUEUE ] ──▶ worker(s) ──▶ the actual work
   ▲               │                                       │
   │          202 {job_id}                          update job state
   └──GET /status/{job_id}──▶ API ──read state──▶ [ JOB STORE ] ◀┘
```

1. The API **validates** the request, **records** a job, **pushes** it to a queue, and immediately
   returns **`202 Accepted`** with a `job_id`.
2. One or more **workers** take jobs from the queue and do the slow work.
3. The client **polls** `GET .../status/{job_id}` (or receives a callback) until the job reaches a
   terminal status, such as `successful`, `failed` or `canceled`.

Why this shape matters:

- **HTTP has time limits.** Proxies, ingress and clients typically cut connections at 30–60 s. A
  playbook or an ArgoCD rollout can take minutes.
- **Durability:** a job in a queue survives an API pod restart or deploy. A request handler or an
  in-memory task does not.
- **Back-pressure:** a burst of 500 requests becomes 500 queued jobs worked through at a
  controlled rate. It does not become 500 simultaneous executions.
- **Retries:** failed jobs can be retried without the client resubmitting.
- **Independent scaling:** workers scale separately from the API, and any API replica can answer
  the status call.

Queues usually deliver a job **at least once**, so the same job can run twice. The work a job does
must therefore be **idempotent**: running it twice has the same effect as running it once.

## AWX is already a job queue

**AWX works exactly like a job queue.** When an API calls `awx.launch_job(...)`:

- AWX **records** the job and returns a `job_id` immediately. The job is `pending`/`waiting` in
  AWX's own queue.
- AWX's execution nodes act as the **workers**: they pick the job up and run it (`running`).
- AWX **stores the job state and output** (`successful` / `failed` / `error` / `canceled`), and it
  survives restarts of your API.
- Your API reads that state with `awx.get_job_status(job_id)`, or streams output with
  `awx.get_job_output(...)`.

So **an API that launches AWX jobs and exposes a status route is already using a job queue.** It
doesn't need another one. The DNS module in `example-api` follows this pattern: `POST /dns/`
launches the job and returns its `job_id`, and `GET /dns/status/{job_id}` reads it back from AWX.

This is also why the connector's launch response says `status="successful"`: AWX *accepted* the job
into its queue, but the job isn't done yet. The status call maps AWX states to a `status_code` in the
response body: `pending`/`waiting`/`running` → 202, `successful` → 200, `failed`/`error`/`canceled` → 500.
Your status route still answers with HTTP 200: a failed job is a result the client asked for, not
an error in your API.

ArgoCD behaves in a similar asynchronous way: you request a sync, ArgoCD reconciles in the
background, and you poll `get_app_status`. The HAProxy module in `example-api` works like this.

## When you need your own queue

If the slow work runs **inside your API**, rather than in AWX or ArgoCD, and it must survive
restarts, be retried or be rate-limited, you need a job queue of your own.

!!! warning "There is no job queue in the library (for now)"
    `tashtiot-apis-library` does not ship a job-queue implementation. A team that needs one must
    either **implement it** or **use an external solution**, such as a message broker with a
    task-queue library. Another option is to model the work as an **AWX job or workflow**, which
    gives you the queue for free.

Whichever option a team chooses, a working queue gives you:

- **Durable jobs** that survive restarts.
- A **job id** and a **status** that any API replica can read, so the API can keep the same
  `202` + `GET .../status/{job_id}` contract as the AWX case.
- **Retries** for transient failures (timeouts, 5xx, 429), with backoff and a maximum number of
  attempts. Validation or permission errors won't succeed on retry, so they aren't retried.
- A **timeout** per job.
- Somewhere to keep failed jobs for inspection.

A worker is just another entry point into the same code. It builds the connectors once and calls the
same `operations.py` functions the API would.

## In-process background tasks are not a queue

`asyncio.create_task(...)` (or FastAPI's `BackgroundTasks`) runs work after the response is sent,
**inside the API process**. The HAProxy module in `example-api` does this for the ArgoCD wait and
sync. It is fine for short, best-effort work, but it gives you none of the queue guarantees:

- **The task is lost on restart, deploy or OOM.** Any rollback it would have run never happens,
  which can leave Git and Vault half-applied.
- **The task lives in one replica.** A status route can't ask another replica about it, so status
  must come from the external systems. The HAProxy status route asks ArgoCD for this reason.
- **No retries, no back-pressure.**
- **The loop holds only a weak reference to the task.** If nothing else references it, it can be
  garbage-collected mid-run. Keep tasks in a set until they finish:
    ```python
    _background_tasks: set[asyncio.Task] = set()

    def spawn(coro) -> None:
        task = asyncio.create_task(coro)
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    ```
- **Nobody awaits the task**, so an exception that isn't caught and logged inside it disappears.

## Choosing

| The work… | Use |
|---|---|
| Finishes in well under ~5 s | **Inline:** await it in the request |
| Runs as an **AWX job** (or an ArgoCD sync) | **AWX/ArgoCD as the queue:** launch it, return 202 + the id, expose a status route |
| Is short, best-effort, and acceptable to lose on restart (a notification, a cache warm-up) | **An in-process background task** |
| Is long, runs inside your API, and must not be lost, needs retries or must be rate-limited | **Your own job queue**, either implemented by the team or an external solution |
| Is periodic (a poller or sync loop) | **`general_create_app(async_background_tasks=[...])`**. One copy runs per replica, so make it idempotent. |

## See also

- [API standards → Long-running work](../reference/api-standards.md#long-running-work): the
  required API contract.
- [Async and the event loop](async.md): why long work can't simply be awaited in the request.
- [Drive AWX, ArgoCD & Vault](../how-to/use-awx-argocd-vault.md): launching, polling and streaming
  AWX jobs.
