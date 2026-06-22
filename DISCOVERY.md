# Discovery: organvm/conversation-corpus-engine

**Discovered:** 2026-06-22 | **Verdict:** REAL VALUE — promoted to ranked tier

## Value Thesis

`conversation-corpus-engine` is a zero-dependency, pipx-installable Python engine (33 modules, 277 tests, 11 JSON schema contracts, MIT license) that ingests AI conversation histories from 8 providers — ChatGPT, Claude, Gemini, Grok, Perplexity, Copilot, DeepSeek, Mistral — materializes them into structured, searchable corpora, and exposes them over the Model Context Protocol via the `cce-mcp` stdio server. Its highest latent value is as a **personal AI memory layer for MCP-connected agents**: any Claude Desktop or compatible agent session can call `cce_search` to retrieve grounded, cited answers from years of cross-provider conversation history, locally, with no external API or cloud service required. The engine ships with a full governance stack (promotion policy lifecycle, federated canon review queue, regression evaluation gates) that positions it not just as a personal tool but as an institutional memory system for organizations running multi-provider AI workflows. A commercial architecture spec already exists targeting Ring 1 (SaaS, $29/mo consumer) and Ring 2 (usage-based Platform API + MCP server), with Ring 4 enterprise services as the high-margin path. The single biggest friction point blocking organic adoption: **the package is not on PyPI** — requiring `pipx install git+https://github.com/...` instead of the discoverable `pip install conversation-corpus-engine`.

## Highest Latent Value

**MCP-native personal AI memory.** The `cce-mcp` entry point is a fully compliant JSON-RPC 2.0 MCP server with three tools (`cce_search`, `cce_list_corpora`, `cce_surface_context`) that can be wired into Claude Desktop in two lines of config. No other open-source tool federates across 8 AI providers, runs fully local, has zero runtime dependencies, and ships over MCP. This is a genuine capability gap in the current MCP ecosystem.

## First Concrete Task

**Publish to PyPI.** Add a `publish.yml` GitHub Actions workflow that triggers on version tag push (`v*`), builds the sdist/wheel, and uploads to PyPI via `pypa/gh-action-pypi-publish`. Once live, `pip install conversation-corpus-engine` and `pipx install conversation-corpus-engine[mcp]` work from any terminal — making the MCP server discoverable to the developer community and enabling Ring 1/Ring 2 commercial progression.
