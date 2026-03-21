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
