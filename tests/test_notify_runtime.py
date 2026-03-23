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
    def run_notify_process(
        self,
        *args: str,
        payload: dict[str, object] | None = None,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(NOTIFY_SCRIPT), "--dry-run", *args],
            cwd=cwd or REPO_ROOT,
            env=env,
            input=json.dumps(payload) if payload is not None else None,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def run_notify(
        self,
        client: str,
        payload: dict[str, object],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        via_arg: bool = False,
    ) -> dict[str, object]:
        args = ["--client", client]
        process_payload = payload
        if via_arg:
            args.append(json.dumps(payload))
            process_payload = None
        result = self.run_notify_process(
            *args,
            payload=process_payload,
            cwd=cwd,
            env=env,
        )
        self.assertTrue(result.stdout.strip(), "expected dry-run JSON output")
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

    def test_codex_completion_notification_uses_complete_variant(self) -> None:
        output = self.run_notify(
            "codex",
            {
                "type": "agent-turn-complete",
                "cwd": "/tmp/agent-notify",
            },
            via_arg=True,
        )

        self.assertEqual(output["notification"]["kind"], "complete")
        self.assertEqual(output["notification"]["title"], "Codex")
        self.assertEqual(output["notification"]["subtitle"], "agent-notify · 执行完成")

    def test_codex_transcript_exec_approval_maps_to_permission(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            transcript_path = Path(tmpdir) / "session.jsonl"
            transcript_path.write_text(
                json.dumps({"type": "event_msg", "payload": {"type": "exec_approval_request"}}) + "\n",
                encoding="utf-8",
            )

            output = self.run_notify(
                "codex",
                {
                    "hook_event_name": "Stop",
                    "cwd": "/tmp/agent-notify",
                    "transcript_path": str(transcript_path),
                    "turn_id": "turn-1",
                },
            )

        self.assertEqual(output["notification"]["kind"], "permission")
        self.assertEqual(output["notification"]["title"], "Codex")
        self.assertEqual(output["notification"]["subtitle"], "agent-notify · 等待授权")

    def test_codex_transcript_elicitation_maps_to_question(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            transcript_path = Path(tmpdir) / "session.jsonl"
            transcript_path.write_text(
                json.dumps({"type": "event_msg", "payload": {"type": "elicitation_request"}}) + "\n",
                encoding="utf-8",
            )

            output = self.run_notify(
                "codex",
                {
                    "hook_event_name": "Stop",
                    "cwd": "/tmp/agent-notify",
                    "transcript_path": str(transcript_path),
                    "turn_id": "turn-2",
                },
            )

        self.assertEqual(output["notification"]["kind"], "question")
        self.assertEqual(output["notification"]["subtitle"], "agent-notify · 等待回答")

    def test_codex_transcript_request_user_input_maps_to_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            transcript_path = Path(tmpdir) / "session.jsonl"
            transcript_path.write_text(
                json.dumps({"type": "event_msg", "payload": {"type": "request_user_input"}}) + "\n",
                encoding="utf-8",
            )

            output = self.run_notify(
                "codex",
                {
                    "hook_event_name": "Stop",
                    "cwd": "/tmp/agent-notify",
                    "transcript_path": str(transcript_path),
                    "turn_id": "turn-3",
                },
            )

        self.assertEqual(output["notification"]["kind"], "input")
        self.assertEqual(output["notification"]["subtitle"], "agent-notify · 需要补充信息")

    def test_codex_transcript_stream_error_maps_to_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            transcript_path = Path(tmpdir) / "session.jsonl"
            transcript_path.write_text(
                json.dumps({"type": "event_msg", "payload": {"type": "stream_error"}}) + "\n",
                encoding="utf-8",
            )

            output = self.run_notify(
                "codex",
                {
                    "hook_event_name": "Stop",
                    "cwd": "/tmp/agent-notify",
                    "transcript_path": str(transcript_path),
                    "turn_id": "turn-4",
                },
            )

        self.assertEqual(output["notification"]["kind"], "error")
        self.assertEqual(output["notification"]["subtitle"], "agent-notify · 执行出错")

    def test_codex_missing_transcript_falls_back_safely(self) -> None:
        result = self.run_notify_process(
            "--client",
            "codex",
            payload={
                "hook_event_name": "Stop",
                "cwd": "/tmp/agent-notify",
                "transcript_path": "/tmp/does-not-exist.jsonl",
                "turn_id": "turn-5",
            },
        )

        self.assertEqual(result.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
