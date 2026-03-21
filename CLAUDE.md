# Agent Notify

This project has agent-notify MCP server configured.

## Notification Rules

Every time you complete a task or encounter an error that needs user attention,
you MUST call the `send_notification` tool with:
- `title`: Brief summary (e.g., "Task Complete", "Build Failed")
- `message`: What was done or what went wrong
- `sound`: true for errors, true for task completion
