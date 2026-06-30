"""Execution backends behind the ``Executor`` Protocol (default: ``CommandExecutor``)."""

from __future__ import annotations

import asyncio
import re
import shlex
from typing import (
    Any,
    AsyncIterator,
    Dict,
    List,
    Mapping,
    Optional,
    Protocol,
    Union,
    runtime_checkable,
)

from loguru import logger

from .exceptions import ExecutorError

__all__ = ["Executor", "CommandExecutor"]

# A ``{name}`` placeholder; leaves other braces (jsonpath, Go templates, JSON) untouched.
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


@runtime_checkable
class Executor(Protocol):
    """Runs a named operation against its target, yielding stdout chunks as they arrive."""

    def run(self, operation: str, params: Dict[str, Any]) -> AsyncIterator[str]: ...


class CommandExecutor:
    """Run a command per operation, streaming stdout lines.

    ``command_for`` maps each operation to an argv list (recommended) or a string.
    ``{name}`` placeholders are substituted from ``params``; other braces (jsonpath
    ``{.status}``, Go templates, JSON) pass through untouched. A non-zero exit
    raises :class:`ExecutorError`.

    Prefer an argv list: a string command is shell-split (``shlex``), so a param
    value containing spaces only stays one argument inside a list token.
    """

    def __init__(
        self,
        *,
        command_for: Mapping[str, Union[List[str], str]],
        shell: bool = False,
        cwd: Optional[str] = None,
        env: Optional[Mapping[str, str]] = None,
    ) -> None:
        self.command_for = command_for
        self.shell = shell
        self.cwd = cwd
        self.env = dict(env) if env is not None else None

    def _expand(self, text: str, params: Dict[str, Any], operation: str) -> str:
        def repl(match: "re.Match[str]") -> str:
            name = match.group(1)
            if name not in params:
                raise ExecutorError(f"Missing param {name!r} for operation {operation!r}.")
            return str(params[name])

        return _PLACEHOLDER.sub(repl, text)

    def _resolve(self, operation: str, params: Dict[str, Any]) -> Union[List[str], str]:
        template = self.command_for.get(operation)
        if template is None:
            raise ExecutorError(f"Unknown operation {operation!r}.")
        if isinstance(template, str):
            return self._expand(template, params, operation)
        return [self._expand(token, params, operation) for token in template]

    async def run(self, operation: str, params: Dict[str, Any]) -> AsyncIterator[str]:
        command = self._resolve(operation, params)
        logger.debug("Running operation {}: {}", operation, command)

        if self.shell:
            proc = await asyncio.create_subprocess_shell(
                command if isinstance(command, str) else " ".join(command),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=self.cwd,
                env=self.env,
            )
        else:
            argv = shlex.split(command) if isinstance(command, str) else command
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=self.cwd,
                env=self.env,
            )

        assert proc.stdout is not None
        try:
            async for raw in proc.stdout:
                yield raw.decode(errors="replace").rstrip("\n")
            await proc.wait()
        finally:
            # On normal completion the proc has exited; on cancel/abort (the
            # generator is closed early) kill the child so nothing is left running.
            if proc.returncode is None:
                proc.kill()
                await proc.wait()

        if proc.returncode != 0:
            raise ExecutorError(f"Operation {operation!r} exited with code {proc.returncode}.")
