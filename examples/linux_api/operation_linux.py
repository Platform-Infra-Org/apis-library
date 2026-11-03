"""Replacement STATUS FUNCTIONS from the photographed Linux API module.

This is not the complete private operation_linux.py: the photos do not show
complete launch payloads. Copy these two functions into your existing module;
keep create_new_machine, delete_machine, launch_ssh_keys_job, other operations,
and their config import/payloads exactly as they are.
"""

from tashtiot_apis_library import AWX
from tashtiot_apis_library.connectors.awx.models import AWXOperationResponse


async def get_machine_status(
    awx: AWX,
    workflow_job_id: int,
) -> AWXOperationResponse:
    """Existing signature and response type, with a child-job summary in stdout."""
    return await awx.get_workflow_job_status(workflow_job_id, include_logs=True)


async def get_ssh_keys_job_status(
    awx: AWX,
    job_id: int,
) -> AWXOperationResponse:
    """Existing signature and response type, with a concise single-job summary."""
    return await awx.get_job_status(job_id, include_logs=True)
