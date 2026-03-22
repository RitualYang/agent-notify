#!/usr/bin/env python3

from __future__ import annotations

from copy import deepcopy
import json
import os
import shlex
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SUPPORTED_CLIENTS = ("claude", "cursor", "opencode")
KNOWN_CLIENTS = ("claude", "cursor", "opencode", "codex")
CLIENT_ALIASES = {
    "all": SUPPORTED_CLIENTS,
    "both": ("claude", "cursor"),
    "none": (),
    "clear": (),
}
AGENT_NOTIFY_SOURCE = "agent-notify"


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    supported: bool
    note: str | None = None


DEFAULT_RUNTIME_DIR = Path(os.path.expanduser("~/.agent-notify")).resolve()
DEFAULT_CLAUDE_SETTINGS = Path(os.path.expanduser("~/.claude/settings.json"))
DEFAULT_CURSOR_HOOKS = Path(os.path.expanduser("~/.cursor/hooks.json"))
DEFAULT_OPENCODE_PLUGIN = Path(os.path.expanduser("~/.config/opencode/plugins/agent-notify.js"))

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_SOURCE = REPO_ROOT / "hooks" / "notify.py"
OPENCODE_TEMPLATE = REPO_ROOT / "plugins" / "opencode" / "agent-notify.js.template"

DEFAULT_CONFIG = {
    "macos": {"sound": "Glass"},
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
        "question_message": "Agent 正在等待你的回答。",
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


PROVIDERS: dict[str, ProviderSpec] = {
    "claude": ProviderSpec(name="claude", supported=True),
    "cursor": ProviderSpec(name="cursor", supported=True),
    "opencode": ProviderSpec(name="opencode", supported=True),
    "codex": ProviderSpec(
        name="codex",
        supported=False,
        note="当前未发现 Codex CLI 稳定的用户级 hooks / plugin 接口，已预留 provider 架构，后续可补上。",
    ),
}


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


def merge_missing_defaults(existing: Any, defaults: Any) -> Any:
    if isinstance(existing, dict) and isinstance(defaults, dict):
        merged = dict(existing)
        for key, value in defaults.items():
            if key not in merged:
                merged[key] = deepcopy(value)
                continue
            merged[key] = merge_missing_defaults(merged[key], value)
        return merged
    return existing


def ensure_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def command_for(script_path: Path, client: str) -> str:
    return f"{shlex.quote(str(script_path))} --client {client} --source {AGENT_NOTIFY_SOURCE}"


def normalize_clients(raw_clients: list[str] | None, default_clients: tuple[str, ...]) -> list[str]:
    normalized: list[str] = []
    pending = raw_clients or list(default_clients)
    for item in pending:
        for part in str(item).split(","):
            client_name = part.strip().lower()
            if not client_name:
                continue
            expanded = CLIENT_ALIASES.get(client_name, (client_name,))
            for client in expanded:
                if client not in normalized:
                    normalized.append(client)
    return normalized


def remove_empty_hook_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for entry in entries:
        hooks = entry.get("hooks")
        if isinstance(hooks, list):
            if hooks:
                filtered.append(entry)
            continue
        filtered.append(entry)
    return filtered


def prune_empty_objects(data: dict[str, Any]) -> dict[str, Any]:
    hooks = data.get("hooks")
    if isinstance(hooks, dict):
        empty_keys = [key for key, value in hooks.items() if value in ({}, [], None)]
        for key in empty_keys:
            hooks.pop(key, None)
        if not hooks:
            data.pop("hooks", None)
    return data


def merge_default_config(config_path: Path) -> None:
    current = load_json(config_path, {})
    if not isinstance(current, dict):
        current = {}
    merged = merge_missing_defaults(current, DEFAULT_CONFIG)
    if not config_path.exists() or merged != current:
        save_json(config_path, merged)


def remove_path_if_empty(path: Path) -> None:
    if not path.exists() or not path.is_dir():
        return
    try:
        next(path.iterdir())
    except StopIteration:
        path.rmdir()


def split_command(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def command_has_flag(parts: list[str], flag: str, value: str) -> bool:
    for index, part in enumerate(parts[:-1]):
        if part == flag and parts[index + 1] == value:
            return True
    return False


def is_agent_notify_command(command: Any, client: str, runtime_path: Path) -> bool:
    if not isinstance(command, str):
        return False
    if command == command_for(runtime_path, client):
        return True

    parts = split_command(command)
    if not parts or Path(parts[0]).name != "notify.py":
        return False

    if not command_has_flag(parts, "--client", client):
        return False

    if command_has_flag(parts, "--source", AGENT_NOTIFY_SOURCE):
        return True

    if ".agent-notify/" in command:
        return True

    return False


def claude_hook_contains_agent_notify(entry: Any, client: str, runtime_path: Path) -> bool:
    if not isinstance(entry, dict):
        return False
    hooks = entry.get("hooks")
    if not isinstance(hooks, list):
        return False
    return any(
        isinstance(hook, dict) and is_agent_notify_command(hook.get("command"), client, runtime_path)
        for hook in hooks
    )


def is_claude_installed(settings_path: Path, runtime_path: Path) -> bool:
    data = load_json(settings_path, {})
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return False
    for event_name in ["Notification", "Stop"]:
        entries = hooks.get(event_name)
        if not isinstance(entries, list):
            continue
        if any(claude_hook_contains_agent_notify(entry, "claude", runtime_path) for entry in entries):
            return True
    return False


def is_cursor_installed(hooks_path: Path, runtime_path: Path) -> bool:
    data = load_json(hooks_path, {})
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return False
    for event_name in ["afterAgentResponse", "stop"]:
        entries = hooks.get(event_name)
        if not isinstance(entries, list):
            continue
        if any(
            isinstance(entry, dict) and is_agent_notify_command(entry.get("command"), "cursor", runtime_path)
            for entry in entries
        ):
            return True
    return False


def is_opencode_installed(plugin_path: Path) -> bool:
    if not plugin_path.exists():
        return False
    return "agent-notify opencode plugin" in plugin_path.read_text(encoding="utf-8")


def get_installed_clients(
    runtime_path: Path,
    claude_settings: Path,
    cursor_hooks: Path,
    opencode_plugin: Path,
) -> list[str]:
    installed: list[str] = []
    if is_claude_installed(claude_settings, runtime_path):
        installed.append("claude")
    if is_cursor_installed(cursor_hooks, runtime_path):
        installed.append("cursor")
    if is_opencode_installed(opencode_plugin):
        installed.append("opencode")
    return installed


def get_interactive_default_clients(
    runtime_path: Path,
    claude_settings: Path,
    cursor_hooks: Path,
    opencode_plugin: Path,
) -> list[str]:
    if not runtime_path.is_file():
        return []

    defaults: list[str] = []
    if claude_settings.exists() and is_claude_installed(claude_settings, runtime_path):
        defaults.append("claude")
    if cursor_hooks.exists() and is_cursor_installed(cursor_hooks, runtime_path):
        defaults.append("cursor")
    if opencode_plugin.exists() and is_opencode_installed(opencode_plugin):
        defaults.append("opencode")
    return defaults


def install_claude(runtime_path: Path, settings_path: Path) -> None:
    command = command_for(runtime_path, "claude")
    data = load_json(settings_path, {})
    hooks = data.setdefault("hooks", {})
    notification_entries = hooks.setdefault("Notification", [])
    stop_entries = hooks.setdefault("Stop", [])

    for matcher in ["permission_prompt", "idle_prompt", "elicitation_dialog"]:
        if not any(
            isinstance(entry, dict)
            and entry.get("matcher") == matcher
            and any(
                isinstance(hook, dict) and hook.get("command") == command
                for hook in entry.get("hooks", [])
            )
            for entry in notification_entries
        ):
            notification_entries.append(
                {
                    "matcher": matcher,
                    "hooks": [{"type": "command", "command": command}],
                }
            )

    if not any(
        isinstance(entry, dict)
        and any(
            isinstance(hook, dict) and hook.get("command") == command
            for hook in entry.get("hooks", [])
        )
        for entry in stop_entries
    ):
        stop_entries.append({"hooks": [{"type": "command", "command": command}]})

    save_json(settings_path, data)


def uninstall_claude(runtime_path: Path, settings_path: Path) -> bool:
    data = load_json(settings_path, {})
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return False

    changed = False
    for event_name in ["Notification", "Stop"]:
        entries = hooks.get(event_name)
        if not isinstance(entries, list):
            continue
        updated_entries: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                updated_entries.append(entry)
                continue
            hook_list = entry.get("hooks")
            if not isinstance(hook_list, list):
                updated_entries.append(entry)
                continue
            filtered_hooks = [
                hook
                for hook in hook_list
                if not (
                    isinstance(hook, dict)
                    and is_agent_notify_command(hook.get("command"), "claude", runtime_path)
                )
            ]
            if len(filtered_hooks) != len(hook_list):
                changed = True
            if filtered_hooks:
                entry["hooks"] = filtered_hooks
                updated_entries.append(entry)
        hooks[event_name] = remove_empty_hook_entries(updated_entries)

    if not changed:
        return False

    cleaned = prune_empty_objects(data)
    if not cleaned:
        settings_path.unlink(missing_ok=True)
        return True

    save_json(settings_path, cleaned)
    return True


def install_cursor(runtime_path: Path, hooks_path: Path) -> None:
    command = command_for(runtime_path, "cursor")
    data = load_json(hooks_path, {})
    hooks = data.setdefault("hooks", {})
    data["version"] = 1

    for event_name in ["afterAgentResponse", "stop"]:
        entries = hooks.setdefault(event_name, [])
        if not any(isinstance(entry, dict) and entry.get("command") == command for entry in entries):
            entries.append({"command": command})

    save_json(hooks_path, data)


def uninstall_cursor(runtime_path: Path, hooks_path: Path) -> bool:
    data = load_json(hooks_path, {})
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return False

    changed = False
    for event_name in ["afterAgentResponse", "stop"]:
        entries = hooks.get(event_name)
        if not isinstance(entries, list):
            continue
        filtered = [
            entry
            for entry in entries
            if not (
                isinstance(entry, dict)
                and is_agent_notify_command(entry.get("command"), "cursor", runtime_path)
            )
        ]
        if len(filtered) != len(entries):
            changed = True
        hooks[event_name] = filtered

    if not changed:
        return False

    cleaned = prune_empty_objects(data)
    if cleaned in ({}, {"version": 1}):
        hooks_path.unlink(missing_ok=True)
        return True

    save_json(hooks_path, cleaned)
    return True


def render_opencode_template(template_path: Path, runtime_path: Path) -> str:
    template = template_path.read_text(encoding="utf-8")
    return template.replace("__AGENT_NOTIFY_RUNTIME__", str(runtime_path))


def install_opencode(runtime_path: Path, plugin_path: Path, template_path: Path) -> None:
    plugin_path.parent.mkdir(parents=True, exist_ok=True)
    plugin_path.write_text(render_opencode_template(template_path, runtime_path), encoding="utf-8")


def uninstall_opencode(plugin_path: Path) -> bool:
    if not plugin_path.exists():
        return False
    text = plugin_path.read_text(encoding="utf-8")
    if "agent-notify opencode plugin" not in text:
        return False
    plugin_path.unlink()
    remove_path_if_empty(plugin_path.parent)
    return True


def copy_runtime(install_dir: Path) -> Path:
    bin_dir = install_dir / "bin"
    target_script = bin_dir / "notify.py"
    bin_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(RUNTIME_SOURCE, target_script)
    ensure_executable(target_script)
    merge_default_config(install_dir / "config.json")
    return target_script


def install_provider(
    client: str,
    runtime_path: Path,
    claude_settings: Path,
    cursor_hooks: Path,
    opencode_plugin: Path,
) -> str | None:
    if client == "claude":
        install_claude(runtime_path, claude_settings)
        return "installed"
    if client == "cursor":
        install_cursor(runtime_path, cursor_hooks)
        return "installed"
    if client == "opencode":
        install_opencode(runtime_path, opencode_plugin, OPENCODE_TEMPLATE)
        return "installed"
    return None


def uninstall_provider(
    client: str,
    runtime_path: Path,
    claude_settings: Path,
    cursor_hooks: Path,
    opencode_plugin: Path,
) -> str | None:
    if client == "claude":
        return "removed" if uninstall_claude(runtime_path, claude_settings) else None
    if client == "cursor":
        return "removed" if uninstall_cursor(runtime_path, cursor_hooks) else None
    if client == "opencode":
        return "removed" if uninstall_opencode(opencode_plugin) else None
    return None
