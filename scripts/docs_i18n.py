"""Keep the Hebrew docs (`<page>.he.md`) aligned with the English pages.

  uv run --extra docs python scripts/docs_i18n.py check docs/<page>.md docs/<page>.he.md
  uv run --extra docs python scripts/docs_i18n.py ids docs   # add/refresh {#english-id} on Hebrew headings

Every Hebrew heading carries the id MkDocs generates for the matching English heading, so anchors
(`api-standards.md#async-rules`) are identical in both languages.

Headings are matched by position, so a translation must keep the English page's headings: same
count, same levels, same order. Lines inside fenced code blocks are ignored.
"""

import re
import sys
from pathlib import Path

HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
ID_SUFFIX = re.compile(r"\s*\{#[^}]*\}\s*$")


def headings(text):
    """Return [(line_index, level, title)] for ATX headings outside fenced code."""
    out, fence = [], None
    for i, line in enumerate(text.splitlines()):
        s = line.lstrip()
        m = re.match(r"(`{3,}|~{3,})", s)
        if m:
            marker = m.group(1)
            if fence is None:
                fence = marker[0] * len(marker)
            elif s.startswith(fence) and s.strip() == s.strip()[0] * len(s.strip()):
                fence = None
            continue
        if fence is None and line.startswith("#"):
            h = HEADING.match(line)
            if h:
                out.append((i, len(h.group(1)), h.group(2)))
    return out


def english_ids(en_text):
    """Heading ids exactly as MkDocs' toc extension generates them for the English page."""
    import markdown

    md = markdown.Markdown(
        extensions=[
            "toc",
            "attr_list",
            "admonition",
            "tables",
            "md_in_html",
            "pymdownx.superfences",
        ]
    )
    md.convert(en_text)
    ids = []

    def walk(tokens):
        for t in tokens:
            ids.append((t["level"], t["id"]))
            walk(t["children"])

    walk(md.toc_tokens)
    return ids


def check(en_path, he_path):
    en = [lvl for _, lvl, _ in headings(Path(en_path).read_text())]
    he = [lvl for _, lvl, _ in headings(Path(he_path).read_text())]
    if en == he:
        print(f"OK {he_path}: {len(he)} headings match")
        return True
    print(f"MISMATCH {he_path}: english levels {en}\n          hebrew  levels {he}")
    return False


def add_ids(docs_dir):
    ok = True
    for he_path in sorted(Path(docs_dir).rglob("*.he.md")):
        en_path = he_path.with_name(he_path.name.replace(".he.md", ".md"))
        en_text, he_text = en_path.read_text(), he_path.read_text()
        ids = english_ids(en_text)
        hs = headings(he_text)
        if [lvl for lvl, _ in ids] != [lvl for _, lvl, _ in hs]:
            print(f"MISMATCH {he_path}: cannot pair headings")
            ok = False
            continue
        lines = he_text.splitlines()
        for (line_i, lvl, title), (_, hid) in zip(hs, ids, strict=True):
            lines[line_i] = f"{'#' * lvl} {ID_SUFFIX.sub('', title)} {{#{hid}}}"
        he_path.write_text("\n".join(lines) + ("\n" if he_text.endswith("\n") else ""))
        print(f"ids {he_path}: {len(hs)}")
    return ok


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "check":
        sys.exit(0 if check(sys.argv[2], sys.argv[3]) else 1)
    if cmd == "ids":
        sys.exit(0 if add_ids(sys.argv[2]) else 1)
    sys.exit(f"unknown command {cmd}")
