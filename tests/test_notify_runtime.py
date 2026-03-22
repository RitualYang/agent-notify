import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTIFY_SCRIPT = REPO_ROOT / "hooks" / "notify.py"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import providers  # noqa: E402


class NotifyRuntimeTests(unittest.TestCase):
    def run_notify(
        self,
        client: str,
        payload: dict[str, object],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> dict[str, object]:
        result = subprocess.run(
            [sys.executable, str(NOTIFY_SCRIPT), "--dry-run", "--client", client],
            cwd=cwd or REPO_ROOT,
            env=env,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_claude_stop_subtitle_includes_project_name_from_payload_cwd(self) -> None:
        output = self.run_notify(
            "claude",
            {
                "hook_event_name": "Stop",
                "cwd": "/tmp/agent-notify",
            },
        )

        self.assertEqual(output["notification"]["subtitle"], "agent-notify · 执行完成")

    def test_claude_stop_subtitle_includes_project_name_from_env_fallback(self) -> None:
        output = self.run_notify(
            "claude",
            {
                "hook_event_name": "Stop",
            },
            env={**os.environ, "CLAUDE_PROJECT_DIR": "/tmp/demo-project"},
        )

        self.assertEqual(output["notification"]["subtitle"], "demo-project · 执行完成")

    def test_cursor_stop_subtitle_includes_project_name_from_workspace_root(self) -> None:
        output = self.run_notify(
            "cursor",
            {
                "hook_event_name": "stop",
                "status": "completed",
                "conversation_id": "conv-1",
                "workspace_roots": ["/tmp/agent-notify"],
            },
        )

        self.assertEqual(output["notification"]["subtitle"], "agent-notify · 执行完成")

    def test_cursor_question_subtitle_falls_back_to_process_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "multi-project-demo"
            project_dir.mkdir()

            output = self.run_notify(
                "cursor",
                {
                    "hook_event_name": "afterAgentResponse",
                    "conversation_id": "conv-2",
                    "text": "Would you like me to update the API client as well?",
                },
                cwd=project_dir,
            )

        self.assertEqual(output["notification"]["kind"], "question")
        self.assertEqual(output["notification"]["subtitle"], "multi-project-demo · 等待回答")

    def test_claude_permission_notification_uses_permission_variant(self) -> None:
        output = self.run_notify(
            "claude",
            {
                "hook_event_name": "Notification",
                "notification_type": "permission_prompt",
                "cwd": "/tmp/agent-notify",
            },
        )

        self.assertEqual(output["notification"]["kind"], "permission")
        self.assertEqual(output["notification"]["subtitle"], "agent-notify · 等待授权")

    def test_claude_elicitation_uses_question_variant(self) -> None:
        output = self.run_notify(
            "claude",
            {
                "hook_event_name": "Elicitation",
                "cwd": "/tmp/agent-notify",
            },
        )

        self.assertEqual(output["notification"]["kind"], "question")
        self.assertEqual(output["notification"]["subtitle"], "agent-notify · 等待回答")

    def test_opencode_error_uses_error_variant(self) -> None:
        output = self.run_notify(
            "opencode",
            {
                "type": "session.error",
                "project_context": {
                    "directory": "/tmp/agent-notify",
                },
            },
        )

        self.assertEqual(output["notification"]["kind"], "error")
        self.assertEqual(output["notification"]["subtitle"], "agent-notify · 执行出错")

    def test_opencode_idle_subtitle_includes_project_name_from_forwarded_directory(self) -> None:
        output = self.run_notify(
            "opencode",
            {
                "type": "session.idle",
                "project_context": {
                    "directory": "/tmp/agent-notify",
                    "worktree": "/tmp/agent-notify",
                },
            },
        )

        self.assertEqual(output["notification"]["subtitle"], "agent-notify · 执行完成")

    def test_rendered_opencode_template_forwards_project_context(self) -> None:
        rendered = providers.render_opencode_template(
            providers.OPENCODE_TEMPLATE,
            Path("/tmp/runtime-notify.py"),
        )

        self.assertIn("project_context", rendered)
        self.assertIn("directory", rendered)
        self.assertIn("worktree", rendered)


if __name__ == "__main__":
    unittest.main()
