"""Low level client that wraps the Argo CD REST API."""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping, Optional, Union

from pydantic import BaseModel

from ...fastapi_template.utils import BaseAPI
from ..errors import ArgoCDError
from .models import ArgoApplication

__all__ = ["ArgoCDClient"]


def _parse_response_message(response_json: Mapping[str, Any]) -> str | None:
    message = response_json.get("message")
    if isinstance(message, Mapping):
        return json.dumps(message)
    if isinstance(message, str):
        return message
    return None


def _handle_response(response_json: Mapping[str, Any], status_code: int) -> None:
    message = _parse_response_message(response_json)

    if status_code == 307:
        raise ArgoCDError(
            status_code=status_code,
            detail="ArgoCD endpoint is redirecting. "
            + (f"ArgoCD message: {message}" if message else ""),
        )

    if status_code == 403:
        raise ArgoCDError(
            status_code=status_code,
            detail="Don't have permission to access this resource, "
            "or this resource doesn't exist." + (f" ArgoCD message: {message}" if message else ""),
        )

    if status_code >= 400:
        detail = f"ArgoCD status code: {status_code}."
        if message:
            detail += f" ArgoCD message: {message}"
        raise ArgoCDError(status_code=status_code, detail=detail)


def _to_payload(
    app_definition: Union[ArgoApplication, Mapping[str, Any], BaseModel],
) -> Dict[str, Any]:
    """Normalize an app definition (model instance or mapping) into a JSON-able dict."""
    if isinstance(app_definition, BaseModel):
        return app_definition.model_dump(exclude_none=True)
    return dict(app_definition)


class ArgoCDClient:
    """Low level client responsible for calling Argo CD endpoints."""

    def __init__(self, base_url: str, api_key: str) -> None:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        self.api = BaseAPI(base_url.rstrip("/"), headers=headers).client

    async def _request(self, method: str, uri: str, **kwargs: Any) -> Mapping[str, Any]:
        response = await getattr(self.api, method)(uri, **kwargs)
        # Argo CD can respond with an empty body (e.g. some delete responses).
        response_json = response.json() if response.content else {}
        _handle_response(response_json, response.status_code)
        return response_json

    async def sync_app(self, app_name: str) -> None:
        await self._request("post", f"/api/v1/applications/{app_name}/sync", json={})

    async def get_app(self, app_name: str) -> ArgoApplication:
        response_json = await self._request("get", f"/api/v1/applications/{app_name}")
        return ArgoApplication.model_validate(response_json)

    async def create_app(
        self,
        app_definition: Union[ArgoApplication, Mapping[str, Any], BaseModel],
        validate: bool = True,
        upsert: bool = False,
    ) -> ArgoApplication:
        payload = _to_payload(app_definition)

        response_json = await self._request(
            "post",
            "/api/v1/applications",
            params={"validate": str(validate).lower(), "upsert": str(upsert).lower()},
            json=payload,
        )
        return ArgoApplication.model_validate(response_json)

    async def delete_app(
        self,
        app_name: str,
        app_namespace: Optional[str] = None,
        cascade: bool = True,
    ) -> None:
        params: dict[str, Any] = {"cascade": str(cascade).lower()}
        if app_namespace:
            params["appNamespace"] = app_namespace

        await self._request("delete", f"/api/v1/applications/{app_name}", params=params)

    async def patch_app(
        self,
        app_definition: Union[ArgoApplication, Mapping[str, Any], BaseModel],
        app_name: str,
        namespace: str,
        project: str,
    ) -> None:
        patch_payload = _to_payload(app_definition)

        data = {
            "appNamespace": namespace,
            "name": app_name,
            "patch": json.dumps(patch_payload),
            "patchType": "merge",
            "project": project,
        }

        await self._request("patch", f"/api/v1/applications/{app_name}", content=json.dumps(data))
