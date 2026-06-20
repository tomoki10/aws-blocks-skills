#!/usr/bin/env python3
"""Detect when an upstream AWS docs page has drifted from the version we last reviewed.

Companion to scripts/check-i18n.sh. Where that script tracks English -> Japanese drift via
git blob hashes, this one tracks "upstream AWS doc page -> the skill files derived from it".

It works by keeping, for each tracked page, a normalized text *snapshot* plus its sha256 in
scripts/upstream/manifest.json. On each run it re-fetches the page, normalizes it with the SAME
logic used to make the snapshot, and compares. The snapshot lets us show *what* changed (a unified
diff), not just *that* something changed — which is what makes the (judgement-based) reflection
into best-practices.md tractable.

Usage:
    python3 scripts/check-upstream-docs.py            # check all sources
    python3 scripts/check-upstream-docs.py --update [<id>]   # re-baseline (after reviewing)

Exit codes (parallel to check-i18n.sh):
    0  all tracked pages match their snapshot
    1  at least one page CHANGED (drift detected)
    2  fetch/parse error, or page structure changed (NOT a content drift — don't false-alarm)
"""

import datetime
import difflib
import hashlib
import html
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "scripts" / "upstream" / "manifest.json"

# Marks the start/end of the meaningful article body on docs.aws.amazon.com pages. The wrapping
# chrome (nav, header, footer, build-version markers) is volatile and must be excluded so the hash
# only changes when the prose/code actually changes.
START_MARKER = 'id="main-col-body"'
END_MARKER = 'id="main-col-footer"'

# Block-level tags whose close (or self-close) becomes a line break, so the normalized text reads
# as readable lines for diffing while staying stable across fetches.
_BLOCK_RE = re.compile(
    r"(?i)</(p|div|li|ul|ol|h[1-6]|tr|table|thead|tbody|pre|code|section|article|header|figure|blockquote|dt|dd|dl)>"
)
_BR_RE = re.compile(r"(?i)<br\s*/?>")
_SCRIPT_RE = re.compile(r"(?is)<(script|style)\b.*?</\1>")
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")


class FetchError(Exception):
    """Network failure — distinct from a content change (exit 2, not 1)."""


class StructureError(Exception):
    """The expected content container was not found — AWS likely redesigned the page (exit 2)."""


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "aws-blocks-skills-upstream-check/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        raise FetchError(f"could not fetch {url}: {exc}") from exc


def normalize(page_html: str) -> str:
    """Extract the article body and reduce it to stable, diff-friendly multi-line text."""
    start = page_html.find(START_MARKER)
    if start == -1:
        raise StructureError(f"start marker {START_MARKER!r} not found")
    # Begin after the opening tag that holds the start marker so its leftover attributes don't leak.
    body_start = page_html.find(">", start)
    if body_start == -1:
        raise StructureError("opening tag for the content body is malformed")
    body_start += 1
    end = page_html.find(END_MARKER, body_start)
    if end == -1:
        raise StructureError(f"end marker {END_MARKER!r} not found")
    # End at the '<' that opens the footer tag so its partial markup doesn't leak as text.
    frag_end = page_html.rfind("<", body_start, end)
    if frag_end == -1:
        frag_end = end
    frag = page_html[body_start:frag_end]

    frag = _SCRIPT_RE.sub(" ", frag)
    frag = _BLOCK_RE.sub("\n", frag)
    frag = _BR_RE.sub("\n", frag)
    frag = _TAG_RE.sub(" ", frag)
    frag = html.unescape(frag)

    lines = [_WS_RE.sub(" ", ln).strip() for ln in frag.split("\n")]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines) + "\n"


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_manifest() -> dict:
    if not MANIFEST.exists():
        sys.stderr.write(f"manifest not found: {MANIFEST}\n")
        sys.exit(2)
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def save_manifest(manifest: dict) -> None:
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def check_source(src: dict) -> int:
    """Return per-source exit code: 0 OK, 1 CHANGED, 2 error."""
    sid = src["id"]
    try:
        current = normalize(fetch(src["url"]))
    except FetchError as exc:
        print(f"ERROR    {sid}  (fetch failed: {exc})")
        return 2
    except StructureError as exc:
        print(f"ERROR    {sid}  (page structure changed: {exc} — update the extractor in {Path(__file__).name})")
        return 2

    if sha256(current) == src.get("content_sha256"):
        print(f"OK       {sid}")
        return 0

    print(f"CHANGED  {sid}  ({src['url']})")
    snap_path = REPO_ROOT / src["snapshot"]
    baseline = snap_path.read_text(encoding="utf-8").splitlines() if snap_path.exists() else []
    diff = difflib.unified_diff(
        baseline,
        current.splitlines(),
        fromfile=f"{sid} (last reviewed {src.get('last_reviewed', '?')})",
        tofile=f"{sid} (now)",
        lineterm="",
    )
    for line in diff:
        print(line)
    print(f"\n--> review the diff, reflect into {', '.join(src.get('derived_files', []))},")
    print(f"    then re-baseline with: python3 {Path(__file__).relative_to(REPO_ROOT)} --update {sid}")
    return 1


def update_source(src: dict) -> int:
    sid = src["id"]
    try:
        current = normalize(fetch(src["url"]))
    except (FetchError, StructureError) as exc:
        print(f"ERROR    {sid}  ({exc})")
        return 2
    snap_path = REPO_ROOT / src["snapshot"]
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    snap_path.write_text(current, encoding="utf-8")
    src["content_sha256"] = sha256(current)
    src["last_reviewed"] = datetime.date.today().isoformat()
    print(f"UPDATED  {sid}  sha256={src['content_sha256']}  last_reviewed={src['last_reviewed']}")
    return 0


def main(argv: list) -> int:
    do_update = "--update" in argv
    target_id = None
    if do_update:
        rest = [a for a in argv if a != "--update"]
        target_id = rest[0] if rest else None

    manifest = load_manifest()
    sources = manifest.get("sources", [])
    if target_id:
        sources_to_run = [s for s in sources if s["id"] == target_id]
        if not sources_to_run:
            sys.stderr.write(f"no source with id {target_id!r} in manifest\n")
            return 2
    else:
        sources_to_run = sources

    worst = 0
    if do_update:
        for src in sources_to_run:
            worst = max(worst, update_source(src))
        save_manifest(manifest)
    else:
        for src in sources_to_run:
            worst = max(worst, check_source(src))
    return worst


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
