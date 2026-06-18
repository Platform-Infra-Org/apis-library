"""High level wrapper around the Bitbucket Server Git API."""

from __future__ import annotations

import base64
from typing import Iterable, List, Optional, Sequence, Tuple, Union

from loguru import logger

from .client import GitClient
from .models import GitChangedFile, GitDirectoryEntry, GitFileContent
from ..errors import GitError

__all__ = ["Git", "logger"]


class Git:
    """Helper that wraps the Bitbucket Server API client."""

    def __init__(
        self,
        base_url: str,
        token: str,
        username_or_email: str,
        project_key: str,
        repo_slug: str,
        default_ref: str = "main",
        ssh_key_file_path: str = "/etc/.ssh/private_key",
        # Forwarded to GitClient so callers can specify the Bitbucket SSH port without
        # having to instantiate GitClient directly.
        ssh_port: int = 7999,
    ) -> None:
        logger.debug(
            "Initialising Git service with Bitbucket Server: base_url={}, project_key={}, repo_slug={}",
            base_url,
            project_key,
            repo_slug,
        )
        self.client = GitClient(
            base_url,
            username_or_email,
            token,
            project_key,
            repo_slug,
            default_ref,
            ssh_key_file_path,
            ssh_port,
        )
        self.default_ref = default_ref
        self.last_commit: Optional[str] = None

    async def modify_file(self, path: str, commit_message: str, content: Union[str, bytes], *, branch: Optional[str] = None) -> None:
        logger.info("Modifying file at path={} (branch={}).", path, branch or self.default_ref)
        await self._ensure_exists_for_mutation(path, branch)
        await self.client.create_or_update_file(path, commit_message, content, branch=branch, create=False)
        return

    async def add_file(self, path: str, commit_message: str, content: Union[str, bytes], *, branch: Optional[str] = None) -> None:
        logger.info("Adding file at path={} (branch={}).", path, branch or self.default_ref)
        await self._ensure_absent_for_create(path, branch)
        await self.client.create_or_update_file(path, commit_message, content, branch=branch, create=True)
        return

    async def delete_file(self, path: str, commit_message: str, *, branch: Optional[str] = None) -> None:
        logger.info("Deleting file at path={} (branch={}).", path, branch or self.default_ref)
        await self.client.delete_file(path, commit_message, branch)

    async def get_file_content(self, path: str, ref: Optional[str] = None, encoding: str = "utf-8") -> str:
        logger.debug("Fetching text for path={} (ref={}).", path, ref or self.default_ref)
        meta = await self._get_file(path, ref=ref)
        if not meta.content:
            raise GitError(status_code=500, detail=f"File {path} missing content")
        return base64.b64decode(meta.content).decode(encoding)

    async def list_dir(self, path: str, ref: Optional[str] = None) -> List[Tuple[str, str]]:
        logger.debug("Listing directory path={} (ref={}).", path or "/", ref or self.default_ref)
        items = await self._list_dir_raw(path, ref=ref)
        return [
            (item.name or "", item.path or "")
            for item in items
            if (item.name or "") and (item.path or "")
        ]

    async def list_files_recursive(self, path: str = "", ref: Optional[str] = None) -> List[str]:
        logger.debug("Listing files recursively from path={} (ref={}).", path or "/", ref or self.default_ref)
        if hasattr(self.client, "list_files_recursive"):
            return await self.client.list_files_recursive(path, ref)

        files: List[str] = []
        stack: List[str] = [path.strip("/")] if path else [""]

        while stack:
            current = stack.pop()
            entries = await self._list_dir_raw(current, ref=ref)
            for entry in entries:
                entry_type = (entry.type or "").lower()
                entry_path = entry.path or ""
                if not entry_path:
                    continue
                if entry_type == "dir":
                    stack.append(entry_path)
                elif entry_type == "file":
                    files.append(entry_path)

        return sorted(set(files))

    @staticmethod
    def _ensure_str(content: Union[str, bytes], *, encoding: str = "utf-8") -> str:
        return content.decode(encoding) if isinstance(content, bytes) else content

    async def _ensure_exists_for_mutation(self, path: str, branch: Optional[str]) -> None:
        ref = branch or self.default_ref
        try:
            await self._get_file(path, ref=ref)
        except GitError as exc:
            logger.error(
                "Mutation target {} missing (ref={}): {}",
                path,
                ref,
                exc.detail if hasattr(exc, "detail") else exc,
            )
            raise

    async def _ensure_absent_for_create(self, path: str, branch: Optional[str]) -> None:
        ref = branch or self.default_ref
        try:
            await self._get_file(path, ref=ref)
        except GitError:
            return
        logger.error(
            "Creation target {} already exists (ref={}).",
            path,
            ref,
        )
        raise GitError(status_code=409, detail=f"File {path} already exists")

    async def _get_file(self, path: str, ref: Optional[str]) -> GitFileContent:
        return await self.client.get_file(path, ref=ref)

    async def _list_dir_raw(self, path: str, ref: Optional[str]) -> Sequence[GitDirectoryEntry]:
        return await self.client.list_dir(path, ref=ref)

    async def file_exists(self, path: str, ref: Optional[str] = None) -> bool:
        
        try:
            await self._get_file(path, ref or self.default_ref)
            return True

        except GitError as exc:
            if exc.status_code == 404:
                logger.error(
                    "Mutation target {} missing (ref={}): {}",
                    path,
                    ref,
                    exc.detail if hasattr(exc, "detail") else exc,
                )
                return False

            raise
