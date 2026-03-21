import pytest


@pytest.fixture
def mcp_server():
    """Import the server's FastMCP instance."""
    from agent_notify.server import mcp
    return mcp


def test_send_notification_tool_registered(mcp_server):
    """Verify send_notification is registered as a tool."""
    tool_names = [t.name for t in mcp_server._tool_manager.list_tools()]
    assert "send_notification" in tool_names


def test_list_notifications_tool_registered(mcp_server):
    tool_names = [t.name for t in mcp_server._tool_manager.list_tools()]
    assert "list_notifications" in tool_names


def test_get_config_tool_registered(mcp_server):
    tool_names = [t.name for t in mcp_server._tool_manager.list_tools()]
    assert "get_config" in tool_names
