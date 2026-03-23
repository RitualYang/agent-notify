#!/usr/bin/env python3

from __future__ import annotations

from copy import deepcopy
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SUPPORTED_CLIENTS = ("claude", "cursor", "opencode", "codex")
KNOWN_CLIENTS = SUPPORTED_CLIENTS
CLIENT_ALIASES = {
    "all": SUPPORTED_CLIENTS,
    "both": ("claude", "cursor"),
    "none": (),
    "clear": (),
}
AGENT_NOTIFY_SOURCE = "agent-notify"
CODEX_EXPERIMENTAL_MIN_VERSION = (0, 114, 0)
CODEX_EXPERIMENTAL_MAX_VERSION = (0, 116, 999)
CODEX_MANAGED_TABLE = "agent_notify"
CODEX_MANAGED_CLIENT_KEY = "codex"


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    supported: bool
    note: str | None = None


@dataclass(frozen=True)
class ProviderActionResult:
    action: str | None = None
    notes: tuple[str, ...] = ()


DEFAULT_RUNTIME_DIR = Path(os.path.expanduser("~/.agent-notify")).resolve()
DEFAULT_CLAUDE_SETTINGS = Path(os.path.expanduser("~/.claude/settings.json"))
DEFAULT_CURSOR_HOOKS = Path(os.path.expanduser("~/.cursor/hooks.json"))
DEFAULT_OPENCODE_PLUGIN = Path(os.path.expanduser("~/.config/opencode/plugins/agent-notify.js"))
DEFAULT_CODEX_CONFIG = Path(os.path.expanduser("~/.codex/config.toml"))
DEFAULT_CODEX_HOOKS = Path(os.path.expanduser("~/.codex/hooks.json"))

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
    "codex": {
        "notify_on_stop": True,
        "stop_title": "Codex",
        "stop_message": "任务已完成，等待你查看结果。",
        "notification_title": "Codex",
    },
}


PROVIDERS: dict[str, ProviderSpec] = {
    "claude": ProviderSpec(name="claude", supported=True),
    "cursor": ProviderSpec(name="cursor", supported=True),
    "opencode": ProviderSpec(name="opencode", supported=True),
    "codex": ProviderSpec(
        name="codex",
        supported=True,
        note="Codex 完成提醒为稳定支持；更丰富的通知分类依赖实验性 hooks，仅在 0.114.x-0.116.x 启用。",
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


def load_toml(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return default


def toml_key(key: str) -> str:
    if re.match(r"^[A-Za-z0-9_-]+$", key):
        return key
    return json.dumps(key, ensure_ascii=False)


def toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    raise TypeError(f"Unsupported TOML value: {value!r}")


def dump_toml(data: dict[str, Any]) -> str:
    lines: list[str] = []

    def emit_table(table: dict[str, Any], path: list[str]) -> None:
        scalar_items: list[tuple[str, Any]] = []
        table_items: list[tuple[str, dict[str, Any]]] = []
        for key, value in table.items():
            if isinstance(value, dict):
                table_items.append((key, value))
            else:
                scalar_items.append((key, value))

        if path:
            if lines:
                lines.append("")
            lines.append("[" + ".".join(toml_key(part) for part in path) + "]")

        for key, value in scalar_items:
            lines.append(f"{toml_key(key)} = {toml_value(value)}")

        for key, value in table_items:
            emit_table(value, [*path, key])

    emit_table(data, [])
    return "\n".join(lines) + "\n"


def save_toml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_toml(payload), encoding="utf-8")


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


def argv_for(script_path: Path, client: str) -> list[str]:
    return [str(script_path), "--client", client, "--source", AGENT_NOTIFY_SOURCE]


def command_for(script_path: Path, client: str) -> str:
    return " ".join(shlex.quote(part) for part in argv_for(script_path, client))


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


def is_agent_notify_argv(command: Any, client: str, runtime_path: Path) -> bool:
    if isinstance(command, list):
        parts = [str(item) for item in command]
    elif isinstance(command, str):
        parts = split_command(command)
    else:
        return False

    if not parts:
        return False

    if parts == argv_for(runtime_path, client):
        return True

    if Path(parts[0]).name != "notify.py":
        return False

    if not command_has_flag(parts, "--client", client):
        return False

    if command_has_flag(parts, "--source", AGENT_NOTIFY_SOURCE):
        return True

    return ".agent-notify/" in " ".join(parts)


def codex_notify_argv(runtime_path: Path) -> list[str]:
    return argv_for(runtime_path, "codex")


def parse_codex_version(raw: str) -> tuple[int, int, int] | None:
    match = re.search(r"codex-cli\s+(\d+)\.(\d+)\.(\d+)", raw)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def detect_codex_version() -> tuple[int, int, int] | None:
    try:
        result = subprocess.run(
            ["codex", "--version"],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None

    if result.returncode != 0:
        return None

    return parse_codex_version(result.stdout + "\n" + result.stderr)


def codex_supports_experimental_hooks(version: tuple[int, int, int] | None) -> bool:
    if version is None:
        return False
    return CODEX_EXPERIMENTAL_MIN_VERSION <= version <= CODEX_EXPERIMENTAL_MAX_VERSION


def codex_managed_state(config: dict[str, Any]) -> dict[str, Any]:
    managed = config.setdefault(CODEX_MANAGED_TABLE, {})
    if not isinstance(managed, dict):
        managed = {}
        config[CODEX_MANAGED_TABLE] = managed
    client_state = managed.setdefault(CODEX_MANAGED_CLIENT_KEY, {})
    if not isinstance(client_state, dict):
        client_state = {}
        managed[CODEX_MANAGED_CLIENT_KEY] = client_state
    return client_state


def prune_empty_dicts(data: dict[str, Any]) -> dict[str, Any]:
    for key, value in list(data.items()):
        if isinstance(value, dict):
            cleaned = prune_empty_dicts(value)
            if cleaned:
                data[key] = cleaned
            else:
                data.pop(key, None)
        elif value in ({}, [], None):
            data.pop(key, None)
    return data


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


def codex_hook_contains_agent_notify(entry: Any, runtime_path: Path) -> bool:
    if not isinstance(entry, dict):
        return False
    hooks = entry.get("hooks")
    if not isinstance(hooks, list):
        return False
    return any(
        isinstance(hook, dict) and is_agent_notify_command(hook.get("command"), "codex", runtime_path)
        for hook in hooks
    )


def is_codex_installed(config_path: Path, hooks_path: Path, runtime_path: Path) -> bool:
    config = load_toml(config_path, {})
    if isinstance(config, dict) and is_agent_notify_argv(config.get("notify"), "codex", runtime_path):
        return True

    data = load_json(hooks_path, {})
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return False
    entries = hooks.get("Stop")
    if not isinstance(entries, list):
        return False
    return any(codex_hook_contains_agent_notify(entry, runtime_path) for entry in entries)


def get_installed_clients(
    runtime_path: Path,
    claude_settings: Path,
    cursor_hooks: Path,
    opencode_plugin: Path,
    codex_config: Path,
    codex_hooks: Path,
) -> list[str]:
    installed: list[str] = []
    if is_claude_installed(claude_settings, runtime_path):
        installed.append("claude")
    if is_cursor_installed(cursor_hooks, runtime_path):
        installed.append("cursor")
    if is_opencode_installed(opencode_plugin):
        installed.append("opencode")
    if is_codex_installed(codex_config, codex_hooks, runtime_path):
        installed.append("codex")
    return installed


def get_interactive_default_clients(
    runtime_path: Path,
    claude_settings: Path,
    cursor_hooks: Path,
    opencode_plugin: Path,
    codex_config: Path,
    codex_hooks: Path,
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
    if codex_config.exists() and is_codex_installed(codex_config, codex_hooks, runtime_path):
        defaults.append("codex")
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


def install_codex(runtime_path: Path, config_path: Path, hooks_path: Path) -> ProviderActionResult:
    notes: list[str] = []
    config = load_toml(config_path, {})
    if not isinstance(config, dict):
        config = {}

    notify_installed = False
    notify_value = config.get("notify")
    if notify_value is None or is_agent_notify_argv(notify_value, "codex", runtime_path):
        config["notify"] = codex_notify_argv(runtime_path)
        notify_installed = True
    else:
        notes.append("codex: existing notify config preserved; skipped replacing non-agent-notify callback")

    managed = codex_managed_state(config)
    managed["managed_notify"] = notify_installed

    version = detect_codex_version()
    hooks_installed = False
    if codex_supports_experimental_hooks(version):
        features = config.setdefault("features", {})
        if not isinstance(features, dict):
            features = {}
            config["features"] = features

        if "codex_hooks" not in features or managed.get("managed_codex_hooks_feature"):
            features["codex_hooks"] = True
            managed["managed_codex_hooks_feature"] = True

            command = command_for(runtime_path, "codex")
            data = load_json(hooks_path, {})
            hooks = data.setdefault("hooks", {})
            stop_entries = hooks.setdefault("Stop", [])
            if not any(codex_hook_contains_agent_notify(entry, runtime_path) for entry in stop_entries):
                stop_entries.append({"hooks": [{"type": "command", "command": command}]})
            save_json(hooks_path, data)
            hooks_installed = True
        else:
            notes.append("codex: existing codex_hooks feature preserved; skipped experimental hook installation")
    else:
        version_text = ".".join(str(part) for part in version) if version else "unknown"
        notes.append(
            f"codex: installed completion-only notifications; experimental hooks require Codex CLI 0.114.x-0.116.x (detected {version_text})"
        )
        managed.pop("managed_codex_hooks_feature", None)

    if not hooks_installed:
        uninstall_codex_hooks_only(runtime_path, hooks_path)

    save_toml(config_path, prune_empty_dicts(config))
    return ProviderActionResult(action="installed", notes=tuple(notes))


def uninstall_codex_hooks_only(runtime_path: Path, hooks_path: Path) -> bool:
    data = load_json(hooks_path, {})
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return False

    entries = hooks.get("Stop")
    if not isinstance(entries, list):
        return False

    filtered: list[dict[str, Any]] = []
    changed = False
    for entry in entries:
        if codex_hook_contains_agent_notify(entry, runtime_path):
            changed = True
            continue
        filtered.append(entry)

    if not changed:
        return False

    hooks["Stop"] = filtered
    cleaned = prune_empty_objects(data)
    if cleaned == {}:
        hooks_path.unlink(missing_ok=True)
        return True

    save_json(hooks_path, cleaned)
    return True


def uninstall_codex(runtime_path: Path, config_path: Path, hooks_path: Path) -> bool:
    config = load_toml(config_path, {})
    if not isinstance(config, dict):
        config = {}

    changed = uninstall_codex_hooks_only(runtime_path, hooks_path)

    managed = config.get(CODEX_MANAGED_TABLE, {})
    codex_state = managed.get(CODEX_MANAGED_CLIENT_KEY, {}) if isinstance(managed, dict) else {}
    if not isinstance(codex_state, dict):
        codex_state = {}

    if codex_state.get("managed_notify") and is_agent_notify_argv(config.get("notify"), "codex", runtime_path):
        config.pop("notify", None)
        changed = True

    features = config.get("features")
    if (
        isinstance(features, dict)
        and codex_state.get("managed_codex_hooks_feature")
        and features.get("codex_hooks") is True
    ):
        features.pop("codex_hooks", None)
        changed = True

    codex_state.pop("managed_notify", None)
    codex_state.pop("managed_codex_hooks_feature", None)
    cleaned = prune_empty_dicts(config)

    if not changed:
        return False

    if cleaned:
        save_toml(config_path, cleaned)
    else:
        config_path.unlink(missing_ok=True)
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
    codex_config: Path,
    codex_hooks: Path,
) -> ProviderActionResult:
    if client == "claude":
        install_claude(runtime_path, claude_settings)
        return ProviderActionResult(action="installed")
    if client == "cursor":
        install_cursor(runtime_path, cursor_hooks)
        return ProviderActionResult(action="installed")
    if client == "opencode":
        install_opencode(runtime_path, opencode_plugin, OPENCODE_TEMPLATE)
        return ProviderActionResult(action="installed")
    if client == "codex":
        return install_codex(runtime_path, codex_config, codex_hooks)
    return ProviderActionResult()


def uninstall_provider(
    client: str,
    runtime_path: Path,
    claude_settings: Path,
    cursor_hooks: Path,
    opencode_plugin: Path,
    codex_config: Path,
    codex_hooks: Path,
) -> ProviderActionResult:
    if client == "claude":
        return ProviderActionResult(action="removed") if uninstall_claude(runtime_path, claude_settings) else ProviderActionResult()
    if client == "cursor":
        return ProviderActionResult(action="removed") if uninstall_cursor(runtime_path, cursor_hooks) else ProviderActionResult()
    if client == "opencode":
        return ProviderActionResult(action="removed") if uninstall_opencode(opencode_plugin) else ProviderActionResult()
    if client == "codex":
        return ProviderActionResult(action="removed") if uninstall_codex(runtime_path, codex_config, codex_hooks) else ProviderActionResult()
    return ProviderActionResult()
