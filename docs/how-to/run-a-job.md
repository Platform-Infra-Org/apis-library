# Run a job through the job manager

The job manager runs operations Ansible can't drive — on **any** system: SSH
targets, cloud CLIs, kubectl, custom scripts. The API enqueues; a separate
worker executes. Both need only **Redis**.

## 1. Install the extra

```bash
pip install "tashtiot-apis-library[job-manager]"
```

This pulls Dramatiq (the Redis broker) and `dramatiq-abort`. The base package
never requires them.

## 2. Mount the API onto your app

```python
from tashtiot_apis_library import general_create_app, enable_job_manager

app = general_create_app(enable_metrics_route=True)
enable_job_manager(app)          # includes the /jobs router; reads REDIS_URL from settings
```

API replicas only *enqueue* — `enable_job_manager` deliberately builds no
executor.

## 3. Run a worker

The worker executes the operations. The default executor is universal: it runs a
command per operation. Map operation names to commands with `JM_COMMAND_MAP` (a
JSON `{operation: argv}` object):

```bash
export REDIS_URL=redis://localhost:6379/0
export JM_COMMAND_MAP='{
  "drain_node": ["ssh", "{host}", "kubectl", "drain", "{node}"],
  "scale":      ["kubectl", "scale", "--replicas={n}", "deploy/{name}"]
}'

dramatiq tashtiot_apis_library.job_manager.tasks --processes 2 --threads 4
```

Each argv token is `{param}`-expanded from the request's `params` (other braces,
e.g. jsonpath `{.status}`, pass through). argv form (no shell) is the default and
avoids injection; set `JM_COMMAND_SHELL=true` only if you really need the shell.

Need a bespoke backend (a remoting protocol, an API client)? Write a small class
implementing the `Executor` protocol (`run(operation, params)` yielding stdout
chunks) and register it in your own worker module — the actor and routes don't
change:

```python
# myapp/worker.py  ->  dramatiq myapp.worker --processes 2 --threads 4
from tashtiot_apis_library.job_manager import CommandExecutor, tasks

tasks.set_executor(CommandExecutor(command_for={
    "drain_node": ["ssh", "{host}", "kubectl", "drain", "{node}"],
}))
from tashtiot_apis_library.job_manager.tasks import run_job  # noqa: F401 - registers the actor
```

## 4. Launch and poll

```bash
curl -i -X POST localhost:8000/jobs \
  -d '{"target": "host-1", "operation": "drain_node", "params": {"host": "host-1", "node": "n1"}}'
# 202 Accepted, Location: /jobs/<id>

curl localhost:8000/jobs/<id>/status              # {"status": "running"}
curl localhost:8000/jobs/<id>/logs                # captured stdout (once terminal)
curl -X POST localhost:8000/jobs/<id>/cancel      # cooperative abort
```

`target` is both what the operation acts on **and the serialization key**: two
jobs with the same `target` never run concurrently (the per-target lock).

From Python, with the AWX-mirrored client surface:

```python
from tashtiot_apis_library import JobManager
from tashtiot_apis_library.job_manager import JobRequest, RedisJobRepository
from tashtiot_apis_library.job_manager.broker import create_async_redis, setup_broker

setup_broker()                                 # so launch/cancel reach the broker
manager = JobManager(RedisJobRepository(create_async_redis()))

resp = await manager.launch_job(JobRequest(target="host-1", operation="drain_node",
                                           params={"host": "host-1", "node": "n1"}))
record = await manager.wait_for_job_completion(resp.job_id, timeout=300)
```

!!! note "Idempotent launches"
    Pass `idempotency_key` on the request to dedupe retried launches — the same
    key reuses the in-flight job instead of starting a second one.
