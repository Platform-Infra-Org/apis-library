"""High-level AWX service with convenient methods for workflow and job operations."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict, Optional

from loguru import logger

from .client import AWXClient
from .models import AWXOperationResponse, AWXJobStatus

__all__ = ["AWX", "logger"]


def _http_code_from_awx_status(status: AWXJobStatus | str) -> int:
    """Map AWX job status (enum or string) to an HTTP status code.

    Prefer AWXJobStatus enum comparison; gracefully fall back to string matching.
    """
    status_enum: Optional[AWXJobStatus] = None

    if isinstance(status, AWXJobStatus):
        status_enum = status
    else:
        try:
            status_enum = AWXJobStatus(status)
        except Exception:
            # unknown value - normalize string and fall back to simple mapping
            s = str(status).lower()
            if s in ("pending", "waiting", "running"):
                return 202
            if s == "successful":
                return 200
            if s in ("failed", "error", "canceled"):
                return 500
            return 200

    if status_enum in (AWXJobStatus.PENDING, AWXJobStatus.WAITING, AWXJobStatus.RUNNING):
        return 202
    if status_enum == AWXJobStatus.SUCCESSFUL:
        return 200
    if status_enum in (AWXJobStatus.FAILED, AWXJobStatus.ERROR, AWXJobStatus.CANCELED):
        return 500

    return 200


class AWX:
    """High-level AWX service providing convenient workflow and job operations."""

    def __init__(self, base_url: str, token: str) -> None:
        """Initialize AWX service.

        Args:
            base_url: Base URL of AWX instance (e.g., "https://awx.example.com/api/v2")
            token: Authentication token
        """
        self.base_url = base_url
        self.client = AWXClient(base_url, token)

    async def launch_workflow_job(
        self,
        workflow_id: int,
        extra_vars: Optional[Dict[str, Any]] = None,
        inventory: Optional[int] = None,
        limit: Optional[str] = None,
    ) -> AWXOperationResponse:
        """Launch a workflow job.

        Args:
            workflow_id: Workflow template ID
            extra_vars: Extra variables to pass to the workflow
            inventory: Inventory ID (optional)
            limit: Limit string (optional)

        Returns:
            AWXOperationResponse object with workflow job details
        """
        logger.info(f"Launching workflow job from template {workflow_id}")
        job = await self.client.launch_workflow_job(
            workflow_id=workflow_id,
            extra_vars=extra_vars,
            inventory=inventory,
            limit=limit,
        )

        status_enum = job.status
        status = status_enum.value

        return AWXOperationResponse(
            status=status,
            status_code=_http_code_from_awx_status(status_enum),
            job_id=job.id,
            stdout=self.base_url + job.url,  # Workflow jobs typically don't have a single stdout
        )

    async def launch_job(
        self,
        job_template_id: int,
        extra_vars: Optional[Dict[str, Any]] = None,
        inventory: Optional[int] = None,
        limit: Optional[str] = None,
        credential: Optional[int] = None,
    ) -> AWXOperationResponse:
        """Launch a single job.

        Args:
            job_template_id: Job template ID
            extra_vars: Extra variables to pass to the job
            inventory: Inventory ID (optional)
            limit: Limit string (optional)
            credential: Credential ID (optional)

        Returns:
            AWXOperationResponse object with job details
        """
        logger.info(f"Launching job from template {job_template_id}")
        job = await self.client.launch_job(
            job_template_id=job_template_id,
            extra_vars=extra_vars,
            inventory=inventory,
            limit=limit,
            credential=credential,
        )

        status_enum = job.status
        status = status_enum.value

        return AWXOperationResponse(
            status=status,
            status_code=_http_code_from_awx_status(status_enum),
            job_id=job.id,
            stdout=job.result_stdout or "",
        )

    async def get_job_status(self, job_id: int) -> AWXOperationResponse:
        """Get the status of a single job.

        Args:
            job_id: Job ID

        Returns:
            AWXOperationResponse object with current job status
        """
        logger.debug(f"Getting status for job {job_id}")
        job = await self.client.get_job_status(job_id)

        status_enum = job.status
        status = status_enum.value

        return AWXOperationResponse(
            status=status,
            status_code=_http_code_from_awx_status(status_enum),
            job_id=job.id,
            stdout=job.result_stdout or "",
        )

    async def get_workflow_job_status(self, workflow_job_id: int) -> AWXOperationResponse:
        """Get the status of a workflow job.

        Args:
            workflow_job_id: Workflow job ID

        Returns:
            AWXOperationResponse object with current workflow status
        """
        logger.debug(f"Getting status for workflow job {workflow_job_id}")
        job = await self.client.get_workflow_job_status(workflow_job_id)

        status_enum = job.status
        status = status_enum.value

        return AWXOperationResponse(
            status=status,
            status_code=_http_code_from_awx_status(status_enum),
            job_id=job.id,
            stdout="",
        )

    async def _wait_for_completion(
        self,
        label: str,
        ref_id: int,
        fetch: Callable[[int], Awaitable[AWXOperationResponse]],
        timeout: int,
        poll_interval: int,
    ) -> AWXOperationResponse:
        """Poll ``fetch`` until the referenced job reports a terminal status."""
        logger.info(f"Waiting for {label} {ref_id} to complete (timeout={timeout}s)")

        elapsed = 0
        while elapsed < timeout:
            result = await fetch(ref_id)

            if result.status == "successful" or result.status == "failed":
                logger.info(f"{label} {ref_id} completed with status: {result.status}")
                return result

            logger.debug(
                f"{label} {ref_id} still running (status={result.status}), waiting {poll_interval}s"
            )
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise TimeoutError(f"{label} {ref_id} did not complete within {timeout} seconds")

    async def wait_for_job_completion(
        self,
        job_id: int,
        timeout: int = 300,
        poll_interval: int = 5,
    ) -> AWXOperationResponse:
        """Poll until a job completes or times out.

        Args:
            job_id: Job ID to monitor
            timeout: Maximum wait time in seconds (default: 300)
            poll_interval: Seconds between status checks (default: 5)

        Returns:
            AWXOperationResponse object with final status

        Raises:
            TimeoutError: If job doesn't complete within timeout
        """
        return await self._wait_for_completion(
            "Job", job_id, self.get_job_status, timeout, poll_interval
        )

    async def wait_for_workflow_completion(
        self,
        workflow_job_id: int,
        timeout: int = 300,
        poll_interval: int = 5,
    ) -> AWXOperationResponse:
        """Poll until a workflow job completes or times out.

        Args:
            workflow_job_id: Workflow job ID to monitor
            timeout: Maximum wait time in seconds (default: 300)
            poll_interval: Seconds between status checks (default: 5)

        Returns:
            AWXOperationResponse object with final status

        Raises:
            TimeoutError: If workflow doesn't complete within timeout
        """
        return await self._wait_for_completion(
            "Workflow job", workflow_job_id, self.get_workflow_job_status, timeout, poll_interval
        )
