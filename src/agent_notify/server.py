from mcp.server.fastmcp import FastMCP
from agent_notify.notifiers.macos import send_macos_notification
from agent_notify.store import NotificationStore

mcp = FastMCP(name="agent-notify")
store = NotificationStore(max_size=100)


@mcp.tool()
def send_notification(title: str, message: str, sound: bool = True) -> str:
    """Send a desktop notification to the user. Call this tool every time you complete a task,
    encounter an error, or need the user's attention. The notification appears in macOS Notification Center."""
    success = send_macos_notification(title, message, sound=sound)
    store.add(title, message)
    if success:
        return f"Notification sent: {title}"
    else:
        return f"Failed to send notification: {title}"


@mcp.tool()
def list_notifications(limit: int = 10) -> list[dict]:
    """List recent notifications that have been sent. Returns the most recent notifications first."""
    return store.list(limit=limit)


@mcp.tool()
def get_config() -> dict:
    """Get the current notification configuration.
    Call this when you first connect to understand your notification responsibilities:
    You MUST call send_notification after completing any task or encountering errors."""
    return {
        "channels": ["macos"],
        "instruction": "You MUST call send_notification after completing any task or encountering an error.",
        "history_size": 100,
    }


def main():
    mcp.run()


if __name__ == "__main__":
    main()
