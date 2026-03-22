#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path, PureWindowsPath
from typing import Any


DEFAULT_CONFIG = {
    "macos": {
        "sound": "Glass",
    },
    "dedupe_window_seconds": 2,
    "claude": {
        "notify_on_stop": True,
        "notify_on_notification": True,
        "notification_types": [
            "permission_prompt",
            "idle_prompt",
            "elicitation_dialog",
        ],
        "stop_title": "Claude Code",
        "stop_message": "任务已完成，等待你查看结果。",
        "notification_title": "Claude Code",
    },
    "cursor": {
        "notify_on_stop": True,
        "notify_on_question": True,
        "stop_title": "Cursor",
        "stop_message": "Agent 已执行完毕，等待你查看结果。",
        "question_title": "Cursor",
        "question_message": "Agent 需要你确认或提供更多信息。",
        "suppress_stop_after_question_seconds": 8,
        "question_patterns": [
            r"\?",
            r"\bwould you like\b",
            r"\bdo you want\b",
            r"\bshould i\b",
            r"\bcould you\b",
            r"\bcan you\b",
            r"\bplease confirm\b",
            r"\bplease provide\b",
            r"\blet me know\b",
            r"\bwhich option\b",
            r"\bwhat would you like\b",
            r"请确认",
            r"请提供",
            r"请问",
            r"请选择",
            r"你希望",
            r"你想要",
            r"是否需要",
            r"要不要",
        ],
    },
    "opencode": {
        "notify_on_stop": True,
        "notify_on_notification": True,
        "stop_title": "OpenCode",
        "stop_message": "会话已进入空闲状态，等待你查看结果。",
        "notification_title": "OpenCode",
        "notification_events": [
            "permission.asked",
            "session.error",
        ],
    },
}


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_config(config_path: Path) -> dict[str, Any]:
    return deep_merge(DEFAULT_CONFIG, load_json(config_path, {}))


def read_payload() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}
    return payload if isinstance(payload, dict) else {"payload": payload}


def applescript_quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def send_notification(title: str, message: str, subtitle: str | None, sound: str | None) -> None:
    script = f'display notification "{applescript_quote(message)}" with title "{applescript_quote(title)}"'
    if subtitle:
        script += f' subtitle "{applescript_quote(subtitle)}"'
    if sound:
        script += f' sound name "{applescript_quote(sound)}"'
    subprocess.run(["osascript", "-e", script], check=False)


def truncate(text: str, limit: int = 120) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def path_basename(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip().rstrip("/\\")
    if not cleaned:
        return None
    if "\\" in cleaned:
        name = PureWindowsPath(cleaned).name
    else:
        name = Path(cleaned).name
    return name or None


def first_path_in_list(value: Any) -> str | None:
    if not isinstance(value, list):
        return None
    for item in value:
        name = path_basename(item)
        if name:
            return item
    return None


def format_subtitle(project_name: str | None, subtitle: str | None) -> str | None:
    if project_name and subtitle:
        return f"{project_name} · {subtitle}"
    if project_name:
        return project_name
    return subtitle


def resolve_project_name(payload: dict[str, Any], client: str) -> str | None:
    opencode_context = payload.get("project_context", {})
    if not isinstance(opencode_context, dict):
        opencode_context = {}

    if client == "claude":
        candidates = [
            payload.get("cwd"),
            os.environ.get("CLAUDE_PROJECT_DIR"),
        ]
    elif client == "cursor":
        candidates = [
            first_path_in_list(payload.get("workspace_roots")),
            first_path_in_list(payload.get("workspaceRoots")),
            payload.get("cwd"),
            os.getcwd(),
        ]
    elif client == "opencode":
        candidates = [
            opencode_context.get("directory"),
            payload.get("directory"),
            opencode_context.get("worktree"),
            payload.get("worktree"),
        ]
    else:
        candidates = []

    for candidate in candidates:
        project_name = path_basename(candidate)
        if project_name:
            return project_name
    return None


def recent_duplicate(state: dict[str, Any], key: str, window_seconds: int) -> bool:
    last = state.get("last_notification", {})
    return last.get("key") == key and (time.time() - float(last.get("timestamp", 0))) < window_seconds


def remember_notification(state: dict[str, Any], key: str) -> None:
    state["last_notification"] = {
        "key": key,
        "timestamp": time.time(),
    }


def remember_cursor_question(state: dict[str, Any], payload: dict[str, Any]) -> None:
    state["last_cursor_question"] = {
        "conversation_id": payload.get("conversation_id"),
        "timestamp": time.time(),
    }


def suppress_cursor_stop(state: dict[str, Any], payload: dict[str, Any], seconds: int) -> bool:
    question = state.get("last_cursor_question", {})
    if not question:
        return False
    if question.get("conversation_id") != payload.get("conversation_id"):
        return False
    return (time.time() - float(question.get("timestamp", 0))) < seconds


def detect_platform(payload: dict[str, Any], client_arg: str | None) -> str:
    if client_arg:
        return client_arg
    event = str(payload.get("hook_event_name") or payload.get("type") or "")
    if event in {"Notification", "Stop", "SubagentStop", "Elicitation"}:
        return "claude"
    if event in {"session.idle", "permission.asked", "session.error"}:
        return "opencode"
    return "cursor"


def classify_claude(payload: dict[str, Any], config: dict[str, Any]) -> dict[str, str] | None:
    event = payload.get("hook_event_name")
    claude_config = config["claude"]
    if event == "Notification" and claude_config.get("notify_on_notification", True):
        notification_type = payload.get("notification_type")
        if notification_type not in claude_config.get("notification_types", []):
            return None
        title = str(payload.get("title") or claude_config.get("notification_title") or "Claude Code")
        message = str(payload.get("message") or "Claude Code 需要你处理一个新事件。")
        return {
            "kind": "ask",
            "title": title,
            "subtitle": str(notification_type or "需要输入"),
            "message": truncate(message),
        }

    if event in {"Stop", "SubagentStop"} and claude_config.get("notify_on_stop", True):
        return {
            "kind": "complete",
            "title": str(claude_config.get("stop_title") or "Claude Code"),
            "subtitle": "执行完成",
            "message": str(claude_config.get("stop_message") or "任务已完成，等待你查看结果。"),
        }

    if event == "Elicitation" and claude_config.get("notify_on_notification", True):
        return {
            "kind": "ask",
            "title": str(claude_config.get("notification_title") or "Claude Code"),
            "subtitle": "需要输入",
            "message": "Claude Code 正在等待你的回答。",
        }

    return None


def is_cursor_question(text: str, config: dict[str, Any]) -> bool:
    if not text.strip():
        return False
    for pattern in config["cursor"].get("question_patterns", []):
        if re.search(pattern, text, flags=re.IGNORECASE):
            return True
    return False


def classify_cursor(payload: dict[str, Any], config: dict[str, Any], state: dict[str, Any]) -> dict[str, str] | None:
    event = payload.get("hook_event_name")
    cursor_config = config["cursor"]

    if event == "afterAgentResponse" and cursor_config.get("notify_on_question", True):
        text = str(payload.get("text") or payload.get("response") or "")
        if not is_cursor_question(text, config):
            return None
        remember_cursor_question(state, payload)
        return {
            "kind": "ask",
            "title": str(cursor_config.get("question_title") or "Cursor"),
            "subtitle": "需要确认",
            "message": truncate(text) or str(cursor_config.get("question_message")),
        }

    if event == "stop" and cursor_config.get("notify_on_stop", True):
        status = str(payload.get("status") or "completed")
        if status != "completed":
            return None
        if suppress_cursor_stop(
            state,
            payload,
            int(cursor_config.get("suppress_stop_after_question_seconds", 8)),
        ):
            return None
        return {
            "kind": "complete",
            "title": str(cursor_config.get("stop_title") or "Cursor"),
            "subtitle": "执行完成",
            "message": str(cursor_config.get("stop_message") or "Agent 已执行完毕，等待你查看结果。"),
        }

    return None


def classify_opencode(payload: dict[str, Any], config: dict[str, Any]) -> dict[str, str] | None:
    event = str(payload.get("type") or payload.get("hook_event_name") or "")
    opencode_config = config["opencode"]

    if event == "session.idle" and opencode_config.get("notify_on_stop", True):
        return {
            "kind": "complete",
            "title": str(opencode_config.get("stop_title") or "OpenCode"),
            "subtitle": "执行完成",
            "message": str(opencode_config.get("stop_message") or "会话已进入空闲状态，等待你查看结果。"),
        }

    if event in opencode_config.get("notification_events", []) and opencode_config.get("notify_on_notification", True):
        message = str(payload.get("message") or "OpenCode 需要你处理一个新事件。")
        subtitle = "需要确认" if event == "permission.asked" else event
        if event == "permission.asked" and not payload.get("message"):
            message = "OpenCode 正在等待你的权限确认。"
        if event == "session.error" and not payload.get("message"):
            message = "OpenCode 会话发生错误，请打开界面查看。"
        return {
            "kind": "ask",
            "title": str(opencode_config.get("notification_title") or "OpenCode"),
            "subtitle": subtitle,
            "message": truncate(message),
        }

    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Send Claude Code / Cursor / OpenCode notifications on macOS.")
    parser.add_argument("--client", choices=["claude", "cursor", "opencode"], help="Force hook client type.")
    parser.add_argument("--source", help="Optional installer marker. Reserved for agent-notify.")
    parser.add_argument("--dry-run", action="store_true", help="Print notification payload instead of calling osascript.")
    parser.add_argument("--config", help="Path to config file. Defaults to ~/.agent-notify/config.json")
    parser.add_argument("--state", help="Path to state file. Defaults to ~/.agent-notify/state.json")
    args = parser.parse_args()

    base_dir = Path(os.path.expanduser("~/.agent-notify"))
    config_path = Path(os.path.expanduser(args.config)) if args.config else base_dir / "config.json"
    state_path = Path(os.path.expanduser(args.state)) if args.state else base_dir / "state.json"

    config = load_config(config_path)
    state = load_json(state_path, {}) if not args.dry_run else {}
    payload = read_payload()
    client = detect_platform(payload, args.client)

    if client == "claude":
        notification = classify_claude(payload, config)
    elif client == "opencode":
        notification = classify_opencode(payload, config)
    else:
        notification = classify_cursor(payload, config, state)

    if not notification:
        if not args.dry_run:
            save_json(state_path, state)
        return 0

    notification["subtitle"] = format_subtitle(
        resolve_project_name(payload, client),
        notification.get("subtitle"),
    )

    key = "|".join(
        [
            client,
            notification["kind"],
            notification["title"],
            notification["subtitle"],
            notification["message"],
            str(payload.get("conversation_id") or ""),
            str(payload.get("notification_type") or ""),
            str(payload.get("type") or ""),
        ]
    )

    if not args.dry_run and recent_duplicate(state, key, int(config.get("dedupe_window_seconds", 2))):
        save_json(state_path, state)
        return 0

    if not args.dry_run:
        remember_notification(state, key)
        save_json(state_path, state)
        send_notification(
            title=notification["title"],
            subtitle=notification.get("subtitle"),
            message=notification["message"],
            sound=config.get("macos", {}).get("sound"),
        )
        return 0

    print(
        json.dumps(
            {
                "client": client,
                "notification": notification,
                "payload": payload,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
