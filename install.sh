#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
# shellcheck source=scripts/interactive-select.sh
source "$ROOT_DIR/scripts/interactive-select.sh"

usage() {
  cat <<'EOF'
Usage:
  ./install.sh                    # interactive sync menu
  ./install.sh update            # refresh currently installed clients
  ./install.sh all               # enable all supported clients
  ./install.sh none              # remove all supported clients
  ./install.sh claude opencode   # enable only selected clients, remove others
  ./install.sh claude,opencode   # comma-separated form also works
  ./install.sh --help

Selections:
  1 = claude
  2 = cursor
  3 = opencode
  4 = codex
  all = enable all supported
  none = remove all supported

This is a single sync script:
- checked items are installed/enabled
- unchecked items are removed
- update refreshes the currently installed clients in place

Extra options are forwarded to scripts/install.py.
Examples:
  ./install.sh
  ./install.sh update
  ./install.sh claude cursor
  ./install.sh none
  ./install.sh opencode --install-dir ~/.agent-notify
EOF
}

selection_to_client() {
  case "$1" in
    1|claude) echo "claude" ;;
    2|cursor) echo "cursor" ;;
    3|opencode) echo "opencode" ;;
    4|codex) echo "codex" ;;
    all|all-supported) echo "all" ;;
    0|none|clear) echo "none" ;;
    both) echo "both" ;;
    *) return 1 ;;
  esac
}

clients=()
forwarded=()
update_installed=false

while [ "$#" -gt 0 ]; do
  case "$1" in
    update)
      update_installed=true
      shift 1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --client)
      if [ "$#" -lt 2 ]; then
        echo "Missing value for --client" >&2
        exit 1
      fi
      clients+=("$2")
      shift 2
      ;;
    --*)
      forwarded+=("$1")
      if [ "$#" -gt 1 ] && [ "${2#-}" = "$2" ]; then
        forwarded+=("$2")
        shift 2
      else
        shift 1
      fi
      ;;
    *)
      clients+=("$1")
      shift 1
      ;;
  esac
done

if [ "$update_installed" = true ] && [ "${#clients[@]}" -gt 0 ]; then
  echo "update cannot be combined with explicit client selections" >&2
  exit 1
fi

if [ "$update_installed" = false ] && [ "${#clients[@]}" -eq 0 ] && [ -t 0 ] && [ -t 1 ]; then
  defaults=()
  cmd=("$PYTHON_BIN" "$ROOT_DIR/scripts/install.py" --print-interactive-defaults)
  if [ "${#forwarded[@]}" -gt 0 ]; then
    cmd+=("${forwarded[@]}")
  fi
  installed_output="$("${cmd[@]}" 2>/dev/null || true)"
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    defaults+=("$line")
  done <<< "$installed_output"
  menu_args=("Select clients to enable notifications for" true)
  if [ "${#defaults[@]}" -gt 0 ]; then
    menu_args+=("${defaults[@]}")
  fi
  menu_select_clients "${menu_args[@]}"
  if [ "${#MENU_SELECTED_CLIENTS[@]}" -eq 0 ]; then
    clients=(none)
  else
    clients=("${MENU_SELECTED_CLIENTS[@]}")
  fi
fi

args=()
if [ "${#clients[@]}" -gt 0 ]; then
  for item in "${clients[@]}"; do
    IFS=',' read -r -a parts <<< "$item"
    for part in "${parts[@]}"; do
      part="$(printf '%s' "$part" | tr '[:upper:]' '[:lower:]')"
      [ -n "$part" ] || continue
      client="$(selection_to_client "$part")" || {
        echo "Unknown client selection: $part" >&2
        exit 1
      }
      args+=("--client" "$client")
    done
  done
fi

cmd=("$PYTHON_BIN" "$ROOT_DIR/scripts/install.py")
if [ "$update_installed" = true ]; then
  cmd+=(--update-installed)
fi
if [ "${#args[@]}" -gt 0 ]; then
  cmd+=("${args[@]}")
fi
if [ "${#forwarded[@]}" -gt 0 ]; then
  cmd+=("${forwarded[@]}")
fi

exec "${cmd[@]}"
