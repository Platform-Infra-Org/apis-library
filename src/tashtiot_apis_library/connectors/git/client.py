"""Hybrid Bitbucket GitClient client: structured errors, GitHub-like shapes and an httpx multipart."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from loguru import logger

from ...fastapi_template.utils import BaseAPI
from ..errors import GitError
from .models import GitDirectoryEntry, GitFileContent

__all__ = ["GitClient"]


async def _run_git(
    args: List[str], cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None
) -> Tuple[str, str]:
    cmd = ["git"] + args
    logger.debug(f"running {' '.join(cmd)}")
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout_bytes, stderr_bytes = await process.communicate()
    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")

    if process.returncode != 0:
        logger.debug(f"{' '.join(cmd)} has failed due to {' '.join(args)}\n{stderr}")
        raise GitError(status_code=500, detail=f"Git command failed: {' '.join(args)}\n{stderr}")
    return stdout, stderr


def _safe_json(response) -> Dict[str, Any]:
    try:
        return response.json()
    except ValueError:
        return {}


def _bb_message(data: Dict[str, Any]) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    if "error" in data and isinstance(data["error"], dict):
        return data["error"].get("message")
    return data.get("message")


def _handle_response(response_json: Dict[str, Any], status_code: int) -> None:
    message = _bb_message(response_json)

    if status_code == 401:
        raise GitError(401, f"Bitbucket token invalid. {message or ''}")
    if status_code == 403:
        raise GitError(403, f"Permission denied. {message or ''}")
    if status_code == 404:
        raise GitError(404, f"Path, repo, or ref not found. {message or ''}")
    if status_code >= 400:
        raise GitError(status_code, f"Bitbucket error: {message or status_code}")


def _blob_sha(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode("utf-8")
    return hashlib.sha1(header + content).hexdigest()


def _server_browse_endpoint(project_key: str, repo_slug: str, path: str) -> str:
    return f"/projects/{project_key}/repos/{repo_slug}/browse/{path.lstrip('/')}"


class GitClient:
    """Bitbucket Server API client."""

    def __init__(
        self,
        base_url: str,
        username_or_email: str,
        token: str,
        project_key: str,
        repo_slug: str,
        default_ref: str = "main",
        ssh_key_file_path: str = "/etc/.ssh/private_key",
        ssh_port: int = 7995,
    ) -> None:
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        self.api = BaseAPI(base_url.rstrip("/"), headers=headers).client
        self.repo_slug = repo_slug
        self._default_ref = default_ref
        self.project_key = project_key
        self.ssh_host = f"{base_url.replace('https://', '').split('/')[0]}:{ssh_port}"

        self._git_env = os.environ.copy()
        self._git_env["GIT_SSH_COMMAND"] = f"ssh -i {ssh_key_file_path} -o StrictHostKeyChecking=no"

        self.username_or_email = username_or_email

    async def get_file(self, path: str, ref: Optional[str] = None) -> GitFileContent:
        ref = ref or self._default_ref
        endpoint = _server_browse_endpoint(self.project_key, self.repo_slug, path)
        params = {"at": ref}

        # Get metadata
        meta_response = await self.api.get(endpoint, params=params)
        meta_data = _safe_json(meta_response)
        _handle_response(meta_data, meta_response.status_code)

        # Get raw content
        raw_params = {"at": ref, "raw": 1}
        raw_response = await self.api.get(
            endpoint, params=raw_params, headers={"Accept": "application/octet-stream"}
        )
        _handle_response(_safe_json(raw_response), raw_response.status_code)
        content_bytes = raw_response.content

        # Parse metadata
        path_meta = meta_data.get("path") if isinstance(meta_data, dict) else {}
        if isinstance(path_meta, dict):
            components = (
                path_meta.get("components")
                if isinstance(path_meta.get("components"), list)
                else None
            )
            meta_path = path_meta.get("toString") or "/".join(components or [])
            meta_name = path_meta.get("name")
        else:
            meta_path = None
            meta_name = None

        return GitFileContent(
            type="file",
            encoding="base64",
            size=len(content_bytes),
            name=meta_name or (meta_path or path).split("/")[-1],
            path=(meta_path or path).lstrip("/"),
            content=base64.b64encode(content_bytes).decode(),
            sha=_blob_sha(content_bytes),
        )

    async def list_dir(self, path: str, ref: Optional[str] = None) -> List[GitDirectoryEntry]:
        ref = ref or self._default_ref
        endpoint = _server_browse_endpoint(self.project_key, self.repo_slug, path)
        response = await self.api.get(endpoint, params={"at": ref})
        data = _safe_json(response)
        _handle_response(data, response.status_code)

        children = {}
        if isinstance(data, dict):
            children = data.get("children", {}) or {}

        values: Iterable[Dict[str, Any]] = []
        if isinstance(children, dict):
            raw_values = children.get("values")
            if isinstance(raw_values, list):
                values = raw_values

        entries: List[GitDirectoryEntry] = []
        for entry in values:
            if not isinstance(entry, dict):
                continue
            path_meta = entry.get("path")
            if isinstance(path_meta, dict):
                components = (
                    path_meta.get("components")
                    if isinstance(path_meta.get("components"), list)
                    else None
                )
                entry_path = path_meta.get("toString") or "/".join(components or [])
            else:
                entry_path = path_meta
            if not entry_path:
                continue
            entry_type = (entry.get("type") or "").lower()
            entries.append(
                GitDirectoryEntry(
                    name=entry_path.split("/")[-1],
                    path=entry_path,
                    type="dir" if entry_type == "directory" else "file",
                )
            )
        return entries

    async def _server_branch_head(self, branch: str) -> Optional[str]:
        endpoint = f"/projects/{self.project_key}/repos/{self.repo_slug}/branches"
        response = await self.api.get(endpoint, params={"filterText": branch, "limit": 1})
        data = _safe_json(response)
        _handle_response(data, response.status_code)

        if not isinstance(data, dict):
            return None

        values = data.get("values")

        if not isinstance(values, list):
            return None

        normalised = branch.replace("refs/heads/", "")

        for entry in values:
            if not isinstance(entry, dict):
                continue

            display_id = entry.get("displayId") or entry.get("display_id")
            entry_id = entry.get("id")
            if (
                display_id == normalised
                or entry_id == branch
                or entry_id == f"refs/heads/{normalised}"
            ):
                latest = entry.get("latestCommit") or entry.get("latest_commit")
                if isinstance(latest, str) and latest:
                    return latest

        return None

    async def _commit(
        self,
        commit_message: str,
        *,
        files: Optional[Dict[str, bytes]],
        deleted: List[str],
        branch: Optional[str],
        create: bool,
    ) -> None:
        source_commit = await self._server_branch_head(branch or self._default_ref)

        for path, content in (files or {}).items():
            endpoint = _server_browse_endpoint(self.project_key, self.repo_slug, path)
            data = {"message": commit_message, "branch": branch}
            if source_commit:
                data["sourceCommitId"] = source_commit
            if create:
                data.pop("sourceCommitId", None)
            response = await self.api.put(
                endpoint,
                data=data,
                files={
                    "content": (
                        Path(path).name,
                        content,
                        "application/octet-stream",
                    )
                },
            )

            _handle_response(_safe_json(response), response.status_code)

    async def create_or_update_file(
        self,
        path: str,
        commit_message: str,
        content: Union[str, bytes],
        create: bool,
        branch: Optional[str] = None,
    ) -> None:
        data_bytes = content.encode() if isinstance(content, str) else content
        await self._commit(
            commit_message, files={path: data_bytes}, deleted=[], branch=branch, create=create
        )

    async def delete_file(
        self, path: str, commit_message: str, branch: Optional[str] = None
    ) -> None:

        temp_dir = tempfile.mktemp(prefix="git-delete-")

        try:
            ref = branch or self._default_ref
            ssh_url = f"ssh://git@{self.ssh_host}/{self.project_key}/{self.repo_slug}.git"
            repo_dir = os.path.join(temp_dir, "repo")

            await _run_git(
                [
                    "clone",
                    "--depth",
                    "1",
                    "--branch",
                    ref,
                    "--single-branch",
                    ssh_url,
                    repo_dir,
                ],
                env=self._git_env,
            )

            await _run_git(
                [
                    "-C",
                    repo_dir,
                    "config",
                    "--local",
                    "user.name",
                    self.username_or_email,
                ],
                env=self._git_env,
            )

            await _run_git(
                [
                    "-C",
                    repo_dir,
                    "config",
                    "--local",
                    "user.email",
                    self.username_or_email,
                ],
                env=self._git_env,
            )

            file_path = os.path.join(repo_dir, path.lstrip("/"))
            if not os.path.exists(file_path):
                raise GitError(status_code=404, detail=f"File {path} not found")

            os.remove(file_path)
            await _run_git(["add", path.lstrip("/")], cwd=repo_dir, env=self._git_env)
            await _run_git(["commit", "-m", commit_message], cwd=repo_dir, env=self._git_env)

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await _run_git(["push"], cwd=repo_dir, env=self._git_env)
                    break
                except GitError as e:
                    if "rejected" in e.detail and attempt < max_retries - 1:
                        await _run_git(["push", "--rebase"], cwd=repo_dir, env=self._git_env)
                    else:
                        raise
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
