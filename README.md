# agent-notify

为 `Claude Code`、`Cursor`、`OpenCode` 提供 macOS 系统通知。

一个脚本即可同步状态：勾选的客户端会启用通知，取消勾选的客户端会被移除。

通知副标题会尽量携带当前项目文件夹名，便于同时操作多个项目时区分来源。

## Quick Start

克隆仓库后执行：

```bash
./install.sh
```

交互菜单：

- `↑ / ↓`：移动
- `Space`：勾选 / 取消
- `Enter`：确认
- `a`：全选 / 全不选
- `q`：退出

说明：

- 会按前置检查结果预勾选已完成配置的客户端
- 未检测到可用配置时，默认全部不勾选
- 全部取消后回车，会删除所有已支持客户端
- 完成后请重启对应应用

## 支持范围

- `Claude Code`：完成提醒、需要处理时提醒
- `Cursor`：完成提醒、需要确认时提醒
- `OpenCode`：`session.idle`、`permission.asked`、`session.error`

## 常用命令

```bash
./install.sh               # 交互式选择
./install.sh all           # 启用全部
./install.sh none          # 删除全部
./install.sh claude cursor # 只保留 Claude Code + Cursor
./install.sh opencode      # 只保留 OpenCode
```

也支持：

```bash
./install.sh claude,opencode
./install.sh 1 3
```

## 写入位置

- `~/.agent-notify/bin/notify.py`
- `~/.agent-notify/config.json`
- `~/.claude/settings.json`
- `~/.cursor/hooks.json`
- `~/.config/opencode/plugins/agent-notify.js`

## 配置

编辑 `~/.agent-notify/config.json`：

- `macos.sound`：通知声音
- `claude.notify_on_stop`：Claude 完成提醒开关
- `cursor.notify_on_question`：Cursor 提问提醒开关
- `cursor.question_patterns`：Cursor 提问关键词
- `opencode.notify_on_notification`：OpenCode 事件提醒开关
- `dedupe_window_seconds`：去重窗口

## 进阶

底层脚本仍可直接调用：

```bash
python3 scripts/install.py --client claude --client opencode
python3 scripts/install.py --client none
python3 scripts/install.py --print-installed
python3 scripts/install.py --print-interactive-defaults
```

## 说明

- `Cursor` 的“需要确认”目前是文本启发式判断，可能有少量误报或漏报
- `Codex` 目前只预留了扩展位，尚未接入稳定的 hooks / plugin 配置
