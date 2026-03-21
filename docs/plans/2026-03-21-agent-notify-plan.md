# agent-notify Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python MCP Server that sends macOS desktop notifications, triggered automatically by AI coding agents via system prompt instructions.

**Architecture:** FastMCP-based stdio server exposing `send_notification`, `list_notifications`, and `get_config` tools. Notifications dispatched via `osascript`. Auto-triggered by system prompt rules in CLAUDE.md / .cursorrules / .trae/rules.

**Tech Stack:** Python 3.10+, `mcp[cli]` (FastMCP), `osascript` (macOS native), `uv` for packaging

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/agent_notify/__init__.py`
- Create: `src/agent_notify/server.py` (stub)

**Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "agent-notify"
version = "0.1.0"
description = "MCP Server for desktop notifications from AI coding agents"
requires-python = ">=3.10"
dependencies = [
    "mcp[cli]>=1.0.0",
]

[project.scripts]
agent-notify = "agent_notify.server:main"
```

**Step 2: Create package init**

```python
# src/agent_notify/__init__.py
"""agent-notify: MCP Server for desktop notifications."""
```

**Step 3: Create server stub**

```python
# src/agent_notify/server.py
from mcp import FastMCP

mcp = FastMCP(name="agent-notify")

def main():
    mcp.run()

if __name__ == "__main__":
    main()
```

**Step 4: Initialize project with uv**

Run: `cd /Users/wty/agent-notify && uv sync`
Expected: Dependencies installed, .venv created

**Step 5: Verify server starts**

Run: `cd /Users/wty/agent-notify && echo '{}' | timeout 3 uv run agent-notify 2>&1 || true`
Expected: Server starts without crash (may timeout — that's fine, it's waiting for stdio input)

**Step 6: Init git and commit**

```bash
cd /Users/wty/agent-notify
git init
echo -e "__pycache__/\n*.pyc\n.venv/\ndist/\n*.egg-info/" > .gitignore
git add .
git commit -m "feat: project scaffolding with FastMCP server stub"
```

---

### Task 2: macOS Notifier

**Files:**
- Create: `src/agent_notify/notifiers/__init__.py`
- Create: `src/agent_notify/notifiers/macos.py`
- Create: `tests/test_macos_notifier.py`

**Step 1: Write the failing test**

```python
# tests/test_macos_notifier.py
import subprocess
from unittest.mock import patch, MagicMock
from agent_notify.notifiers.macos import send_macos_notification


def test_send_notification_calls_osascript():
    with patch("agent_notify.notifiers.macos.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = send_macos_notification("Test Title", "Test Message")
        assert result is True
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "osascript"
        assert "Test Title" in args[1]
        assert "Test Message" in args[1]


def test_send_notification_with_sound():
    with patch("agent_notify.notifiers.macos.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        send_macos_notification("Title", "Msg", sound=True)
        args = mock_run.call_args[0][0]
        assert "sound name" in args[1].lower() or "Sound" in args[1]


def test_send_notification_without_sound():
    with patch("agent_notify.notifiers.macos.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        send_macos_notification("Title", "Msg", sound=False)
        args = mock_run.call_args[0][0]
        assert "sound name" not in args[1].lower()


def test_send_notification_failure():
    with patch("agent_notify.notifiers.macos.subprocess.run") as mock_run:
        mock_run.side_effect = Exception("osascript not found")
        result = send_macos_notification("Title", "Msg")
        assert result is False
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/wty/agent-notify && uv run pytest tests/test_macos_notifier.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_notify.notifiers'`

**Step 3: Write minimal implementation**

```python
# src/agent_notify/notifiers/__init__.py
```

```python
# src/agent_notify/notifiers/macos.py
import subprocess


def send_macos_notification(title: str, message: str, sound: bool = True) -> bool:
    """Send a macOS desktop notification via osascript."""
    script = f'display notification "{message}" with title "{title}"'
    if sound:
        script += ' sound name "Glass"'
    try:
        subprocess.run(["osascript", "-e", script], check=True, timeout=5)
        return True
    except Exception:
        return False
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/wty/agent-notify && uv run pytest tests/test_macos_notifier.py -v`
Expected: 4 passed

**Step 5: Commit**

```bash
git add src/agent_notify/notifiers/ tests/
git commit -m "feat: macOS notifier with osascript"
```

---

### Task 3: Notification History Store

**Files:**
- Create: `src/agent_notify/store.py`
- Create: `tests/test_store.py`

**Step 1: Write the failing test**

```python
# tests/test_store.py
from agent_notify.store import NotificationStore


def test_store_add_and_list():
    store = NotificationStore(max_size=5)
    store.add("Title 1", "Message 1")
    store.add("Title 2", "Message 2")
    items = store.list(limit=10)
    assert len(items) == 2
    assert items[0]["title"] == "Title 2"  # most recent first
    assert items[1]["title"] == "Title 1"


def test_store_max_size():
    store = NotificationStore(max_size=3)
    for i in range(5):
        store.add(f"Title {i}", f"Message {i}")
    items = store.list(limit=10)
    assert len(items) == 3


def test_store_list_limit():
    store = NotificationStore(max_size=100)
    for i in range(10):
        store.add(f"Title {i}", f"Message {i}")
    items = store.list(limit=3)
    assert len(items) == 3


def test_store_item_has_timestamp():
    store = NotificationStore()
    store.add("T", "M")
    items = store.list()
    assert "timestamp" in items[0]
    assert "title" in items[0]
    assert "message" in items[0]
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/wty/agent-notify && uv run pytest tests/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# src/agent_notify/store.py
from collections import deque
from datetime import datetime, timezone


class NotificationStore:
    def __init__(self, max_size: int = 100):
        self._items: deque[dict] = deque(maxlen=max_size)

    def add(self, title: str, message: str) -> dict:
        item = {
            "title": title,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._items.appendleft(item)
        return item

    def list(self, limit: int = 10) -> list[dict]:
        return list(self._items)[:limit]
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/wty/agent-notify && uv run pytest tests/test_store.py -v`
Expected: 4 passed

**Step 5: Commit**

```bash
git add src/agent_notify/store.py tests/test_store.py
git commit -m "feat: in-memory notification history store"
```

---

### Task 4: MCP Tools — send_notification

**Files:**
- Modify: `src/agent_notify/server.py`
- Create: `tests/test_tools.py`

**Step 1: Write the failing test**

```python
# tests/test_tools.py
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mcp_server():
    """Import the server's FastMCP instance."""
    from agent_notify.server import mcp
    return mcp


def test_send_notification_tool_registered(mcp_server):
    """Verify send_notification is registered as a tool."""
    # FastMCP stores tools internally
    assert "send_notification" in [t.name for t in mcp_server._tool_manager.list_tools()]


def test_list_notifications_tool_registered(mcp_server):
    assert "list_notifications" in [t.name for t in mcp_server._tool_manager.list_tools()]


def test_get_config_tool_registered(mcp_server):
    assert "get_config" in [t.name for t in mcp_server._tool_manager.list_tools()]
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/wty/agent-notify && uv run pytest tests/test_tools.py -v`
Expected: FAIL — tool not found

**Step 3: Write full server implementation**

```python
# src/agent_notify/server.py
from mcp import FastMCP
from agent_notify.notifiers.macos import send_macos_notification
from agent_notify.store import NotificationStore

mcp = FastMCP(name="agent-notify")
store = NotificationStore(max_size=100)


@mcp.tool
def send_notification(title: str, message: str, sound: bool = True) -> str:
    """Send a desktop notification to the user. Call this tool every time you complete a task,
    encounter an error, or need the user's attention. The notification appears in macOS Notification Center."""
    success = send_macos_notification(title, message, sound=sound)
    store.add(title, message)
    if success:
        return f"Notification sent: {title}"
    else:
        return f"Failed to send notification: {title}"


@mcp.tool
def list_notifications(limit: int = 10) -> list[dict]:
    """List recent notifications that have been sent. Returns the most recent notifications first."""
    return store.list(limit=limit)


@mcp.tool
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
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/wty/agent-notify && uv run pytest tests/test_tools.py -v`
Expected: 3 passed

**Step 5: Run all tests**

Run: `cd /Users/wty/agent-notify && uv run pytest -v`
Expected: All 11 tests passed

**Step 6: Commit**

```bash
git add src/agent_notify/server.py tests/test_tools.py
git commit -m "feat: MCP tools - send_notification, list_notifications, get_config"
```

---

### Task 5: End-to-End Verification

**Files:**
- None created

**Step 1: Test server starts and responds to MCP inspector**

Run: `cd /Users/wty/agent-notify && uv run mcp dev src/agent_notify/server.py`
Expected: MCP Inspector UI opens, shows 3 tools registered

If `mcp dev` is not available, test via direct invocation:
Run: `cd /Users/wty/agent-notify && echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1.0"}}}' | uv run agent-notify 2>/dev/null | head -1`
Expected: JSON response with server capabilities

**Step 2: Test real macOS notification**

Run: `cd /Users/wty/agent-notify && python3 -c "from agent_notify.notifiers.macos import send_macos_notification; send_macos_notification('agent-notify', 'Setup complete!')"`
Expected: macOS notification appears on screen

**Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix: end-to-end verification fixes" --allow-empty
```

---

### Task 6: Integration Config Files

**Files:**
- Create: `CLAUDE.md` (system prompt for Claude Code)

**Step 1: Create CLAUDE.md**

```markdown
# Agent Notify

This project has agent-notify MCP server configured.

## Notification Rules

Every time you complete a task or encounter an error that needs user attention,
you MUST call the `send_notification` tool with:
- `title`: Brief summary (e.g., "Task Complete", "Build Failed")
- `message`: What was done or what went wrong
- `sound`: true for errors, true for task completion
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add CLAUDE.md with notification rules"
```

---

### Task 7: Package and Install

**Files:**
- None created

**Step 1: Build package**

Run: `cd /Users/wty/agent-notify && uv build`
Expected: `dist/agent_notify-0.1.0-py3-none-any.whl` created

**Step 2: Register with Claude Code**

Run: `claude mcp add notify -- uv run --directory /Users/wty/agent-notify agent-notify`
Expected: MCP server registered

**Step 3: Verify registration**

Run: `claude mcp list`
Expected: `notify` appears in list

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: finalize packaging"
```
