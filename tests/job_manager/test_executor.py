"""CommandExecutor: real subprocess streaming + non-zero -> ExecutorError.

Uses the running Python interpreter as a portable subprocess (no shell, no infra).
"""

import sys

import pytest

from tashtiot_apis_library.job_manager.exceptions import ExecutorError
from tashtiot_apis_library.job_manager.executor import CommandExecutor


@pytest.mark.asyncio
async def test_streams_stdout_lines():
    # The script itself has no {name} placeholders (only {n} is a param) so it's left intact.
    script = "import sys\nfor i in range(int(sys.argv[1])): print('line%d' % i)"
    ex = CommandExecutor(command_for={"say": [sys.executable, "-c", script, "{n}"]})
    lines = [chunk async for chunk in ex.run("say", {"n": 3})]
    assert lines == ["line0", "line1", "line2"]


@pytest.mark.asyncio
async def test_params_are_formatted_into_argv():
    ex = CommandExecutor(command_for={"echo": [sys.executable, "-c", "print('{msg}')"]})
    lines = [chunk async for chunk in ex.run("echo", {"msg": "hello"})]
    assert lines == ["hello"]


@pytest.mark.asyncio
async def test_literal_braces_preserved_partial_placeholder_expanded():
    # jsonpath-style `{.keep}` must survive; `{val}` must be substituted.
    ex = CommandExecutor(command_for={"q": [sys.executable, "-c", "print('{val}::{.keep}')"]})
    lines = [chunk async for chunk in ex.run("q", {"val": "X"})]
    assert lines == ["X::{.keep}"]


@pytest.mark.asyncio
async def test_unknown_operation_raises():
    ex = CommandExecutor(command_for={})
    with pytest.raises(ExecutorError):
        [chunk async for chunk in ex.run("nope", {})]


@pytest.mark.asyncio
async def test_missing_param_raises():
    ex = CommandExecutor(command_for={"op": [sys.executable, "-c", "print('{missing}')"]})
    with pytest.raises(ExecutorError):
        [chunk async for chunk in ex.run("op", {})]


@pytest.mark.asyncio
async def test_shell_mode_quotes_argv_tokens():
    # Each argv token becomes one shell-quoted argument: the param value stays a single
    # arg, so the embedded `; echo INJECTED` is printed literally, never executed.
    ex = CommandExecutor(command_for={"op": ["printf", "%s", "{msg}"]}, shell=True)
    lines = [chunk async for chunk in ex.run("op", {"msg": "a b; echo INJECTED"})]
    assert lines == ["a b; echo INJECTED"]


@pytest.mark.asyncio
async def test_nonzero_exit_raises_after_streaming():
    ex = CommandExecutor(
        command_for={"fail": [sys.executable, "-c", "import sys; print('partial'); sys.exit(2)"]}
    )
    with pytest.raises(ExecutorError):
        [chunk async for chunk in ex.run("fail", {})]


@pytest.mark.asyncio
async def test_shell_mode_quotes_params_in_string_template():
    # A string template in shell mode quotes each substituted param, so API-supplied
    # values can't inject shell syntax; the template's own syntax still works.
    ex = CommandExecutor(command_for={"op": "printf %s {msg}"}, shell=True)
    lines = [chunk async for chunk in ex.run("op", {"msg": "a b; echo INJECTED"})]
    assert lines == ["a b; echo INJECTED"]
