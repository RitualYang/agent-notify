# Hooks Version Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reorganize the repo so the existing MCP server lives under `mcp/`, and add a new `hooks/` directory with a zero-dependency Python CLI that Claude Code hooks can call automatically (Stop + PostToolUse).

**Architecture:** Move all existing files into `mcp/` subdirectory. Create `hooks/notify.py` — a single-file CLI using only stdlib, calling `osascript` directly. Provide `hooks/settings.json` as a ready-to-copy hooks config example.

**Tech Stack:** Python 3.10+ stdlib only (no dependencies), osascript, Claude Code hooks (Stop + PostToolUse)

---

### Task 1: Move existing MCP version into `mcp/` subdirectory

**Files:**
- Move: `src/` → `mcp/src/`
- Move: `tests/` → `mcp/tests/`
- Move: `pyproject.toml` → `mcp/pyproject.toml`
- Move: `README.md` → `mcp/README.md`
- Move: `uv.lock` → `mcp/uv.lock`
- Move: `dist/` → `mcp/dist/`
- Keep: `CLAUDE.md` at root
- Keep: `docs/` at root

**Step 1: Create mcp/ directory and move files**

Run:
```bash
cd /Users/wty/agent-notify
mkdir mcp
git mv src mcp/src
git mv tests mcp/tests
git mv pyproject.toml mcp/pyproject.toml
git mv README.md mcp/README.md
git mv uv.lock mcp/uv.lock
```

**Step 2: Move dist/ (not tracked by git)**

Run:
```bash
mv /Users/wty/agent-notify/dist /Users/wty/agent-notify/mcp/dist
```

**Step 3: Move .venv (not tracked by git)**

Run:
```bash
mv /Users/wty/agent-notify/.venv /Users/wty/agent-notify/mcp/.venv
```

**Step 4: Verify mcp/ structure**

Run: `find /Users/wty/agent-notify/mcp -not -path '*/\.*' -not -path '*/__pycache__/*' -not -path '*/.venv/*' -not -path '*/dist/*'`
Expected:
```
mcp/
mcp/src/agent_notify/__init__.py
mcp/src/agent_notify/server.py
mcp/src/agent_notify/store.py
mcp/src/agent_notify/notifiers/__init__.py
mcp/src/agent_notify/notifiers/macos.py
mcp/tests/test_macos_notifier.py
mcp/tests/test_store.py
mcp/tests/test_tools.py
mcp/pyproject.toml
mcp/README.md
mcp/uv.lock
```

**Step 5: Verify tests still pass from mcp/ directory**

Run: `cd /Users/wty/agent-notify/mcp && uv run pytest -v`
Expected: 11 passed

**Step 6: Commit**

```bash
cd /Users/wty/agent-notify
git add -A
git commit -m "refactor: move MCP server into mcp/ subdirectory"
```

---

### Task 2: Create hooks/notify.py CLI

**Files:**
- Create: `hooks/notify.py`

**Step 1: Create hooks/ directory and notify.py**

```python
# hooks/notify.py
#!/usr/bin/env python3
"""Zero-dependency CLI for Claude Code hooks to send macOS notifications."""
import argparse
import subprocess
import sys


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def notify(title: str, message: str, sound: bool = True) -> bool:
    script = f'display notification "{_escape(message)}" with title "{_escape(title)}"'
    if sound:
        script += ' sound name "Glass"'
    try:
        subprocess.run(["osascript", "-e", script], check=True, timeout=5)
        return True
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", default="Claude Code")
    parser.add_argument("--message", default="Task complete")
    parser.add_argument("--no-sound", action="store_true")
    args = parser.parse_args()
    ok = notify(args.title, args.message, sound=not args.no_sound)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
```

**Step 2: Make it executable**

Run: `chmod +x /Users/wty/agent-notify/hooks/notify.py`

**Step 3: Smoke test**

Run: `python3 /Users/wty/agent-notify/hooks/notify.py --title "Test" --message "hooks notify.py works"`
Expected: macOS notification appears, exit code 0

**Step 4: Commit**

```bash
cd /Users/wty/agent-notify
git add hooks/notify.py
git commit -m "feat: hooks/notify.py zero-dependency CLI for Claude Code hooks"
```

---

### Task 3: Create hooks/settings.json example config

**Files:**
- Create: `hooks/settings.json`

**Step 1: Create settings.json**

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/agent-notify/hooks/notify.py --title \"Claude Code\" --message \"Task complete\""
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash|Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/agent-notify/hooks/notify.py --title \"Tool Used\" --message \"$(echo $CLAUDE_TOOL_NAME) completed\""
          }
        ]
      }
    ]
  }
}
```

**Step 2: Commit**

```bash
cd /Users/wty/agent-notify
git add hooks/settings.json
git commit -m "feat: hooks/settings.json example config for Stop and PostToolUse hooks"
```

---

### Task 4: Create hooks/README.md

**Files:**
- Create: `hooks/README.md`

**Step 1: Create README**

```markdown
# agent-notify — hooks 版

通过 Claude Code hooks 自动触发通知，**无需提示词，无需 MCP Server**。

## 工作原理

```
Claude Code 触发 hook 事件（Stop / PostToolUse）
    │ 自动执行 shell 命令
    ▼
hooks/notify.py（零依赖 Python CLI）
    │ osascript
    ▼
macOS 通知中心 🔔
```

## 安装

无需安装，直接使用 `notify.py`（仅需 Python 3.10+ 和 macOS）。

## 配置

将 `settings.json` 中的 hooks 配置合并到你的 Claude Code 配置文件：

- **全局配置**：`~/.claude/settings.json`
- **项目配置**：`.claude/settings.json`

将 `/path/to/agent-notify` 替换为实际路径。

## hooks 说明

| Hook | 触发时机 | 用途 |
|------|----------|------|
| `Stop` | Claude 每次停止响应时 | 任务完成通知 |
| `PostToolUse` | 指定工具调用后 | 关键操作通知 |

## 手动测试

```bash
python3 hooks/notify.py --title "Test" --message "It works"
python3 hooks/notify.py --title "Silent" --message "No sound" --no-sound
```

## 与 MCP 版对比

| | MCP 版 (`mcp/`) | hooks 版 (`hooks/`) |
|---|---|---|
| 触发方式 | AI 主动调用工具 | Claude Code 自动触发 |
| 需要提示词 | 是（CLAUDE.md） | 否 |
| 安装 | 注册 MCP server | 编辑 settings.json |
| 历史记录 | 内存中 100 条 | 无 |
| 依赖 | mcp[cli] | 无（stdlib only） |
```

**Step 2: Commit**

```bash
cd /Users/wty/agent-notify
git add hooks/README.md
git commit -m "docs: hooks/README.md with setup and comparison guide"
```

---

### Task 5: Update root README.md

**Files:**
- Create: `README.md` (new root-level overview)

**Step 1: Create root README.md**

```markdown
# agent-notify

让 AI 编程助手在完成任务后自动发送 macOS 桌面通知。提供两种集成方式：

| | MCP 版 | hooks 版 |
|---|---|---|
| 目录 | `mcp/` | `hooks/` |
| 触发方式 | AI 主动调用工具 | Claude Code 自动触发 |
| 需要提示词 | 是 | 否 |
| 依赖 | Python + mcp[cli] | Python stdlib only |

## 快速选择

- **想要零配置、自动触发** → 用 [hooks 版](hooks/README.md)
- **想要通知历史记录、多客户端支持** → 用 [MCP 版](mcp/README.md)
```

**Step 2: Commit**

```bash
cd /Users/wty/agent-notify
git add README.md
git commit -m "docs: root README with version comparison"
```
