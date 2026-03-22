#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./install-release.sh v0.1.0 [install.sh args...]

Downloads the exact tagged release archive, extracts it to a temporary
directory, and runs the packaged install.sh with the remaining arguments.

Environment:
  AGENT_NOTIFY_REPO              Override GitHub repo, default: RitualYang/agent-notify
  AGENT_NOTIFY_RELEASE_BASE_URL  Override asset base URL
EOF
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

if [ "$#" -lt 1 ]; then
  usage >&2
  exit 1
fi

case "${1:-}" in
  -h|--help)
    usage
    exit 0
    ;;
esac

version="$1"
shift

if ! printf '%s\n' "$version" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+$'; then
  echo "Expected an exact version tag like v0.1.0. Range matching is not supported." >&2
  exit 1
fi

require_cmd curl
require_cmd tar
require_cmd mktemp

repo="${AGENT_NOTIFY_REPO:-RitualYang/agent-notify}"
base_url="${AGENT_NOTIFY_RELEASE_BASE_URL:-https://github.com/${repo}/releases/download}"
asset_name="agent-notify-${version}.tar.gz"
asset_url="${base_url}/${version}/${asset_name}"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/agent-notify-release.XXXXXX")"
cleanup() {
  rm -rf "$tmpdir"
}
trap cleanup EXIT

archive_path="$tmpdir/$asset_name"
package_dir="$tmpdir/agent-notify-${version}"

curl -fsSL "$asset_url" -o "$archive_path"
tar -xzf "$archive_path" -C "$tmpdir"

if [ ! -f "$package_dir/install.sh" ]; then
  echo "Downloaded archive does not contain agent-notify-${version}/install.sh" >&2
  exit 1
fi

bash "$package_dir/install.sh" "$@"
