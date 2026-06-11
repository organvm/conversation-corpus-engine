#!/usr/bin/env python3
"""claude_code_to_bundle — Convert Claude Code session JSONL transcripts into a
standard ChatGPT-export bundle that the engine's `import_chatgpt_export_corpus`
adapter can ingest.

Background
----------
Claude Code stores session transcripts as plain-text JSONL files under
`~/.claude/projects/<scope-slug>/<session-uuid>.jsonl`, one JSON event per
line. The lines relevant to conversation history have `type == "user"` or
`type == "assistant"` and carry a `sessionId` UUID, an ISO-8601 `timestamp`,
an event `uuid`, and a `message` object:

    {"type": "user"|"assistant",
     "sessionId": "<uuid>", "timestamp": "<iso8601>", "uuid": "...",
     "isSidechain": false,
     "message": {"role": "user"|"assistant", "content": str | [blocks]}}

Content blocks (in `message.content` lists) are tagged:

    {"type": "text", "text": ...}                       -> message text (kept)
    {"type": "thinking", "thinking": ...}               -> reasoning (skipped)
    {"type": "tool_use", "name": ..., "input": {...}}   -> tool call (skipped)
    {"type": "tool_result", "content": ...}             -> tool output (skipped)

Sidechain events (`isSidechain == true`) are subagent traffic — their "user"
turns are synthetic orchestrator prompts, not the human — and are skipped by
default (`--include-sidechains` keeps them). Other event types (`system`,
`summary`, `mode`, `file-history-snapshot`, ...) carry no conversation turns.

User prompt text passes through byte-identical: no trimming, no whitespace
normalization. Emptiness checks are performed on a stripped copy only.

The engine's official adapter expects the standard ChatGPT-export bundle:

    bundle/
      conversations.json    # list of conversations with mapping/parent/children
      user.json

This script reads one or more `*.jsonl` transcripts, filters conversation
events, groups them by session UUID, and emits a synthetic bundle dir.

Usage
-----
    python scripts/claude_code_to_bundle.py <input-dir> [<input-dir> ...] <output-bundle-dir>

Then ingest with the standard adapter:
    cce provider import --provider chatgpt --source-drop-root <drop-root> --register --build
(with the bundle placed at `<drop-root>/chatgpt/inbox/<bundle-dir>`), or
directly:
    cce provider import --provider chatgpt --source-path <output-bundle-dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def _session_id_from_path(path: Path) -> str:
    """Derive a stable session ID from a file path stem."""
    raw = path.stem
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:36]


def _ensure_timestamp(ts: Any) -> float:
    """Convert a timestamp value (epoch number or ISO-8601 string) to epoch seconds."""
    if ts is None:
        return 0.0
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str):
        raw = ts.strip()
        if raw.endswith(("Z", "z")):
            raw = raw[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(raw).timestamp()
        except (ValueError, TypeError):
            return 0.0
    return 0.0


def _normalize_role(role: str | None) -> str:
    if not role:
        return "user"
    r = role.strip().lower()
    if r in ("user", "human", "you"):
        return "user"
    if r in ("assistant", "ai", "bot", "model", "claude"):
        return "assistant"
    return "user"


def _extract_parts(content: Any) -> list[str]:
    """Extract verbatim text parts from a Claude Code `message.content` value.

    String content is the typical user prompt — returned untouched (the prompt
    is the sacred object; byte-identical pass-through). List content is walked
    block by block: `text` blocks are kept verbatim; `thinking`, `tool_use`,
    `tool_result`, and image blocks are skipped (no conversational text).
    """
    if isinstance(content, str):
        return [content] if content.strip() else []
    if not isinstance(content, list):
        return []
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            if block.strip():
                parts.append(block)
            continue
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text)
    return parts


def discover_input_files(input_paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for p in input_paths:
        if p.is_dir():
            files.extend(sorted(p.glob("*.jsonl")))
        elif p.suffix == ".jsonl" and p.exists():
            files.append(p)
        else:
            print(f"  skip (not found/not JSONL): {p}", file=sys.stderr)
    return files


def convert_directory(
    input_paths: list[Path],
    output_bundle: Path,
    *,
    include_sidechains: bool = False,
) -> dict:
    """Read Claude Code session JSONL files, write a standard bundle to output_bundle."""
    files = discover_input_files(input_paths)
    if not files:
        raise FileNotFoundError(f"no *.jsonl files found under any of: {input_paths}")

    # Group conversation events by session UUID
    sessions: dict[str, list[dict]] = {}
    seen_items: set[str] = set()  # dedup by event uuid (fallback: content hash)
    skipped_invalid = 0
    skipped_sidechain = 0
    lines_total = 0

    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"  skip (unreadable): {path.name} — {exc}", file=sys.stderr)
            continue

        last_ts = 0.0
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            lines_total += 1
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                skipped_invalid += 1
                continue
            if not isinstance(record, dict):
                skipped_invalid += 1
                continue

            if record.get("type") not in ("user", "assistant"):
                continue
            message = record.get("message")
            if not isinstance(message, dict):
                continue
            if record.get("isSidechain") and not include_sidechains:
                skipped_sidechain += 1
                continue

            role = _normalize_role(message.get("role") or record.get("type"))
            parts = _extract_parts(message.get("content"))
            if not parts:
                continue

            session_id = record.get("sessionId") or _session_id_from_path(path)

            # Dedup by native event uuid within same session (resumed sessions
            # replay earlier events); fall back to a content hash.
            event_uid = record.get("uuid")
            if not event_uid:
                joined = "\n".join(parts)
                event_uid = hashlib.md5(joined.encode("utf-8")).hexdigest()
            dedup_key = f"{session_id}:{event_uid}"
            if dedup_key in seen_items:
                continue
            seen_items.add(dedup_key)

            ts = _ensure_timestamp(record.get("timestamp"))
            if ts <= 0.0:
                ts = last_ts  # preserve file order for unstamped events
            else:
                last_ts = ts

            sessions.setdefault(session_id, []).append(
                {
                    "role": role,
                    "parts": parts,
                    "timestamp": ts,
                    "session": session_id,
                }
            )

    if not sessions:
        raise ValueError("no valid conversation events found in any input file")

    # Build conversations in bundle format
    conversations: list[dict] = []
    skipped_empty_session = 0
    messages_written = 0

    for session_id, items in sessions.items():
        # Stable sort: equal/carried timestamps keep original file order.
        items.sort(key=lambda x: x["timestamp"])
        if not items:
            skipped_empty_session += 1
            continue

        create_time = items[0]["timestamp"]
        update_time = items[-1]["timestamp"]

        mapping: dict[str, dict[str, Any]] = {}
        root_id = f"claude-code-root-{session_id}"
        mapping[root_id] = {
            "id": root_id,
            "parent": None,
            "children": [],
            "message": None,
        }

        prev_id = root_id
        for i, msg in enumerate(items, start=1):
            node_id = f"claude-code-msg-{session_id}-{i:04d}"
            mapping[node_id] = {
                "id": node_id,
                "parent": prev_id,
                "children": [],
                "message": {
                    "id": node_id,
                    "author": {"role": msg["role"]},
                    "create_time": msg["timestamp"],
                    "content": {"content_type": "text", "parts": msg["parts"]},
                },
            }
            mapping[prev_id]["children"].append(node_id)
            prev_id = node_id
            messages_written += 1

        conversations.append(
            {
                "title": f"Claude Code Session {session_id[:8]}",
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
        "messages_written": messages_written,
        "skipped_invalid_lines": skipped_invalid,
        "skipped_sidechain_events": skipped_sidechain,
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
        help="One or more directories or .jsonl files containing Claude Code session data",
    )
    parser.add_argument(
        "output_bundle",
        type=Path,
        help="Output bundle directory (will contain conversations.json + user.json)",
    )
    parser.add_argument(
        "--include-sidechains",
        action="store_true",
        help="Keep subagent (sidechain) events instead of skipping them",
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args()

    try:
        result = convert_directory(
            args.input_paths,
            args.output_bundle,
            include_sidechains=args.include_sidechains,
        )
    except (FileNotFoundError, ValueError, NotADirectoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Scanned: {result['files_scanned']} files ({result['lines_total']} lines)")
        print(
            f"Wrote:   {result['conversations_written']} conversations "
            f"({result['messages_written']} messages)"
        )
        print(
            f"Skipped: {result['skipped_invalid_lines']} invalid, "
            f"{result['skipped_sidechain_events']} sidechain, "
            f"{result['skipped_empty_sessions']} empty"
        )
        print(f"Bundle:  {result['output_bundle']}")
        print()
        print(
            "Next: cce provider import --provider chatgpt --source-path {}".format(
                result["output_bundle"]
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
