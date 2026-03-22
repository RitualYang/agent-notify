import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_RELEASE = REPO_ROOT / "scripts" / "build_release.py"
INSTALL_RELEASE = REPO_ROOT / "install-release.sh"


class ReleaseDistributionTests(unittest.TestCase):
    def run_build_release(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(BUILD_RELEASE), *args],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_install_release(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        return subprocess.run(
            [str(INSTALL_RELEASE), *args],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
            env=merged_env,
        )

    def test_build_release_creates_expected_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            result = self.run_build_release("--version", "v0.1.0", "--output-dir", str(output_dir))

            self.assertEqual(result.returncode, 0, result.stderr)
            archive_path = output_dir / "agent-notify-v0.1.0.tar.gz"
            self.assertTrue(archive_path.exists(), archive_path)

            with tarfile.open(archive_path, "r:gz") as archive:
                members = set(archive.getnames())

            self.assertIn("agent-notify-v0.1.0/install.sh", members)
            self.assertIn("agent-notify-v0.1.0/install-release.sh", members)
            self.assertIn("agent-notify-v0.1.0/scripts/install.py", members)
            self.assertIn("agent-notify-v0.1.0/scripts/providers.py", members)
            self.assertIn("agent-notify-v0.1.0/scripts/interactive-select.sh", members)
            self.assertIn("agent-notify-v0.1.0/hooks/notify.py", members)
            self.assertIn("agent-notify-v0.1.0/plugins/opencode/agent-notify.js.template", members)
            self.assertIn("agent-notify-v0.1.0/README.md", members)
            self.assertIn("agent-notify-v0.1.0/LICENSE", members)
            self.assertNotIn("agent-notify-v0.1.0/tests/test_release_distribution.py", members)

    def test_build_release_requires_exact_version_tag(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_build_release("--version", "0.1.0", "--output-dir", str(tmpdir))

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("vX.Y.Z", result.stderr)

    def test_install_release_downloads_exact_version_archive_and_runs_installer(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            release_root = temp_root / "releases" / "v0.1.0"
            package_root = temp_root / "package" / "agent-notify-v0.1.0"
            output_path = temp_root / "installer-args.txt"

            package_root.mkdir(parents=True)
            installer_path = package_root / "install.sh"
            installer_path.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "printf '%s\\n' \"$@\" > \"$AGENT_NOTIFY_TEST_OUTPUT\"\n",
                encoding="utf-8",
            )
            installer_path.chmod(0o755)

            archive_path = release_root / "agent-notify-v0.1.0.tar.gz"
            release_root.mkdir(parents=True)
            with tarfile.open(archive_path, "w:gz") as archive:
                archive.add(package_root, arcname="agent-notify-v0.1.0")

            result = self.run_install_release(
                "v0.1.0",
                "--flag",
                "demo",
                env={
                    "AGENT_NOTIFY_RELEASE_BASE_URL": f"file://{temp_root / 'releases'}",
                    "AGENT_NOTIFY_TEST_OUTPUT": str(output_path),
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output_path.read_text(encoding="utf-8").splitlines(), ["--flag", "demo"])

    def test_install_release_requires_exact_version_tag(self) -> None:
        result = self.run_install_release("latest")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exact version", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
