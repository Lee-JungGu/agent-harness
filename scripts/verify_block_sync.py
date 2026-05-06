#!/usr/bin/env python3
"""
Verify byte-identical BLOCK content sync across the 4 planner templates.

Reads `templates/planner/{architect,planner_single,qa_specialist,senior_developer}.md`
and extracts the content between `<!-- BLOCK-START:spec-context-block v1` and
`<!-- BLOCK-END:spec-context-block v1 -->` markers (exclusive of the marker
comments themselves). Computes SHA256 of each. All 4 hashes MUST match.

Exit codes:
  0  All 4 BLOCK contents are byte-identical.
  1  Hash mismatch detected (drift).
  2  A planner template is missing or its BLOCK markers are absent/malformed.

Usage:
  python scripts/verify_block_sync.py

Intended invocation: pre-commit hook OR CI job.

Defined contract: see skills/spec/SKILL.md §M5 BLOCK sync mechanism +
templates/planner/*.md `<!-- BLOCK-START:spec-context-block v1 ... -->`
header comments.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

PLANNERS = [
    "templates/planner/architect.md",
    "templates/planner/planner_single.md",
    "templates/planner/qa_specialist.md",
    "templates/planner/senior_developer.md",
]

BLOCK_START_RE = re.compile(r"<!--\s*BLOCK-START:spec-context-block\s+v1.*?-->", re.DOTALL)
BLOCK_END_RE = re.compile(r"<!--\s*BLOCK-END:spec-context-block\s+v1\s*-->")


def extract_block(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    start_match = BLOCK_START_RE.search(text)
    end_match = BLOCK_END_RE.search(text)
    if not start_match or not end_match:
        print(f"[verify_block_sync] {path}: BLOCK-START or BLOCK-END marker missing", file=sys.stderr)
        sys.exit(2)
    if end_match.start() <= start_match.end():
        print(f"[verify_block_sync] {path}: BLOCK-END appears before BLOCK-START", file=sys.stderr)
        sys.exit(2)
    return text[start_match.end():end_match.start()]


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    hashes: dict[str, str] = {}
    for rel in PLANNERS:
        path = repo_root / rel
        if not path.exists():
            print(f"[verify_block_sync] {rel}: file does not exist", file=sys.stderr)
            return 2
        block = extract_block(path)
        hashes[rel] = hashlib.sha256(block.encode("utf-8")).hexdigest()

    unique_hashes = set(hashes.values())
    if len(unique_hashes) == 1:
        print(f"[verify_block_sync] OK: all 4 planner BLOCKs match (sha256={next(iter(unique_hashes))[:16]}...)")
        return 0

    print("[verify_block_sync] FAIL: planner BLOCK content drift detected", file=sys.stderr)
    for rel, h in hashes.items():
        print(f"  {h[:16]}...  {rel}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
