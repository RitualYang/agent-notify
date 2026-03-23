import json
import os
import pty
import select
import subprocess
import sys
import tempfile
import time
import tomllib
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install.py"
INSTALL_SH = REPO_ROOT / "install.sh"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import providers  # noqa: E402


class InstallCliTests(unittest.TestCase):
    def run_install(
        self,
        *args: str,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(INSTALL_SCRIPT), *args],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_install_sh_interactive(self, *args: str, user_input: bytes = b"q") -> tuple[int, str]:
        master_fd, slave_fd = pty.openpty()
        process = subprocess.Popen(
            [str(INSTALL_SH), *args],
            cwd=REPO_ROOT,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            text=False,
            close_fds=True,
        )
        os.close(slave_fd)

        output = b""
        sent_input = False
        deadline = time.time() + 5

        try:
            while time.time() < deadline:
                ready, _, _ = select.select([master_fd], [], [], 0.2)
                if ready:
                    try:
                        chunk = os.read(master_fd, 4096)
                    except OSError:
                        break
                    if not chunk:
                        break
                    output += chunk
                    if not sent_input and b"Select clients to enable notifications for" in output:
                        try:
                            os.write(master_fd, user_input)
                            sent_input = True
                        except OSError:
                            break
                if process.poll() is not None and not ready:
                    break

            if not sent_input and process.poll() is None:
                try:
                    os.write(master_fd, user_input)
                except OSError:
                    pass

            process.wait(timeout=5)
        finally:
            os.close(master_fd)

        return process.returncode, output.decode("utf-8", errors="replace")

    def write_claude_settings(self, settings_path: Path, runtime_path: Path) -> None:
        command = providers.command_for(runtime_path, "claude")
        payload = {
            "hooks": {
                "Notification": [
                    {
                        "matcher": "permission_prompt",
                        "hooks": [{"type": "command", "command": command}],
                    }
                ],
                "Stop": [{"hooks": [{"type": "command", "command": command}]}],
            }
        }
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps(payload), encoding="utf-8")

    def run_install_sh(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(INSTALL_SH), *args],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def make_fake_codex_env(self, temp_root: Path, version: str) -> dict[str, str]:
        bin_dir = temp_root / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        codex_bin = bin_dir / "codex"
        codex_bin.write_text(
            "#!/usr/bin/env bash\n"
            'if [ "$1" = "--version" ]; then\n'
            f'  printf "codex-cli {version}\\n"\n'
            "  exit 0\n"
            "fi\n"
            'printf "unexpected codex invocation: %s\\n" "$*" >&2\n'
            "exit 1\n",
            encoding="utf-8",
        )
        codex_bin.chmod(0o755)
        return {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
        }

    def codex_args(self, temp_root: Path) -> tuple[str, str, str, str]:
        codex_dir = temp_root / ".codex"
        return (
            "--codex-config",
            str(codex_dir / "config.toml"),
            "--codex-hooks",
            str(codex_dir / "hooks.json"),
        )

    def test_print_interactive_defaults_ignores_stale_claude_hook_without_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            install_dir = temp_root / ".agent-notify"
            claude_settings = temp_root / ".claude" / "settings.json"
            cursor_hooks = temp_root / ".cursor" / "hooks.json"
            opencode_plugin = temp_root / ".config" / "opencode" / "plugins" / "agent-notify.js"

            self.write_claude_settings(claude_settings, install_dir / "bin" / "notify.py")

            result = self.run_install(
                "--print-interactive-defaults",
                "--install-dir",
                str(install_dir),
                "--claude-settings",
                str(claude_settings),
                "--cursor-hooks",
                str(cursor_hooks),
                "--opencode-plugin",
                str(opencode_plugin),
                *self.codex_args(temp_root),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "")

    def test_print_interactive_defaults_returns_claude_when_runtime_and_hook_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            install_dir = temp_root / ".agent-notify"
            runtime_path = install_dir / "bin" / "notify.py"
            claude_settings = temp_root / ".claude" / "settings.json"
            cursor_hooks = temp_root / ".cursor" / "hooks.json"
            opencode_plugin = temp_root / ".config" / "opencode" / "plugins" / "agent-notify.js"

            runtime_path.parent.mkdir(parents=True, exist_ok=True)
            runtime_path.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            self.write_claude_settings(claude_settings, runtime_path)

            result = self.run_install(
                "--print-interactive-defaults",
                "--install-dir",
                str(install_dir),
                "--claude-settings",
                str(claude_settings),
                "--cursor-hooks",
                str(cursor_hooks),
                "--opencode-plugin",
                str(opencode_plugin),
                *self.codex_args(temp_root),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip().splitlines(), ["claude"])

    def test_install_sh_shows_unchecked_menu_when_preflight_finds_no_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            returncode, output = self.run_install_sh_interactive(
                "--install-dir",
                str(temp_root / ".agent-notify"),
                "--claude-settings",
                str(temp_root / ".claude" / "settings.json"),
                "--cursor-hooks",
                str(temp_root / ".cursor" / "hooks.json"),
                "--opencode-plugin",
                str(temp_root / ".config" / "opencode" / "plugins" / "agent-notify.js"),
                *self.codex_args(temp_root),
            )

            self.assertEqual(returncode, 1)
            self.assertIn("[ ] Claude Code", output)
            self.assertIn("[ ] Cursor", output)
            self.assertIn("[ ] OpenCode", output)
            self.assertIn("[ ] Codex", output)
            self.assertNotIn("unbound variable", output)

    def test_update_installed_refreshes_existing_client(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            install_dir = temp_root / ".agent-notify"
            runtime_path = install_dir / "bin" / "notify.py"
            runtime_path.parent.mkdir(parents=True, exist_ok=True)
            runtime_path.write_text("# old runtime\n", encoding="utf-8")
            claude_settings = temp_root / ".claude" / "settings.json"
            cursor_hooks = temp_root / ".cursor" / "hooks.json"
            opencode_plugin = temp_root / ".config" / "opencode" / "plugins" / "agent-notify.js"
            self.write_claude_settings(claude_settings, runtime_path)

            result = self.run_install(
                "--update-installed",
                "--install-dir",
                str(install_dir),
                "--claude-settings",
                str(claude_settings),
                "--cursor-hooks",
                str(cursor_hooks),
                "--opencode-plugin",
                str(opencode_plugin),
                *self.codex_args(temp_root),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Enabled clients: claude", result.stdout)
            self.assertEqual(
                runtime_path.read_text(encoding="utf-8"),
                (REPO_ROOT / "hooks" / "notify.py").read_text(encoding="utf-8"),
            )

    def test_update_installed_requires_existing_installation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            result = self.run_install(
                "--update-installed",
                "--install-dir",
                str(temp_root / ".agent-notify"),
                "--claude-settings",
                str(temp_root / ".claude" / "settings.json"),
                "--cursor-hooks",
                str(temp_root / ".cursor" / "hooks.json"),
                "--opencode-plugin",
                str(temp_root / ".config" / "opencode" / "plugins" / "agent-notify.js"),
                *self.codex_args(temp_root),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("No installed clients found", result.stderr)

    def test_update_installed_merges_new_config_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            install_dir = temp_root / ".agent-notify"
            runtime_path = install_dir / "bin" / "notify.py"
            runtime_path.parent.mkdir(parents=True, exist_ok=True)
            runtime_path.write_text("# old runtime\n", encoding="utf-8")
            config_path = install_dir / "config.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                json.dumps(
                    {
                        "cursor": {
                            "question_message": "Keep my custom prompt",
                        }
                    }
                ),
                encoding="utf-8",
            )
            claude_settings = temp_root / ".claude" / "settings.json"
            cursor_hooks = temp_root / ".cursor" / "hooks.json"
            opencode_plugin = temp_root / ".config" / "opencode" / "plugins" / "agent-notify.js"
            self.write_claude_settings(claude_settings, runtime_path)

            result = self.run_install(
                "--update-installed",
                "--install-dir",
                str(install_dir),
                "--claude-settings",
                str(claude_settings),
                "--cursor-hooks",
                str(cursor_hooks),
                "--opencode-plugin",
                str(opencode_plugin),
                *self.codex_args(temp_root),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(config["cursor"]["question_message"], "Keep my custom prompt")
            self.assertEqual(config["notification_variants"]["question"]["subtitle"], "等待回答")

    def test_install_sh_update_refreshes_existing_client(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            install_dir = temp_root / ".agent-notify"
            runtime_path = install_dir / "bin" / "notify.py"
            runtime_path.parent.mkdir(parents=True, exist_ok=True)
            runtime_path.write_text("# old runtime\n", encoding="utf-8")
            claude_settings = temp_root / ".claude" / "settings.json"
            cursor_hooks = temp_root / ".cursor" / "hooks.json"
            opencode_plugin = temp_root / ".config" / "opencode" / "plugins" / "agent-notify.js"
            self.write_claude_settings(claude_settings, runtime_path)

            result = self.run_install_sh(
                "update",
                "--install-dir",
                str(install_dir),
                "--claude-settings",
                str(claude_settings),
                "--cursor-hooks",
                str(cursor_hooks),
                "--opencode-plugin",
                str(opencode_plugin),
                *self.codex_args(temp_root),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Enabled clients: claude", result.stdout)

    def test_install_codex_writes_stable_notify_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            install_dir = temp_root / ".agent-notify"
            codex_config = temp_root / ".codex" / "config.toml"
            codex_hooks = temp_root / ".codex" / "hooks.json"
            codex_config.parent.mkdir(parents=True, exist_ok=True)
            codex_config.write_text('model = "gpt-5.4"\n', encoding="utf-8")

            result = self.run_install(
                "--client",
                "codex",
                "--install-dir",
                str(install_dir),
                "--claude-settings",
                str(temp_root / ".claude" / "settings.json"),
                "--cursor-hooks",
                str(temp_root / ".cursor" / "hooks.json"),
                "--opencode-plugin",
                str(temp_root / ".config" / "opencode" / "plugins" / "agent-notify.js"),
                "--codex-config",
                str(codex_config),
                "--codex-hooks",
                str(codex_hooks),
                env=self.make_fake_codex_env(temp_root, "0.116.0"),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            config_text = codex_config.read_text(encoding="utf-8")
            self.assertIn('model = "gpt-5.4"', config_text)
            self.assertIn("notify = [", config_text)
            self.assertIn('"codex"', config_text)
            self.assertIn('"agent-notify"', config_text)

    def test_install_codex_unsupported_version_skips_experimental_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            install_dir = temp_root / ".agent-notify"
            codex_config = temp_root / ".codex" / "config.toml"
            codex_hooks = temp_root / ".codex" / "hooks.json"
            codex_config.parent.mkdir(parents=True, exist_ok=True)

            result = self.run_install(
                "--client",
                "codex",
                "--install-dir",
                str(install_dir),
                "--claude-settings",
                str(temp_root / ".claude" / "settings.json"),
                "--cursor-hooks",
                str(temp_root / ".cursor" / "hooks.json"),
                "--opencode-plugin",
                str(temp_root / ".config" / "opencode" / "plugins" / "agent-notify.js"),
                "--codex-config",
                str(codex_config),
                "--codex-hooks",
                str(codex_hooks),
                env=self.make_fake_codex_env(temp_root, "0.117.0"),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("completion-only", result.stdout + result.stderr)
            self.assertFalse(codex_hooks.exists())
            self.assertNotIn("codex_hooks = true", codex_config.read_text(encoding="utf-8"))

    def test_uninstall_codex_preserves_foreign_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            install_dir = temp_root / ".agent-notify"
            codex_config = temp_root / ".codex" / "config.toml"
            codex_hooks = temp_root / ".codex" / "hooks.json"

            install_result = self.run_install(
                "--client",
                "codex",
                "--install-dir",
                str(install_dir),
                "--claude-settings",
                str(temp_root / ".claude" / "settings.json"),
                "--cursor-hooks",
                str(temp_root / ".cursor" / "hooks.json"),
                "--opencode-plugin",
                str(temp_root / ".config" / "opencode" / "plugins" / "agent-notify.js"),
                "--codex-config",
                str(codex_config),
                "--codex-hooks",
                str(codex_hooks),
                env=self.make_fake_codex_env(temp_root, "0.116.0"),
            )
            self.assertEqual(install_result.returncode, 0, install_result.stderr)

            codex_config.write_text(
                codex_config.read_text(encoding="utf-8")
                + '\n[projects."/tmp/demo"]\ntrust_level = "trusted"\n',
                encoding="utf-8",
            )

            foreign_command = "echo foreign-stop-hook"
            hooks_payload = json.loads(codex_hooks.read_text(encoding="utf-8"))
            hooks_payload.setdefault("hooks", {}).setdefault("Stop", []).append(
                {"hooks": [{"type": "command", "command": foreign_command}]}
            )
            codex_hooks.write_text(json.dumps(hooks_payload), encoding="utf-8")

            uninstall_result = self.run_install(
                "--client",
                "none",
                "--install-dir",
                str(install_dir),
                "--claude-settings",
                str(temp_root / ".claude" / "settings.json"),
                "--cursor-hooks",
                str(temp_root / ".cursor" / "hooks.json"),
                "--opencode-plugin",
                str(temp_root / ".config" / "opencode" / "plugins" / "agent-notify.js"),
                "--codex-config",
                str(codex_config),
                "--codex-hooks",
                str(codex_hooks),
            )

            self.assertEqual(uninstall_result.returncode, 0, uninstall_result.stderr)
            self.assertIn('trust_level = "trusted"', codex_config.read_text(encoding="utf-8"))
            cleaned_hooks = json.loads(codex_hooks.read_text(encoding="utf-8"))
            self.assertEqual(
                cleaned_hooks["hooks"]["Stop"],
                [{"hooks": [{"type": "command", "command": foreign_command}]}],
            )

    def test_print_installed_includes_codex_when_config_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            install_dir = temp_root / ".agent-notify"
            codex_config = temp_root / ".codex" / "config.toml"
            codex_hooks = temp_root / ".codex" / "hooks.json"

            install_result = self.run_install(
                "--client",
                "codex",
                "--install-dir",
                str(install_dir),
                "--claude-settings",
                str(temp_root / ".claude" / "settings.json"),
                "--cursor-hooks",
                str(temp_root / ".cursor" / "hooks.json"),
                "--opencode-plugin",
                str(temp_root / ".config" / "opencode" / "plugins" / "agent-notify.js"),
                "--codex-config",
                str(codex_config),
                "--codex-hooks",
                str(codex_hooks),
                env=self.make_fake_codex_env(temp_root, "0.116.0"),
            )
            self.assertEqual(install_result.returncode, 0, install_result.stderr)

            result = self.run_install(
                "--print-installed",
                "--install-dir",
                str(install_dir),
                "--claude-settings",
                str(temp_root / ".claude" / "settings.json"),
                "--cursor-hooks",
                str(temp_root / ".cursor" / "hooks.json"),
                "--opencode-plugin",
                str(temp_root / ".config" / "opencode" / "plugins" / "agent-notify.js"),
                "--codex-config",
                str(codex_config),
                "--codex-hooks",
                str(codex_hooks),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("codex", result.stdout.strip().splitlines())


if __name__ == "__main__":
    unittest.main()
