#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from providers import (
    DEFAULT_CLAUDE_SETTINGS,
    DEFAULT_CODEX_CONFIG,
    DEFAULT_CODEX_HOOKS,
    DEFAULT_CURSOR_HOOKS,
    DEFAULT_OPENCODE_PLUGIN,
    DEFAULT_RUNTIME_DIR,
    KNOWN_CLIENTS,
    PROVIDERS,
    SUPPORTED_CLIENTS,
    copy_runtime,
    get_interactive_default_clients,
    get_installed_clients,
    install_provider,
    normalize_clients,
    uninstall_provider,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync macOS notifications for Claude Code, Cursor, OpenCode, and Codex. Selected clients are installed; unselected clients are removed."
    )
    parser.add_argument(
        "--client",
        action="append",
        choices=[*KNOWN_CLIENTS, "all", "both", "none", "clear"],
        help="Repeatable. The final selected set becomes the desired state.",
    )
    parser.add_argument("--install-dir", default=str(DEFAULT_RUNTIME_DIR))
    parser.add_argument("--claude-settings", default=str(DEFAULT_CLAUDE_SETTINGS))
    parser.add_argument("--cursor-hooks", default=str(DEFAULT_CURSOR_HOOKS))
    parser.add_argument("--opencode-plugin", default=str(DEFAULT_OPENCODE_PLUGIN))
    parser.add_argument("--codex-config", default=str(DEFAULT_CODEX_CONFIG))
    parser.add_argument("--codex-hooks", default=str(DEFAULT_CODEX_HOOKS))
    parser.add_argument("--keep-runtime", action="store_true", help="Keep runtime files even when no client remains selected.")
    parser.add_argument("--print-installed", action="store_true", help="Print currently installed supported clients, one per line.")
    parser.add_argument(
        "--update-installed",
        action="store_true",
        help="Refresh runtime, config, hooks, and plugins for currently installed supported clients.",
    )
    parser.add_argument(
        "--print-interactive-defaults",
        action="store_true",
        help="Print clients that pass the interactive preflight check and should be preselected.",
    )
    args = parser.parse_args()

    install_dir = Path(args.install_dir).expanduser().resolve()
    claude_settings = Path(args.claude_settings).expanduser().resolve()
    cursor_hooks = Path(args.cursor_hooks).expanduser().resolve()
    opencode_plugin = Path(args.opencode_plugin).expanduser().resolve()
    codex_config = Path(args.codex_config).expanduser().resolve()
    codex_hooks = Path(args.codex_hooks).expanduser().resolve()
    runtime_path = install_dir / "bin" / "notify.py"

    installed_clients = get_installed_clients(
        runtime_path,
        claude_settings,
        cursor_hooks,
        opencode_plugin,
        codex_config,
        codex_hooks,
    )
    if args.print_installed:
        for client in installed_clients:
            print(client)
        return 0

    if args.print_interactive_defaults:
        for client in get_interactive_default_clients(
            runtime_path,
            claude_settings,
            cursor_hooks,
            opencode_plugin,
            codex_config,
            codex_hooks,
        ):
            print(client)
        return 0

    if args.update_installed and args.client:
        parser.error("--update-installed cannot be combined with --client")

    if args.update_installed:
        selected_clients = installed_clients
        if not selected_clients:
            print("No installed clients found. Run ./install.sh first to select clients.", file=sys.stderr)
            return 1
    else:
        selected_clients = normalize_clients(args.client, ("claude", "cursor"))
    selected_supported = [client for client in selected_clients if client in SUPPORTED_CLIENTS]

    enabled: list[str] = []
    removed: list[str] = []
    skipped: list[str] = []
    notes: list[str] = []

    for client in selected_clients:
        provider = PROVIDERS[client]
        if not provider.supported and client not in skipped:
            skipped.append(client)
            if provider.note:
                notes.append(f"{client}: {provider.note}")

    if selected_supported:
        runtime_path = copy_runtime(install_dir)

    for client in SUPPORTED_CLIENTS:
        if client in selected_supported:
            uninstall_provider(
                client,
                runtime_path,
                claude_settings,
                cursor_hooks,
                opencode_plugin,
                codex_config,
                codex_hooks,
            )
            install_result = install_provider(
                client,
                runtime_path,
                claude_settings,
                cursor_hooks,
                opencode_plugin,
                codex_config,
                codex_hooks,
            )
            if install_result.action == "installed":
                enabled.append(client)
            notes.extend(install_result.notes)
        else:
            uninstall_result = uninstall_provider(
                client,
                runtime_path,
                claude_settings,
                cursor_hooks,
                opencode_plugin,
                codex_config,
                codex_hooks,
            )
            if uninstall_result.action == "removed":
                removed.append(client)
            notes.extend(uninstall_result.notes)

    if not selected_supported and not args.keep_runtime and install_dir.exists():
        shutil.rmtree(install_dir, ignore_errors=True)
        notes.append(f"runtime removed: {install_dir}")

    print(f"Runtime dir: {install_dir}")
    print(f"Claude settings: {claude_settings}")
    print(f"Cursor hooks: {cursor_hooks}")
    print(f"OpenCode plugin: {opencode_plugin}")
    print(f"Codex config: {codex_config}")
    print(f"Codex hooks: {codex_hooks}")
    if enabled:
        print(f"Enabled clients: {', '.join(enabled)}")
    else:
        print("Enabled clients: (none)")
    if removed:
        print(f"Removed clients: {', '.join(removed)}")
    if skipped:
        print(f"Skipped clients: {', '.join(skipped)}")
    for note in notes:
        print(f"Note: {note}")
    print("Restart the corresponding apps to apply the updated hooks or plugins.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
