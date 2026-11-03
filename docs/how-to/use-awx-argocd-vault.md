# Drive AWX, ArgoCD & Vault

Recipes for the remaining three connectors. All methods are async; construct each client with its
base URL and a token.

## AWX — launch a job and await it

```python
from tashtiot_apis_library import AWX

awx = AWX(base_url="https://awx.example.com", token="token")

# Launch a job template; returns an AWXOperationResponse (carries job_id)
response = await awx.launch_job(job_template_id=1, extra_vars={"env": "prod"})

# Block until it finishes, then inspect the standardized result
result = await awx.wait_for_job_completion(response.job_id)
if result.status == "successful":
    print(f"Job {result.job_id} finished!")
```

`launch_workflow_job` / `wait_for_workflow_completion` do the same for workflow job templates, and
`get_job_status(job_id)` polls a single status.

!!! tip "Standardized responses"
    Service methods return `OperationResponse` subclasses, not raw API payloads. The base carries
    `status`, `status_code`, `return_code`, and `stdout`; `AWXOperationResponse` adds `job_id` and
    `ArgoOperationResponse` adds `app_name`. See the [Schemas reference](../reference/api/schemas.md).

## ArgoCD — sync an app and wait for it

```python
from tashtiot_apis_library import ArgoCD

argo = ArgoCD(
    base_url="https://argo.example.com",
    api_key="token",
    application_set_timeout=30,  # seconds to wait for sync/delete
)

await argo.sync("my-app")
app = await argo.wait_for_update("my-app")  # ArgoApplication once healthy/synced
status = await argo.get_app_status("my-app")  # ArgoOperationResponse
```

Other helpers include `wait_for_app_creation`, `wait_for_app_deletion`, `get_app_values`,
`modify_values`, `get_app_parameters`, and `modify_parameters`.

## Vault — read and write secrets

```python
from tashtiot_apis_library import Vault

vault = Vault(base_url="https://vault.example.com", token="token")

secret = await vault.read_secret("secret/data/myapp")  # VaultSecret (.data, .metadata)
await vault.write_secret("secret/data/myapp", {"api_key": "value"})
await vault.delete_secret("secret/data/myapp")
```

`write_secret` accepts a plain mapping, a `VaultSecretPayload`, or any Pydantic model (it is dumped
to a dict, dropping `None`s).

## Errors

Each connector raises its own typed error on `4xx`/`5xx` — `AWXError`, `ArgoCDError`, `VaultError` —
all subclasses of `ExternalServiceError(HTTPException)`. Import them from
`tashtiot_apis_library.connectors.errors`.

## See also

- [Connectors API reference](../reference/api/connectors.md)
- [Read & write Bitbucket files](read-write-bitbucket.md)

## Incremental AWX playbook output for an Argo dispatcher

`get_job_output` is an opt-in method for **single playbook jobs**, including jobs launched
by the CloudCore/Linux APIs. An Argo Workflow and an AWX workflow job are different:
this method does not aggregate child jobs of an AWX workflow job.

```python
chunk = await awx.get_job_output(job_id, start_line=0, page_size=100)
# Serialize chunk with model_dump(mode="json") in your API.
# On the dispatcher: print chunk.stdout, then retain chunk.next_line per job.
```

The response includes existing `status`, `status_code`, `job_id`, `stdout` fields plus:

- `next_line`: the next AWX stdout position; send it as `start_line` on the next request.
- `has_more`: another page or a gap in arriving events requires another fetch.
- `finished`: the job is terminal, AWX reports `event_processing_finished=true`,
  and this chunk drains the available output. **Print this chunk before stopping.**

An API may expose a separate output endpoint returning HTTP 200 for successful reads,
with job status in the JSON. The `status_code` field remains the existing AWX status
mapping; it is not the transport status of this separate output endpoint. Keep the existing status endpoint unchanged. The dispatcher
must stop on `finished`, not merely a successful job status, and determine its final exit
code from `status`. Failed/canceled jobs can still have output to drain. Network/auth errors
are request failures; do not advance the cursor on them. Retain a total wait timeout,
including while waiting for late output or missing processing metadata.

The implementation reads one page from `/api/v2/jobs/{id}/job_events/`, ordered by stdout
position, and advances only through contiguous lines. Empty reads leave the cursor unchanged.
Drain pages immediately while `has_more` is true and `next_line` advances. If the cursor
does not advance (a gap), sleep before retrying to avoid a busy loop. Zero-line events are
filtered before pagination so they cannot block the cursor.
Page size bounds the number of events, not their byte size. AWX output is returned explicitly;
the library does not automatically log playbook output or expose `event_data`/variables.
Output can itself contain sensitive playbook values, so use the same access restrictions
as the existing job and AWX's `no_log` protections. Cursors are job-specific; persist them
outside the process if the dispatcher must resume after a restart. This is not exactly-once
delivery across crashes.

The API must authorize access to each job, just as the status endpoint does. No AWX token
is passed to the dispatcher. A FastAPI response model must preserve the new fields rather
than downcast to `AWXOperationResponse`.

### Local check without AWX or Tyk

```bash
DEBUG=false .venv/bin/pytest tests/connectors/test_awx_output.py tests/connectors/test_awx_client.py --no-cov
DEBUG=false PYTHONPATH=src .venv/bin/python examples/awx_output_demo.py
```

The demo uses mocked AWX HTTP responses and an in-process FastAPI endpoint, then prints
three incremental chunks from a dispatcher-like HTTP client. The simulated playbook adds
these chunks while the dispatcher sleeps; the dispatcher then drains multiple pages
without sleeping again. The GitHub checks workflow also runs this simulation. It needs the dev dependencies.
This validates the library and proposed HTTP contract, not the closed-network API or Tyk.
Before promotion, verify the deployed AWX exposes `start_line`, `end_line`,
`event_processing_finished`, supports the event filters, and permits the API token to read
job events. Older versions lacking completion metadata will time out rather than silently
claim all output was delivered.

The event ordering/completion approach follows the
[AWX CLI monitor](https://github.com/ansible/awx/blob/devel/awxkit/awxkit/cli/stdout.py).

## Concise status summaries (jobs and workflow jobs)

For the Linux API/Dispatcher integration that already prints response bodies, use
`include_logs=True` on the **existing status methods**:

```python
# Inside your existing JOBSTATUS handler; return the result as before.
result = await awx.get_workflow_job_status(workflow_job_id, include_logs=True)
# Or, for a standalone playbook job:
result = await awx.get_job_status(job_id, include_logs=True)
```

Both still return `AWXOperationResponse`, with the same status and HTTP-code mapping.
The optional summary fills `stdout`; the default (`False`) preserves existing behavior.
Keep your API's existing authentication and response-code handling. There is no need
for a new endpoint or cursor in the dispatcher for this snapshot mode. The dispatcher
must display the response's `stdout` (its existing response-body logging may show it as
JSON with escaped newlines; printing `stdout` separately gives readable lines).

Example workflow `stdout`:

```text
[✓] Create VM: successful
[✓] Configure Linux: successful
[✗] Install monitoring: failed
  TASK [Install monitoring agent]
  fatal: [server-01]: FAILED!
    → No package monitoring-agent available
  PLAY RECAP *********************************************************************
  server-01 : ok=4 changed=2 unreachable=0 failed=1 skipped=0 rescued=0 ignored=0
```

Workflow summaries list started child jobs and fetch the last ten filtered lines only
for failed, errored, or canceled playbook jobs. Project-update nodes are skipped.
Nested workflow jobs are traversed, with cycle/depth protection. Other node types show
status only; nodes without a job or job summary are omitted. Node pages are read in ID
order (not a chronological merge of parallel output), up to 100 pages of 100 nodes.
Standalone jobs show their heading plus the last two recap lines on success, or ten
filtered lines on failure/error/cancellation. Pending/running states use a neutral icon.

The filter retains play/task headers, action results, warnings, errors, short messages,
and play recap. It strips ANSI colors and omits verbose module result bodies. It keeps
at most 100 selected lines and 10,000 characters per filtered log and caps the combined
workflow summary at 10,000 characters with a truncation marker. These are output limits;
AWX's plain-text stdout response is still fetched in full. This is a presentation filter,
**not secret redaction**: task names and messages may still include sensitive data.

This is a **snapshot summary**, not incremental streaming: repeated polls may repeat
headings/output, successful workflow children do not include their full playbook output,
and the existing status completion does not wait for late AWX event processing.
Use `get_job_output` when incremental, fully drained single-job output is required.
Optional log/node retrieval errors produce an unavailable marker and a warning while
preserving the primary status. Errors fetching the primary status still raise normally.

Preview locally without AWX/Tyk:

```bash
DEBUG=false PYTHONPATH=src .venv/bin/python examples/awx_status_summary_demo.py
```

AWX exposes [workflow nodes and job stdout through its API](https://docs.ansible.com/projects/awx/en/latest/rest_api/api_ref.html).
The API's AWX token must have permission to read those resources.
