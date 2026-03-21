# agent-notify Design

## Overview

A Python MCP Server that sends macOS desktop notifications when AI coding agents complete tasks. Works across Claude Code, Cursor, Trae, OpenCode, and any MCP-compatible tool. Automatic triggering via system prompt instructions — no explicit user prompt required.

## Architecture

```
AI Client (Claude Code / Cursor / Trae / OpenCode)
    │ stdio (JSON-RPC)
    ▼
agent-notify MCP Server (Python)
    │
    ├─ Tool: send_notification(title, message, sound?)
    ├─ Tool: list_notifications(limit?)
    ├─ Tool: get_config()
    │
    ▼
macOS Notification Center (osascript)
```

## Project Structure

```
agent-notify/
├── src/
│   └── agent_notify/
│       ├── __init__.py
│       ├── server.py          # MCP server entry point
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── notify.py      # send_notification tool
│       │   └── history.py     # list_notifications tool
│       └── notifiers/
│           ├── __init__.py
│           └── macos.py       # osascript notification implementation
├── pyproject.toml             # Package config + CLI entry point
└── README.md
```

## MCP Tools

### `send_notification`
- `title`: string (required) — notification title
- `message`: string (required) — notification body
- `sound`: boolean (optional, default true) — play alert sound

### `list_notifications`
- `limit`: number (optional, default 10) — return last N notifications

### `get_config`
- Returns current notification config (channels, status)
- AI can call this on first connection to understand its responsibilities

## Transport

- **Protocol**: MCP JSON-RPC over stdio (StdioServerTransport)
- **No HTTP**: zero port usage, pure subprocess communication

## Auto-Trigger Strategy

System prompt instructions in each tool's config file:

```
Every time you complete a task or encounter an error that needs user attention,
you MUST call the send_notification tool to notify the user.
```

- Claude Code: `CLAUDE.md`
- Cursor: `.cursorrules`
- Trae: `.trae/rules`

## Integration

```bash
# Install
pip install agent-notify   # or: uvx agent-notify

# Claude Code
claude mcp add notify -- uvx agent-notify

# Cursor (.cursor/mcp.json)
{ "mcpServers": { "notify": { "command": "uvx", "args": ["agent-notify"] } } }
```

## Notification History

In-memory store of last 100 notifications. Not persisted. Cleared on process restart.

## Future Extensions

- Slack / Telegram / DingTalk webhook channels
- Notification filtering rules
- Cross-platform support (Linux notify-send, Windows toast)
