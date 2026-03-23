#!/usr/bin/env bash

menu_select_clients() {
  local title="$1"
  local allow_empty="$2"
  shift 2
  local defaults=("$@")
  local options=("claude" "cursor" "opencode" "codex")
  local labels=("Claude Code" "Cursor" "OpenCode" "Codex")
  local selected=(0 0 0 0)
  local current=0
  local count=${#options[@]}
  local notice=""
  local old_stty

  if [ "${#defaults[@]}" -gt 0 ]; then
    for default in "${defaults[@]}"; do
      case "$default" in
        claude) selected[0]=1 ;;
        cursor) selected[1]=1 ;;
        opencode) selected[2]=1 ;;
        codex) selected[3]=1 ;;
      esac
    done
  fi

  selected_count() {
    local total=0
    local value
    for value in "${selected[@]}"; do
      total=$((total + value))
    done
    printf '%s' "$total"
  }

  toggle_current() {
    if [ "${selected[$current]}" -eq 1 ]; then
      selected[$current]=0
    else
      selected[$current]=1
    fi
  }

  move_up() {
    if [ "$current" -eq 0 ]; then
      current=$((count - 1))
    else
      current=$((current - 1))
    fi
  }

  move_down() {
    if [ "$current" -eq $((count - 1)) ]; then
      current=0
    else
      current=$((current + 1))
    fi
  }

  render_menu() {
    local total_selected
    total_selected="$(selected_count)"

    printf '\033[H\033[2J'
    printf '%s\n\n' "$title"
    printf 'Checked = enabled, unchecked = removed.\n'
    printf 'Use ↑/↓ to move, Space to select/deselect, Enter to confirm.\n'
    printf 'Also supports j/k to move, a to toggle all, q to quit.\n\n'

    local i marker prefix
    for ((i = 0; i < count; i++)); do
      if [ "${selected[$i]}" -eq 1 ]; then
        marker='[x]'
      else
        marker='[ ]'
      fi

      if [ "$i" -eq "$current" ]; then
        prefix='❯'
      else
        prefix=' '
      fi

      printf '%s %s %s\n' "$prefix" "$marker" "${labels[$i]}"
    done

    printf '\nSelected: %s\n' "$total_selected"
    if [ "$allow_empty" = "true" ] && [ "$total_selected" -eq 0 ]; then
      printf 'Press Enter now to remove all supported clients.\n'
    fi
    if [ -n "$notice" ]; then
      printf '%s\n' "$notice"
    fi
  }

  old_stty=$(stty -g)
  cleanup_menu() {
    stty "$old_stty" 2>/dev/null || true
    printf '\033[?25h'
  }

  trap 'cleanup_menu; exit 130' INT TERM
  printf '\033[?25l'

  while true; do
    render_menu
    IFS= read -rsn1 key
    case "$key" in
      '')
        if [ "$(selected_count)" -gt 0 ] || [ "$allow_empty" = "true" ]; then
          break
        fi
        notice='Please select at least one client.'
        ;;
      ' ')
        toggle_current
        notice=''
        ;;
      j|J)
        move_down
        notice=''
        ;;
      k|K)
        move_up
        notice=''
        ;;
      a|A)
        if [ "$(selected_count)" -eq "$count" ]; then
          selected=(0 0 0 0)
        else
          selected=(1 1 1 1)
        fi
        notice=''
        ;;
      q|Q)
        cleanup_menu
        printf '\nCancelled.\n' >&2
        exit 1
        ;;
      $'\x1b')
        IFS= read -rsn1 -t 1 key1 || true
        if [ "$key1" = '[' ]; then
          IFS= read -rsn1 -t 1 key2 || true
          case "$key2" in
            A) move_up ;;
            B) move_down ;;
          esac
        fi
        notice=''
        ;;
    esac
  done

  cleanup_menu
  trap - INT TERM
  printf '\n'

  MENU_SELECTED_CLIENTS=()
  local i
  for ((i = 0; i < count; i++)); do
    if [ "${selected[$i]}" -eq 1 ]; then
      MENU_SELECTED_CLIENTS+=("${options[$i]}")
    fi
  done
}
