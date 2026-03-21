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
