import subprocess


def _escape_applescript(s: str) -> str:
    """Escape a string for use in AppleScript double-quoted strings."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def send_macos_notification(title: str, message: str, sound: bool = True) -> bool:
    """Send a macOS desktop notification via osascript."""
    escaped_title = _escape_applescript(title)
    escaped_message = _escape_applescript(message)
    script = f'display notification "{escaped_message}" with title "{escaped_title}"'
    if sound:
        script += ' sound name "Glass"'
    try:
        subprocess.run(["osascript", "-e", script], check=True, timeout=5)
        return True
    except Exception:
        return False
