#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
import tarfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+$")
RELEASE_PATHS = (
    "install.sh",
    "install-release.sh",
    "README.md",
    "LICENSE",
    "hooks/notify.py",
    "scripts/install.py",
    "scripts/providers.py",
    "scripts/interactive-select.sh",
    "plugins/opencode/agent-notify.js.template",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a versioned release archive for agent-notify.")
    parser.add_argument("--version", required=True, help="Exact release tag like v0.1.0")
    parser.add_argument("--output-dir", default="dist", help="Directory where the tar.gz archive will be written.")
    return parser.parse_args()


def validate_version(version: str) -> None:
    if not VERSION_RE.fullmatch(version):
        raise ValueError("Version must be an exact vX.Y.Z tag.")


def build_release(version: str, output_dir: Path) -> Path:
    validate_version(version)
    output_dir.mkdir(parents=True, exist_ok=True)

    archive_path = output_dir / f"agent-notify-{version}.tar.gz"
    archive_root = f"agent-notify-{version}"

    with tarfile.open(archive_path, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        for relative_path in RELEASE_PATHS:
            source_path = REPO_ROOT / relative_path
            if not source_path.exists():
                raise FileNotFoundError(f"Missing release path: {relative_path}")
            archive.add(source_path, arcname=f"{archive_root}/{relative_path}")

    return archive_path


def main() -> int:
    args = parse_args()
    try:
        archive_path = build_release(args.version, Path(args.output_dir).expanduser().resolve())
    except (ValueError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(archive_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
