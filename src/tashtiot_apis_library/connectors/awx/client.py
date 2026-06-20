"""Low-level AWX HTTP API client for workflow and job operations."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from ...fastapi_template.utils import BaseAPI
from ..errors import AWXError
from .models import (
    AWXJob,
    AWXLaunchJobRequest,
    AWXLaunchWorkflowRequest,
    AWXWorkflowJob,
)

__all__ = ["AWXClient"]


def _parse_response_message(response_json: Dict[str, Any]) -> Optional[str]:
    """Extract error message from AWX response."""
    if isinstance(response_json, dict):
        # Try various common error message fields
        for key in ["detail", "message", "error", "msg"]:
            if key in response_json:
                msg = response_json[key]
                if isinstance(msg, str):
                    return msg
                elif isinstance(msg, dict):
                    return json.dumps(msg)
    return None


def _handle_response(response_json: Dict[str, Any], status_code: int) -> None:
    """Parse and handle AWX API error responses.

    Args:
        response_json: Response JSON data
        status_code: HTTP status code

    Raises:
        AWXError: If status code indicates an error
    """
    message = _parse_response_message(response_json)

    if status_code == 400:
        raise AWXError(
            status_code=status_code,
            detail=f"Bad request. {message or ''}",
        )

    if status_code == 401:
        raise AWXError(
            status_code=status_code,
            detail=f"Authentication failed. {message or 'Invalid token.'}",
        )

    if status_code == 403:
        raise AWXError(
            status_code=status_code,
            detail=f"Permission denied. {message or ''}",
        )

    if status_code == 404:
        raise AWXError(
            status_code=status_code,
            detail=f"Resource not found. {message or ''}",
        )

    if status_code >= 400:
        detail = f"AWX API error (status {status_code})."
        if message:
            detail += f" Message: {message}"
        raise AWXError(status_code=status_code, detail=detail)


class AWXClient:
    """Low-level client for AWX HTTP API."""

    def __init__(self, base_url: str, token: str) -> None:
        """Initialize AWX API client.

        Args:
            base_url: Base URL of AWX instance (e.g., "https://awx.example.com/api/v2")
            token: Authentication token
        """
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self.api = BaseAPI(base_url.rstrip("/"), headers=headers).client

    async def launch_workflow_job(
        self,
        workflow_id: int,
        extra_vars: Optional[Dict[str, Any]] = None,
        inventory: Optional[int] = None,
        limit: Optional[str] = None,
    ) -> AWXWorkflowJob:
        """Trigger a workflow job.

        Args:
            workflow_id: Workflow template ID
            extra_vars: Extra variables to pass to the workflow
            inventory: Inventory ID (optional)
            limit: Limit string (optional)

        Returns:
            AWXWorkflowJob object with workflow job details
        """
        uri = f"/api/v2/workflow_job_templates/{workflow_id}/launch/"

        payload: Dict[str, Any] = {}
        if extra_vars:
            payload["extra_vars"] = json.dumps(extra_vars)
        if inventory:
            payload["inventory"] = inventory
        if limit:
            payload["limit"] = limit

        response = await self.api.post(uri, content=json.dumps(payload))
        response_json = response.json()
        _handle_response(response_json, response.status_code)

        return AWXWorkflowJob.model_validate(response_json)

    async def launch_job(
        self,
        job_template_id: int,
        extra_vars: Optional[Dict[str, Any]] = None,
        inventory: Optional[int] = None,
        limit: Optional[str] = None,
        credential: Optional[int] = None,
    ) -> AWXJob:
        """Trigger a single job.

        Args:
            job_template_id: Job template ID
            extra_vars: Extra variables to pass to the job
            inventory: Inventory ID (optional)
            limit: Limit string (optional)
            credential: Credential ID (optional)

        Returns:
            AWXJob object with job details
        """
        uri = f"/api/v2/job_templates/{job_template_id}/launch/"

        payload: Dict[str, Any] = {}
        if extra_vars:
            payload["extra_vars"] = json.dumps(extra_vars)
        if inventory:
            payload["inventory"] = inventory
        if limit:
            payload["limit"] = limit
        if credential:
            payload["credential"] = credential

        response = await self.api.post(uri, content=json.dumps(payload))
        response_json = response.json()
        _handle_response(response_json, response.status_code)

        return AWXJob.model_validate(response_json)

    async def get_job_status(self, job_id: int) -> AWXJob:
        """Get the status of a single job.

        Args:
            job_id: Job ID

        Returns:
            AWXJob object with current job status
        """
        uri = f"/api/v2/jobs/{job_id}/"

        response = await self.api.get(uri)
        response_json = response.json()
        _handle_response(response_json, response.status_code)

        return AWXJob.model_validate(response_json)

    async def get_workflow_job_status(self, workflow_job_id: int) -> AWXWorkflowJob:
        """Get the status of a workflow job.

        Args:
            workflow_job_id: Workflow job ID

        Returns:
            AWXWorkflowJob object with current workflow status
        """
        uri = f"/api/v2/workflow_jobs/{workflow_job_id}/"

        response = await self.api.get(uri)
        response_json = response.json()
        _handle_response(response_json, response.status_code)

        return AWXWorkflowJob.model_validate(response_json)
