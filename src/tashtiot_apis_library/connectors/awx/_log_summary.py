"""Concise Ansible output for status responses; not a secrets redactor."""

import json
import re
from collections import deque

MAX_LOG_CHARS = 10_000
MAX_FILTERED_LINES = 100
_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_KEEP = re.compile(
    r"^(?:PLAY\b|TASK\b|RUNNING HANDLER\b|fatal:|ERROR\b|\[?(?:WARNING|DEPRECATION WARNING)\b)"
)
_ACTION = re.compile(r"^(?:ok|changed|failed|skipped|unreachable):\s*\[[^\]]+\](?:\s*:\s*FAILED!)?")
_RECAP = re.compile(r"^\S+\s*:\s*ok=\d+\s+changed=\d+.*\bfailed=\d+")
_MSG = re.compile(r"""^\s*["']?msg["']?\s*:\s*(.+?)\s*,?\s*$""")


def bound_logs(text: str, max_chars: int = MAX_LOG_CHARS) -> str:
    """Keep the tail with a visible marker, within the character budget."""
    if len(text) <= max_chars:
        return text
    marker = "... [output truncated]\n"
    return marker + text[-(max_chars - len(marker)) :]


def filter_ansible_logs(raw: str) -> str:
    """Keep task/results/warnings/recap and short messages, omit verbose bodies.

    This is a presentation filter, not a guarantee that messages contain no secrets.
    """
    kept = deque(maxlen=MAX_FILTERED_LINES)
    count = 0
    for raw_line in raw.splitlines():
        line = _ANSI.sub("", raw_line).strip()
        matches = []
        if _KEEP.match(line) or _RECAP.match(line):
            # A fatal result may contain an entire JSON module result.
            matches.append(line.split("=>", 1)[0].rstrip()[:500])
        elif action := _ACTION.match(line):
            matches.append(action.group(0))
        elif message := _MSG.match(line):
            matches.append("  → " + message.group(1).strip("\"'")[:150])
        if "=>" in line:
            try:
                payload = json.loads(line.split("=>", 1)[1])
            except (ValueError, TypeError):
                payload = None
            if isinstance(payload, dict) and isinstance(payload.get("msg"), str):
                matches.append("  → " + " ".join(payload["msg"].splitlines())[:150])
        for match in matches:
            kept.append(match)
            count += 1
    text = "\n".join(kept)
    if count > MAX_FILTERED_LINES:
        text = "... [filtered output truncated]\n" + text
    return bound_logs(text)


def status_heading(name: str, status: str) -> str:
    icon = (
        "✓" if status == "successful" else "✗" if status in {"failed", "error", "canceled"} else "…"
    )
    return f"[{icon}] {' '.join(name.splitlines())}: {status}"


def job_summary(name: str, status: str, filtered: str) -> str:
    lines = [status_heading(name, status)]
    if filtered == "[AWX output unavailable]":
        lines.append("  " + filtered)
    elif status in {"failed", "error", "canceled"}:
        lines.extend("  " + line for line in filtered.splitlines()[-10:])
    elif status == "successful":
        recap = [
            line
            for line in filtered.splitlines()
            if line.startswith("PLAY RECAP") or _RECAP.match(line)
        ]
        lines.extend("  " + line for line in recap[-2:])
    return bound_logs("\n".join(lines))
