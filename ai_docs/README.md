# AI Documentation Sources

This directory contains cached documentation for the ADW expert system.

## Documentation Sources

The following documentation sources are available for loading into the expert system:

- **claude_code_sdk**: https://docs.anthropic.com/claude-code/sdk
  - Claude Code SDK documentation for building custom agents

- **claude_code_hooks**: https://docs.anthropic.com/claude-code/hooks
  - Documentation on Claude Code hooks system for observability

- **claude_code_mcp**: https://docs.anthropic.com/claude-code/mcp
  - Model Context Protocol (MCP) documentation for Claude Code integrations

- **anthropic_api**: https://docs.anthropic.com/api
  - Anthropic API documentation for Claude models

## Usage

Load documentation using the `/load_ai_docs` command:

```bash
# Load all documentation sources
/load_ai_docs

# Load specific documentation
/load_ai_docs claude_code_sdk
/load_ai_docs anthropic_api
```

## Cached Files

After loading, documentation will be cached in this directory as:
- `claude_code_sdk.md`
- `claude_code_hooks.md`
- `claude_code_mcp.md`
- `anthropic_api.md`

Each cached file includes a fetch timestamp for tracking freshness.
