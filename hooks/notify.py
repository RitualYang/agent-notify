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
    "notification_variants": {
        "complete": {
            "subtitle": "执行完成",
            "message": "任务已完成，等待你查看结果。",
        },
        "question": {
            "subtitle": "等待回答",
            "message": "Agent 正在等待你的回答。",
        },
        "permission": {
            "subtitle": "等待授权",
            "message": "Agent 正在等待你的权限确认。",
        },
        "input": {
            "subtitle": "需要补充信息",
            "message": "Agent 需要你补充更多信息。",
        },
        "error": {
            "subtitle": "执行出错",
            "message": "运行过程中发生错误，请打开界面查看。",
        },
    },
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
    "codex": {
        "notify_on_stop": True,
        "stop_title": "Codex",
        "stop_message": "任务已完成，等待你查看结果。",
        "notification_title": "Codex",
    },
}

CLIENT_DEFAULT_TITLES = {
    "claude": "Claude Code",
    "cursor": "Cursor",
    "opencode": "OpenCode",
    "codex": "Codex",
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


def read_payload(raw_arg: str | None = None) -> dict[str, Any]:
    raw = (raw_arg or "").strip()
    if not raw:
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
    elif client == "codex":
        candidates = [
            payload.get("cwd"),
            payload.get("workdir"),
            payload.get("workspace_root"),
            payload.get("worktree"),
        ]
    else:
        candidates = []

    for candidate in candidates:
        project_name = path_basename(candidate)
        if project_name:
            return project_name
    return None


def variant_settings(config: dict[str, Any], kind: str) -> dict[str, Any]:
    variants = config.get("notification_variants", {})
    value = variants.get(kind, {}) if isinstance(variants, dict) else {}
    return value if isinstance(value, dict) else {}


def resolve_notification_title(client: str, kind: str, config: dict[str, Any]) -> str:
    client_config = config.get(client, {})
    if not isinstance(client_config, dict):
        client_config = {}

    if isinstance(client_config.get("title"), str):
        return str(client_config["title"])
    if kind == "complete" and isinstance(client_config.get("stop_title"), str):
        return str(client_config["stop_title"])
    if client == "cursor" and kind == "question" and isinstance(client_config.get("question_title"), str):
        return str(client_config["question_title"])
    if kind in {"question", "permission", "input", "error"} and isinstance(client_config.get("notification_title"), str):
        return str(client_config["notification_title"])
    return CLIENT_DEFAULT_TITLES.get(client, client.title())


def resolve_notification_message(
    client: str,
    kind: str,
    config: dict[str, Any],
    message: str | None,
) -> str:
    normalized = truncate(message) if message else ""
    if normalized:
        return normalized

    client_config = config.get(client, {})
    if not isinstance(client_config, dict):
        client_config = {}

    if kind == "complete" and isinstance(client_config.get("stop_message"), str):
        return str(client_config["stop_message"])
    if client == "cursor" and kind == "question" and isinstance(client_config.get("question_message"), str):
        return str(client_config["question_message"])

    variant = variant_settings(config, kind)
    if isinstance(variant.get("message"), str):
        return str(variant["message"])
    return ""


def resolve_notification_subtitle(kind: str, config: dict[str, Any], subtitle: str | None) -> str:
    if subtitle:
        return subtitle
    variant = variant_settings(config, kind)
    if isinstance(variant.get("subtitle"), str):
        return str(variant["subtitle"])
    return kind


def finalize_notification(client: str, notification: dict[str, str], config: dict[str, Any]) -> dict[str, str]:
    kind = str(notification["kind"])
    return {
        "kind": kind,
        "title": str(notification.get("title") or resolve_notification_title(client, kind, config)),
        "subtitle": resolve_notification_subtitle(kind, config, notification.get("subtitle")),
        "message": truncate(resolve_notification_message(client, kind, config, notification.get("message"))),
    }


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
    if event in {"agent-turn-complete"} or payload.get("transcript_path") or payload.get("turn_id"):
        return "codex"
    return "cursor"


def classify_claude(payload: dict[str, Any], config: dict[str, Any]) -> dict[str, str] | None:
    event = payload.get("hook_event_name")
    claude_config = config["claude"]
    if event == "Notification" and claude_config.get("notify_on_notification", True):
        notification_type = payload.get("notification_type")
        if notification_type not in claude_config.get("notification_types", []):
            return None
        kind_map = {
            "permission_prompt": "permission",
            "idle_prompt": "input",
            "elicitation_dialog": "question",
        }
        return {
            "kind": kind_map.get(str(notification_type), "input"),
            "message": str(payload.get("message") or ""),
        }

    if event in {"Stop", "SubagentStop"} and claude_config.get("notify_on_stop", True):
        return {
            "kind": "complete",
        }

    if event == "Elicitation" and claude_config.get("notify_on_notification", True):
        return {
            "kind": "question",
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
            "kind": "question",
            "message": text,
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
        }

    return None


def classify_opencode(payload: dict[str, Any], config: dict[str, Any]) -> dict[str, str] | None:
    event = str(payload.get("type") or payload.get("hook_event_name") or "")
    opencode_config = config["opencode"]

    if event == "session.idle" and opencode_config.get("notify_on_stop", True):
        return {
            "kind": "complete",
        }

    if event in opencode_config.get("notification_events", []) and opencode_config.get("notify_on_notification", True):
        kind = "permission" if event == "permission.asked" else "error"
        return {
            "kind": kind,
            "message": str(payload.get("message") or ""),
        }

    return None


def recent_transcript_lines(path: Path, limit_bytes: int = 65536) -> list[str]:
    if not path.exists():
        return []

    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        if size == 0:
            return []

        read_size = min(size, limit_bytes)
        handle.seek(size - read_size)
        chunk = handle.read().decode("utf-8", errors="ignore")

    lines = chunk.splitlines()
    if size > read_size and lines:
        lines = lines[1:]
    return lines


def codex_turn_id(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    for key in ("turn_id", "turnId", "turn-id"):
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def recent_codex_event(transcript_path: Any, turn_id: Any) -> dict[str, Any] | None:
    if not isinstance(transcript_path, str) or not transcript_path.strip():
        return None

    expected_turn_id = turn_id.strip() if isinstance(turn_id, str) and turn_id.strip() else None
    latest_event_without_turn_id: dict[str, Any] | None = None
    for line in reversed(recent_transcript_lines(Path(transcript_path))):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not isinstance(payload, dict) or payload.get("type") != "event_msg":
            continue

        event_payload = payload.get("payload")
        if not isinstance(event_payload, dict):
            continue

        if expected_turn_id:
            event_turn_id = codex_turn_id(event_payload) or codex_turn_id(payload)
            if not event_turn_id:
                if latest_event_without_turn_id is None:
                    latest_event_without_turn_id = event_payload
                continue
            if event_turn_id != expected_turn_id:
                continue

        return event_payload

    if expected_turn_id:
        return latest_event_without_turn_id

    return None


def classify_codex(payload: dict[str, Any], config: dict[str, Any]) -> dict[str, str] | None:
    event = str(payload.get("type") or payload.get("event") or payload.get("hook_event_name") or "")
    codex_config = config["codex"]

    if event == "agent-turn-complete" and codex_config.get("notify_on_stop", True):
        return {
            "kind": "complete",
            "message": str(payload.get("message") or payload.get("last_assistant_message") or ""),
        }

    if event != "Stop":
        return None

    kind_map = {
        "exec_approval_request": "permission",
        "apply_patch_approval_request": "permission",
        "elicitation_request": "question",
        "request_user_input": "input",
        "stream_error": "error",
    }

    transcript_event = recent_codex_event(payload.get("transcript_path"), codex_turn_id(payload))
    if not transcript_event:
        return None

    if not payload.get("cwd"):
        transcript_cwd = transcript_event.get("cwd")
        if isinstance(transcript_cwd, str) and transcript_cwd.strip():
            payload["cwd"] = transcript_cwd

    kind = kind_map.get(transcript_event.get("type"))
    if kind:
        return {
            "kind": kind,
            "message": str(payload.get("last_assistant_message") or payload.get("message") or ""),
        }

    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Send Claude Code / Cursor / OpenCode / Codex notifications on macOS.")
    parser.add_argument("--client", choices=["claude", "cursor", "opencode", "codex"], help="Force hook client type.")
    parser.add_argument("--source", help="Optional installer marker. Reserved for agent-notify.")
    parser.add_argument("--dry-run", action="store_true", help="Print notification payload instead of calling osascript.")
    parser.add_argument("--config", help="Path to config file. Defaults to ~/.agent-notify/config.json")
    parser.add_argument("--state", help="Path to state file. Defaults to ~/.agent-notify/state.json")
    parser.add_argument("payload", nargs="?", help="Optional serialized payload argument used by Codex notify callbacks.")
    args = parser.parse_args()

    base_dir = Path(os.path.expanduser("~/.agent-notify"))
    config_path = Path(os.path.expanduser(args.config)) if args.config else base_dir / "config.json"
    state_path = Path(os.path.expanduser(args.state)) if args.state else base_dir / "state.json"

    config = load_config(config_path)
    state = load_json(state_path, {}) if not args.dry_run else {}
    payload = read_payload(args.payload)
    client = detect_platform(payload, args.client)

    if client == "claude":
        notification = classify_claude(payload, config)
    elif client == "opencode":
        notification = classify_opencode(payload, config)
    elif client == "codex":
        notification = classify_codex(payload, config)
    else:
        notification = classify_cursor(payload, config, state)

    if not notification:
        if not args.dry_run:
            save_json(state_path, state)
        return 0

    notification = finalize_notification(client, notification, config)

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
