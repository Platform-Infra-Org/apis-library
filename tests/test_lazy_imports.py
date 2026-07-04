"""Importing the top-level package must not eagerly pull the Remote Config
capability's heavy dependency (aiocache) -- it loads only when a provider is built.

Runs in a fresh interpreter because ``sys.modules`` is process-global and other
tests build a provider (which does import aiocache)."""

import subprocess
import sys


def test_top_level_import_does_not_pull_aiocache():
    code = (
        "import tashtiot_apis_library, sys; "
        "leaked = sorted(m for m in sys.modules if m == 'aiocache' or m.startswith('aiocache.')); "
        "assert not leaked, leaked"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr or result.stdout
