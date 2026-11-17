# DataX Spain & EU Oracle: MCP bridge

Zero-dependency stdio MCP server (Python 3.9+ stdlib). Self-test: `python mcp_bridge.py --self-check`

```json
{
  "mcpServers": {
    "datax-spain-eu": {
      "command": "python3",
      "args": ["/absolute/path/to/mcp_bridge.py"],
      "env": {
        "DATAX_BASE_URL": "https://datax-es.duckdns.org",
        "DATAX_TOKEN": "<token from /api/v1/issue-token>"
      }
    }
  }
}
```

On Windows use `"command": "python"` (or `"py"`) and a path like `"C:/path/to/mcp_bridge.py"`.

See [SKILL.md](SKILL.md) for pricing, payment flow and token recovery.
