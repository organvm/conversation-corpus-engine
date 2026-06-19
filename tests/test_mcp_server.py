from __future__ import annotations

from pathlib import Path

from conversation_corpus_engine.federation import build_federation, upsert_corpus
from conversation_corpus_engine.import_markdown_document_corpus import (
    import_markdown_document_corpus,
)
from conversation_corpus_engine.mcp_server import (
    MCP_PROTOCOL_VERSION,
    call_tool,
    handle_jsonrpc_message,
)


def test_initialize_advertises_read_only_tool_capability() -> None:
    response = handle_jsonrpc_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": MCP_PROTOCOL_VERSION},
        }
    )

    assert response is not None
    assert response["result"]["protocolVersion"] == MCP_PROTOCOL_VERSION
    assert response["result"]["capabilities"] == {"tools": {"listChanged": False}}
    assert response["result"]["serverInfo"]["name"] == "conversation-corpus-engine"


def test_tools_list_exposes_corpus_search_tool() -> None:
    response = handle_jsonrpc_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})

    assert response is not None
    tools = response["result"]["tools"]
    search_tool = next(item for item in tools if item["name"] == "cce_search")
    assert search_tool["annotations"]["readOnlyHint"] is True
    assert "query" in search_tool["inputSchema"]["required"]


def test_cce_search_tool_returns_structured_answer_from_registered_corpus(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    source_root = tmp_path / "source"
    corpus_root = tmp_path / "commercial-memory"
    source_root.mkdir()
    (source_root / "memory.md").write_text(
        "# Commercial Memory\n\nSearch all AI conversations from one place and package the MCP server.\n",
        encoding="utf-8",
    )
    import_markdown_document_corpus(
        source_root,
        corpus_root,
        corpus_id="commercial-memory",
        name="Commercial Memory",
    )
    upsert_corpus(
        project_root,
        corpus_root,
        corpus_id="commercial-memory",
        name="Commercial Memory",
        make_default=True,
    )
    build_federation(project_root)

    result = call_tool(
        "cce_search",
        {
            "project_root": str(project_root),
            "query": "commercial memory MCP server",
            "limit": 4,
        },
    )

    assert result["isError"] is False
    assert result["content"][0]["type"] == "text"
    assert result["structuredContent"]["query"] == "commercial memory MCP server"
    assert (
        result["structuredContent"]["federation"]["selected_corpus"]["corpus_id"]
        == "commercial-memory"
    )
