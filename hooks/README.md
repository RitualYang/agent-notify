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
