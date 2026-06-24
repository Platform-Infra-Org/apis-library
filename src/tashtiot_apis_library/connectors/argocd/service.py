"""High level helpers for interacting with Argo CD."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

import yaml
from loguru import logger
from pydantic import BaseModel

from ..errors import ArgoCDError
from .client import ArgoCDClient
from .models import (
    ArgoApplication,
    ArgoApplicationEvaluation,
    ArgoApplicationSource,
    ArgoApplicationSpec,
    ArgoApplicationStatus,
    ArgoHelmSource,
    ArgoOperationResponse,
)

__all__ = ["ArgoCD", "logger", "evaluate_argo_result"]

# A list of Argo CD parameter entries, each a ``{"name": ..., "value": ...}`` mapping.
ParamList = List[Dict[str, str]]


@dataclass(frozen=True)
class _AppFingerprint:
    revision: Optional[str]
    reconciled_at: Optional[str]
    op_finished_at: Optional[str]
    history_len: int


def _load_status(
    status: Optional[Union[ArgoApplicationStatus, Mapping[str, object]]],
) -> ArgoApplicationStatus:
    if status is None:
        return ArgoApplicationStatus()
    if isinstance(status, ArgoApplicationStatus):
        return status
    return ArgoApplicationStatus.model_validate(status)


def _namespaces_to_list(raw: Any) -> List[str]:
    """Normalize a namespaces value (str/list/None) into a list of strings."""
    if raw is None:
        return []
    if isinstance(raw, str):
        return [ns.strip() for ns in raw.split(",") if ns and ns.strip()]
    if isinstance(raw, list):
        return [str(ns).strip() for ns in raw if str(ns).strip()]
    return []


def add_namespace(params, new_ns: str):
    """
    params : list[dict]   # your parameters list
    new_ns : str          # namespace you want to add
    """
    # 1?? locate the dict whose name ends with ".namespace"
    for p in params:
        if p["name"].endswith(".namespace"):
            # 2?? turn the current comma-separated string into a set
            cur = {ns.strip() for ns in p["value"].split(",") if ns.strip()}
            # 3?? add the new namespace (set removes duplicates automatically)
            cur.add(new_ns.strip())
            # 4?? write back a clean, comma-separated string
            p["value"] = ", ".join(sorted(cur))
            break
    else:
        params.append({"name": "applicationClusters[0].namespace", "value": new_ns})
    return params


def _as_parameter_list(parameters: Union[ParamList, Mapping[str, object]]) -> ParamList:
    if isinstance(parameters, Mapping):
        return [{"name": str(k), "value": str(v)} for k, v in parameters.items()]
    return [dict(p) for p in parameters]


def _fp_from_status(
    status: Optional[Union[ArgoApplicationStatus, Mapping[str, object]]],
) -> _AppFingerprint:
    parsed = _load_status(status)
    history: Sequence[object] = parsed.history or []
    return _AppFingerprint(
        revision=parsed.sync.revision if parsed.sync else None,
        reconciled_at=parsed.reconciled_at,
        op_finished_at=parsed.operation_state.finished_at if parsed.operation_state else None,
        history_len=len(history),
    )


def evaluate_argo_result(
    app_status: Optional[Union[ArgoApplicationStatus, Mapping[str, object]]],
) -> ArgoApplicationEvaluation:
    """
    Evaluate ArgoCD Application status and return an `ArgoApplicationEvaluation`.
    """
    status = _load_status(app_status)
    sync_status = status.sync.status if status.sync else None
    health_status = status.health.status if status.health else None
    phase = status.operation_state.phase if status.operation_state else None
    op_msg = status.operation_state.message if status.operation_state else ""

    import re

    def extract_namespace(msg: str) -> str | None:
        match = re.search(r'namespaces?\s+"([^"]+)"\s+not found', msg)
        return match.group(1) if match else None

    # 1️⃣ Explicit Argo operation failure
    if phase in {"Failed", "Error"}:
        ns = extract_namespace(op_msg)
        if ns:
            return ArgoApplicationEvaluation(result="FAILED", message=f"Namespace '{ns}' not found")
        if "forbidden" in op_msg or "permission" in op_msg:
            return ArgoApplicationEvaluation(result="FAILED", message="RBAC or permission denied")
        if "helm" in op_msg.lower() and (
            "render" in op_msg.lower() or "template" in op_msg.lower()
        ):
            return ArgoApplicationEvaluation(result="FAILED", message="Helm rendering error")
        return ArgoApplicationEvaluation(
            result="FAILED", message=op_msg or "ArgoCD operation failed"
        )

    # 2️⃣ Healthy and synced
    if sync_status == "Synced" and health_status == "Healthy":
        return ArgoApplicationEvaluation(
            result="SUCCESS", message="Application is healthy and synced"
        )

    # 3️⃣ OutOfSync or still reconciling
    if sync_status in {"OutOfSync", "Unknown"} or phase == "Running":
        return ArgoApplicationEvaluation(
            result="INPROGRESS",
            message=f"Application is progressing (Sync={sync_status}, Health={health_status})",
        )

    # 4️⃣ Missing or degraded health
    if health_status in {"Missing", "Degraded"}:
        ns = extract_namespace(op_msg)
        if ns:
            return ArgoApplicationEvaluation(result="FAILED", message=f"Namespace '{ns}' not found")
        return ArgoApplicationEvaluation(
            result="FAILED", message=f"Health={health_status}, Sync={sync_status}"
        )

    # 5️⃣ Fallback (still in progress)
    return ArgoApplicationEvaluation(
        result="INPROGRESS",
        message=f"Sync={sync_status}, Health={health_status}, Phase={phase}",
    )


class ArgoCD:
    """Convenience wrapper that offers higher level Argo CD interactions."""

    def __init__(self, base_url: str, api_key: str, application_set_timeout: int) -> None:
        self.client = ArgoCDClient(base_url, api_key)
        self.application_set_timeout = application_set_timeout

    async def _get_current_namespaces(
        self, cluster_secret_name: str
    ) -> Tuple[List[str], Dict[str, Any]]:
        """Fetch current values for the cluster-secret and return (namespaces, values).

        This is called each time we need to make a decision or a write, to avoid
        using stale data if other writers updated the secret concurrently.
        """
        parameters = await self.get_app_parameters(cluster_secret_name)
        namespaces_string = next(p for p in parameters if p["name"].endswith(".namespace"))
        namespaces = _namespaces_to_list(namespaces_string)
        return namespaces, parameters

    async def wait_for_update(self, app_name: str) -> ArgoApplication:
        """
        Wait until the ArgoCD Application shows a new update (revision or reconcile change).
        Returns the latest Application object when a change is detected.

        Uses self.application_set_timeout as the maximum wait time (in seconds).
        """

        await self.wait_for_app_creation(app_name)

        current = await self.client.get_app(app_name)
        baseline_fp = _fp_from_status(current.status)

        elapsed = 0
        while elapsed < self.application_set_timeout:
            await asyncio.sleep(1)
            elapsed += 1
            try:
                app = await self.client.get_app(app_name)
            except ArgoCDError as exc:
                if exc.status_code in (403, 404):
                    logger.info("Application {} disappeared while waiting for update", app_name)
                    raise TimeoutError(f"Application {app_name} no longer exists") from exc
                raise

            fp = _fp_from_status(app.status)
            if fp != baseline_fp:
                logger.info(
                    "Detected update for {} (revision: {} -> {}, reconciledAt: {} -> {})",
                    app_name,
                    baseline_fp.revision,
                    fp.revision,
                    baseline_fp.reconciled_at,
                    fp.reconciled_at,
                )
                return app

        raise TimeoutError(f"Timed out waiting for update on {app_name}")

    async def wait_for_app_deletion(self, app_name: str) -> None:
        """Wait until the given Argo CD application is deleted."""
        timeout = 0

        try:
            await self.client.get_app(app_name)
        except ArgoCDError as exc:
            if exc.status_code == 403:  # app no longer exists
                return None
            raise

        while timeout < self.application_set_timeout:
            logger.info("Waiting for {} to be deleted...", app_name)
            try:
                await self.client.get_app(app_name)
            except ArgoCDError as exc:
                if exc.status_code == 403:  # app no longer exists
                    return None
                raise
            await asyncio.sleep(1)
            timeout += 1

        raise TimeoutError(f"Timed out waiting for {app_name} to be deleted")

    async def wait_for_app_creation(self, app_name: str) -> None:
        timeout = 0
        while timeout < self.application_set_timeout:
            logger.info("Waiting for {} to be created...", app_name)
            try:
                await self.client.get_app(app_name)
                return None
            except ArgoCDError as exc:
                if exc.status_code != 403:
                    raise
                await asyncio.sleep(1)
                timeout += 1

        raise TimeoutError(f"Timed out waiting for {app_name}")

    async def sync(self, app_name: str) -> None:
        logger.info(f"Syncing {app_name}")
        await self.client.sync_app(app_name)

    async def get_app_status(self, app_name: str) -> ArgoOperationResponse:
        logger.info(f"Getting status for {app_name}")
        response = await self.client.get_app(app_name)
        evaluation = evaluate_argo_result(response.status)

        status_map = {
            "SUCCESS": "successful",
            "FAILED": "failed",
        }

        status_str = status_map.get(evaluation.result, evaluation.result.lower())

        return ArgoOperationResponse(
            status=status_str,
            status_code=200,
            app_name=app_name,
            stdout=evaluation.message,
        )

    async def get_app_values(self, app_name: str) -> str:
        logger.info("Getting ArgoCD app values for {}", app_name)
        response = await self.client.get_app(app_name)
        spec = response.spec
        if not spec or not spec.source or not spec.source.helm:
            return ""
        return spec.source.helm.values or ""

    async def modify_values(
        self,
        values: Union[BaseModel, Mapping[str, object]],
        app_name: str,
        namespace: str,
        project: str,
    ) -> None:
        logger.info(f"Modifying values for {app_name}")
        if isinstance(values, BaseModel):
            values_payload = values.model_dump(exclude_none=True)
        else:
            values_payload = dict(values)
        values_yaml = yaml.safe_dump(values_payload)

        spec = ArgoApplicationSpec(
            source=ArgoApplicationSource(
                helm=ArgoHelmSource(values=values_yaml),
            )
        )
        patch = ArgoApplication(spec=spec)

        await self.client.patch_app(patch, app_name, namespace, project)

    async def get_app_parameters(self, app_name: str) -> str:
        logger.info("Getting ArgoCD app parameters for {}", app_name)
        response = await self.client.get_app(app_name)
        spec = response.spec
        if not spec or not spec.source or not spec.source.helm:
            return ""
        return spec.source.helm.parameters or ""

    async def modify_parameters(
        self,
        parameters: Union[List[Dict[str, str]], Mapping[str, object]],
        app_name: str,
        namespace: str,
        project: str,
    ) -> None:
        """Create / update the Argo CD Application with a new Helm parameters list."""
        logger.info(f"Modifying parameters for {app_name}")
        param_list = _as_parameter_list(parameters)

        spec = ArgoApplicationSpec(
            source=ArgoApplicationSource(helm=ArgoHelmSource(parameters=param_list))
        )
        patch = ArgoApplication(spec=spec)

        await self.client.patch_app(patch, app_name, namespace, project)

    async def add_namespace_to_cluster_secret(
        self,
        cluster_secret_name: str,
        namespace: str,
        project: str,
    ) -> None:
        """Add namespace to cluster secret."""

        namespaces, parameters = await self._get_current_namespaces(cluster_secret_name)

        if namespace not in namespaces:
            parameters_after_adding = add_namespace(parameters, namespace)
            await self.modify_parameters(
                parameters_after_adding, cluster_secret_name, project, "default"
            )
            await self.sync(cluster_secret_name)
