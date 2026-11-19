# Async and the event loop

Everything in this library is asynchronous: the connectors, the outbound SSO client, the Remote
Config provider and the app factory's background tasks. This page explains what that means, why we
chose it over a synchronous design, and why it forces the async rules in
[API standards](../reference/api-standards.md#async-rules).

## What "async" means

A normal (**synchronous**) program does one thing at a time. When it calls another service over
the network, the thread **blocks** and does nothing until the reply arrives. To serve 50 requests at
once, a sync server needs about 50 threads or processes, and most of them spend their time idle.

An **asynchronous** program runs on an **event loop**, a single thread that juggles many tasks. When
a task reaches a slow I/O call and `await`s it, the task hands control back to the loop. The loop
then runs other tasks while the network or disk does its work, and resumes the first task when its
result is ready.

```python
# Sync: the thread is stuck for the full round-trip.
response = requests.get("https://awx/api/v2/jobs/42/")

# Async: while this request is in flight, the event loop serves other requests.
response = await client.get("/api/v2/jobs/42/")
```

| Term | Meaning |
|---|---|
| `async def` | Defines a **coroutine function**. Calling it returns a coroutine object; nothing runs until it is awaited or scheduled. |
| `await x` | "Pause me here until `x` finishes; let the loop run other things meanwhile." Only allowed inside `async def`. |
| Event loop | The scheduler that runs coroutines. uvicorn starts one per worker process. |
| Task | A coroutine scheduled on the loop (`asyncio.create_task(...)`) so it runs concurrently with others. |
| Blocking call | Anything that holds the thread without `await`ing (`time.sleep`, `requests.get`, a sync DB driver, heavy CPU work). |

!!! note
    Async is **concurrency, not parallelism**. It overlaps *waiting*, not *computing*. One event loop
    still uses one CPU core.

## Why async instead of sync APIs

Our APIs are **orchestrators**. A typical request validates input, then calls AWX, ArgoCD, Vault,
Bitbucket, the Config API or an SSO token endpoint, and returns. Almost all of the request time is
spent **waiting on other systems**, which is the case async is built for.

- **Throughput per pod:** One worker can hold hundreds of in-flight requests to slow back-ends
  without a thread for each, so we need fewer replicas and less memory.
- **Built-in fan-out:** Independent calls can run at the same time with `asyncio.gather`, so the
  request takes as long as the slowest call instead of the sum of all calls.
- **Cheap waiting:** `await asyncio.sleep(5)` inside a "wait for the AWX job" loop costs nothing.
  `time.sleep(5)` would block a whole worker.
- **Background work in-process:** Startup tasks such as the Remote Config allowlist poller run on the
  same loop as the request handlers.
- **One model end to end:** Mixing sync and async code forces thread hops and hides bugs. Being async
  everywhere keeps the model simple.

## How the library is async

- **Every connector method is a coroutine.** `AWX`, `ArgoCD`, `Git` and `Vault` expose only
  `async def` methods, so callers must `await` them
  ([Architecture](architecture.md#the-three-layer-connector-pattern)).
- **All outbound HTTP goes through `BaseAPI`**, a thin wrapper that builds an `httpx.AsyncClient`.
  Used as `async with BaseAPI(...) as client:`, it closes its connection pool when the block ends.
- **Git uses subprocesses asynchronously.** The `Git` connector runs `git` over SSH with
  `asyncio.create_subprocess_exec`, so even shelling out doesn't block the loop.
- **Waiting helpers poll with `asyncio.sleep`.** `AWX.wait_for_job_completion` and
  `ArgoCD.wait_for_app_creation` are examples. A long wait costs a sleeping coroutine, not a thread.
- **Outbound SSO and Remote Config are async too.** Token fetches and upstream config lookups are
  awaited, and their results are cached
  ([Authentication design](authentication.md#outbound-client_credentials-cached-and-refreshed)).
- **The app lifespan runs background coroutines.** `general_create_app` launches every coroutine in
  `app.state.async_background_tasks` at startup and cancels them on shutdown.

## Consequences: why the rules exist

Because one thread serves every request on a worker, **a single blocking call stalls all of them**.
A `time.sleep(5)` in one handler means no other request on that worker gets an answer for five
seconds. This is the reason behind each of the [async rules](../reference/api-standards.md#async-rules):

- **Sync I/O libraries are banned in async code.** `requests` and sync DB drivers block the loop.
  The async equivalents (`httpx`, async drivers) yield back to it.
- **Blocking work you can't avoid goes to a thread** with `asyncio.to_thread`. The loop then waits on
  the thread instead of being stuck inside the call.
- **Plain `def` handlers run in a thread pool.** FastAPI runs them in a pool of about 40 threads by
  default so they don't block the loop. That is fine for trivial CPU-only handlers, but using it as a
  way to call sync I/O just moves the bottleneck to the pool.
- **Every network wait needs a timeout.** An awaited call that never returns doesn't block other
  requests, but it holds its request open, and its connection, forever.
- **Tasks need a reference.** The loop holds only a weak reference to a task created with
  `asyncio.create_task`, so an unreferenced task can be garbage-collected mid-run (see
  [Job queues and long-running work](job-queues.md#in-process-background-tasks-are-not-a-queue)).
- **Don't start a loop inside the app.** `asyncio.run()` fails inside an already-running loop, and
  uvicorn already runs one.

## See also

- [API standards → Async rules](../reference/api-standards.md#async-rules): the mandatory rules.
- [Job queues and long-running work](job-queues.md): what to do when the work is too long to await
  in a request.
- [Drive AWX, ArgoCD & Vault](../how-to/use-awx-argocd-vault.md): awaiting connector calls in
  practice.
