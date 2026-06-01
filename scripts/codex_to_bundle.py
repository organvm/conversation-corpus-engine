#!/usr/bin/env python3
"""codex_to_bundle — Convert Codex CLI session JSONL exports into a standard
ChatGPT-export bundle that the engine's `import_chatgpt_export_corpus` adapter
can ingest.

Background
----------
Codex CLI stores session data as plain-text JSONL files in
`~/.codex/sessions/`. The rollout agent writes lines to files named
`rollout-*.jsonl`, one JSON object per line. Each line has a `type` field;
the lines relevant to conversation history have `type == "response_item"`
and carry a `role` (`user` | `assistant`), `content`, `session` UUID, and
`timestamp`.

The engine's official adapter expects the standard ChatGPT-export bundle:

    bundle/
      conversations.json    # list of conversations with mapping/parent/children
      user.json

This script reads one or more `rollout-*.jsonl` files, filters response items,
groups them by session UUID, and emits a synthetic bundle dir.

Usage
-----
    python scripts/codex_to_bundle.py <input-dir> [<input-dir> ...] <output-bundle-dir>

Then ingest with the standard adapter:
    cce provider import chatgpt <output-bundle-dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _session_id_from_path(path: Path) -> str:
    """Derive a stable session ID from a file path stem."""
    raw = path.stem
    h = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:36]
    return h


def _ensure_timestamp(ts: Any) -> float:
    """Convert a timestamp value to epoch seconds."""
    if ts is None:
        return 0.0
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts)
            return dt.timestamp()
        except (ValueError, TypeError):
            return 0.0
    return 0.0


def _normalize_role(role: str | None) -> str:
    if not role:
        return "user"
    r = role.strip().lower()
    if r in ("user", "human", "you"):
        return "user"
    if r in ("assistant", "ai", "bot", "model"):
        return "assistant"
    return "user"


def discover_input_files(input_paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for p in input_paths:
        if p.is_dir():
            files.extend(sorted(p.glob("rollout-*.jsonl")))
        elif p.suffix == ".jsonl" and p.exists():
            files.append(p)
        else:
            print(f"  skip (not found/not JSONL): {p}", file=sys.stderr)
    return files


def convert_directory(input_paths: list[Path], output_bundle: Path) -> dict:
    """Read Codex rollout JSONL files, write a standard bundle to output_bundle."""
    files = discover_input_files(input_paths)
    if not files:
        raise FileNotFoundError(f"no rollout-*.jsonl files found under any of: {input_paths}")

    # Group response items by session UUID
    sessions: dict[str, list[dict]] = {}
    seen_items: set[str] = set()  # dedup by content hash
    skipped_invalid = 0
    lines_total = 0

    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"  skip (unreadable): {path.name} — {exc}", file=sys.stderr)
            continue

        for line_num, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            lines_total += 1
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                skipped_invalid += 1
                continue

            if record.get("type") != "response_item":
                continue
            role = _normalize_role(record.get("role"))
            if role not in ("user", "assistant"):
                continue
            content = (record.get("content") or "").strip()
            if not content:
                continue

            # Dedup by content hash within same session
            content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
            dedup_key = f"{record.get('session', 'unknown')}:{content_hash}"
            if dedup_key in seen_items:
                continue
            seen_items.add(dedup_key)

            session_id = record.get("session") or _session_id_from_path(path)
            sessions.setdefault(session_id, []).append(
                {
                    "role": role,
                    "content": content,
                    "timestamp": _ensure_timestamp(record.get("timestamp")),
                    "session": session_id,
                }
            )

    if not sessions:
        raise ValueError("no valid response_items found in any input file")

    # Build conversations in bundle format
    conversations: list[dict] = []
    skipped_empty_session = 0

    for session_id, items in sessions.items():
        items.sort(key=lambda x: x["timestamp"])
        non_root = [m for m in items if m["content"]]
        if not non_root:
            skipped_empty_session += 1
            continue

        create_time = non_root[0]["timestamp"]
        update_time = non_root[-1]["timestamp"]

        mapping: dict[str, dict[str, Any]] = {}
        root_id = f"codex-root-{session_id}"
        mapping[root_id] = {
            "id": root_id,
            "parent": None,
            "children": [],
            "message": None,
        }

        prev_id = root_id
        for i, msg in enumerate(non_root, start=1):
            node_id = f"codex-msg-{session_id}-{i:04d}"
            mapping[node_id] = {
                "id": node_id,
                "parent": prev_id,
                "children": [],
                "message": {
                    "id": node_id,
                    "author": {"role": msg["role"]},
                    "create_time": msg["timestamp"],
                    "content": {"content_type": "text", "parts": [msg["content"]]},
                },
            }
            mapping[prev_id]["children"].append(node_id)
            prev_id = node_id

        conversations.append(
            {
                "title": f"Codex Session {session_id[:8]}",
                "create_time": create_time,
                "update_time": update_time,
                "conversation_id": session_id,
                "mapping": mapping,
            }
        )

    output_bundle.mkdir(parents=True, exist_ok=True)
    (output_bundle / "conversations.json").write_text(
        json.dumps(conversations, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_bundle / "user.json").write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")

    return {
        "input_paths": [str(p) for p in input_paths],
        "output_bundle": str(output_bundle),
        "files_scanned": len(files),
        "lines_total": lines_total,
        "conversations_written": len(conversations),
        "skipped_invalid_lines": skipped_invalid,
        "skipped_empty_sessions": skipped_empty_session,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "input_paths",
        nargs="+",
        type=Path,
        help="One or more directories or .jsonl files containing rollout-* data",
    )
    parser.add_argument(
        "output_bundle",
        type=Path,
        help="Output bundle directory (will contain conversations.json + user.json)",
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args()

    if len(args.input_paths) < 1:
        parser.error("at least one input path is required")

    output_bundle = args.input_paths.pop() if args.input_paths else Path()
    input_paths = args.input_paths

    if not input_paths:
        parser.error("at least one input path is required before the output bundle")

    try:
        result = convert_directory(input_paths, output_bundle)
    except (FileNotFoundError, ValueError, NotADirectoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Scanned: {result['files_scanned']} files ({result['lines_total']} lines)")
        print(f"Wrote:   {result['conversations_written']} conversations")
        print(
            f"Skipped: {result['skipped_invalid_lines']} invalid, {result['skipped_empty_sessions']} empty"
        )
        print(f"Bundle:  {result['output_bundle']}")
        print()
        print("Next: cce provider import chatgpt {}".format(result["output_bundle"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
