#!/usr/bin/env python3
"""Zero-dependency CLI for Claude Code hooks to send macOS notifications."""
import argparse
import subprocess
import sys


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def notify(title: str, message: str, sound: bool = True) -> bool:
    script = f'display notification "{_escape(message)}" with title "{_escape(title)}"'
    if sound:
        script += ' sound name "Glass"'
    try:
        subprocess.run(["osascript", "-e", script], check=True, timeout=5)
        return True
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", default="Claude Code")
    parser.add_argument("--message", default="Task complete")
    parser.add_argument("--no-sound", action="store_true")
    args = parser.parse_args()
    ok = notify(args.title, args.message, sound=not args.no_sound)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
