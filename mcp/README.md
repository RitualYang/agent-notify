# agent-notify

一个轻量级 MCP Server，让 AI 编程助手在完成任务后自动发送桌面通知。

> 不需要用户显式提示 —— 通过系统提示词指令，AI 自动调用通知工具。

## 工作原理

```
AI Agent 完成任务
    │ 系统提示词指示: "MUST call send_notification"
    ▼
AI 调用 send_notification MCP 工具
    │ stdio (JSON-RPC)
    ▼
agent-notify MCP Server
    │ osascript
    ▼
macOS 通知中心 🔔
```

AI 客户端通过 MCP 协议（stdio）与 agent-notify 通信。通过在项目的系统提示词文件中声明通知规则，AI 会在每次完成任务或遇到错误时自动调用 `send_notification` 工具，无需用户每次手动提示。

## 功能

- **`send_notification`** — 发送 macOS 桌面通知（标题、内容、可选提示音）
- **`list_notifications`** — 查询最近的通知历史（内存中保留最近 100 条）
- **`get_config`** — 返回通知配置，AI 首次连接时可调用以了解通知职责

## 安装

### 前置要求

- Python >= 3.10
- macOS（当前仅支持 macOS 通知）
- [uv](https://docs.astral.sh/uv/)（推荐）

### 从源码安装

```bash
git clone <repo-url> agent-notify
cd agent-notify
uv sync
```

## 集成配置

### Claude Code

```bash
# 安装
claude mcp add notify -- uv run --directory /path/to/agent-notify/mcp agent-notify

# 卸载
claude mcp remove notify
```

然后在项目根目录创建 `CLAUDE.md`：

```markdown
Every time you complete a task or encounter an error that needs user attention,
you MUST call the `send_notification` tool with:
- `title`: Brief summary (e.g., "Task Complete", "Build Failed")
- `message`: What was done or what went wrong
- `sound`: true for errors, true for task completion
```

### Cursor

在项目根目录创建 `.cursor/mcp.json`：

```json
{
  "mcpServers": {
    "notify": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/agent-notify", "agent-notify"]
    }
  }
}
```

并在 `.cursorrules` 中添加相同的通知规则。

### Trae

在项目根目录创建 `.trae/mcp.json`：

```json
{
  "mcpServers": {
    "notify": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/agent-notify", "agent-notify"]
    }
  }
}
```

并在 `.trae/rules` 中添加通知规则。

### 其他 MCP 兼容工具

任何支持 MCP 协议的 AI 编程工具都可以通过 stdio 方式接入，配置方式类似。

## MCP 工具详情

### send_notification

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `title` | string | 是 | - | 通知标题 |
| `message` | string | 是 | - | 通知内容 |
| `sound` | boolean | 否 | `true` | 是否播放提示音 |

**返回值**: `"Notification sent: {title}"` 或 `"Failed to send notification: {title}"`

### list_notifications

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `limit` | integer | 否 | `10` | 返回最近 N 条通知 |

**返回值**: 通知记录数组，按时间倒序，包含 `title`、`message`、`timestamp` 字段。

### get_config

无参数。返回当前通知配置及 AI 行为指令。

## 开发

```bash
# 安装开发依赖
uv sync

# 运行测试
uv run pytest -v

# 使用 MCP Inspector 调试
uv run mcp dev src/agent_notify/server.py
```

## 项目结构

```
agent-notify/
├── src/agent_notify/
│   ├── server.py              # MCP Server 入口 + 工具定义
│   ├── store.py               # 内存通知历史存储
│   └── notifiers/
│       └── macos.py           # macOS osascript 通知实现
├── tests/
│   ├── test_macos_notifier.py # 通知器测试 (4)
│   ├── test_store.py          # 存储测试 (4)
│   └── test_tools.py          # MCP 工具注册测试 (3)
├── pyproject.toml
├── CLAUDE.md                  # Claude Code 自动通知规则
└── README.md
```

## 后续开发计划

### v0.2.0 — 多通道通知

- [ ] **Slack Webhook** — 通过 Incoming Webhook 推送通知到 Slack 频道
- [ ] **飞书 Webhook** — 支持飞书自定义机器人
- [ ] **钉钉 Webhook** — 支持钉钉群机器人
- [ ] **Telegram Bot** — 通过 Bot API 推送通知
- [ ] **通道配置文件** — 支持 `~/.agent-notify/config.toml` 配置多通道参数
- [ ] **`configure_channel` 工具** — AI 可查询/切换通知通道

### v0.3.0 — 跨平台支持

- [ ] **Linux** — 使用 `notify-send` 发送桌面通知
- [ ] **Windows** — 使用 Windows Toast 通知
- [ ] **平台自动检测** — 运行时检测 OS 并选择合适的 notifier

### v0.4.0 — 智能通知

- [ ] **通知级别** — 支持 `info` / `warning` / `error` 级别，不同级别不同表现
- [ ] **通知过滤** — 可配置只接收特定级别或关键词的通知
- [ ] **通知聚合** — 短时间内多条通知合并为一条摘要通知
- [ ] **勿扰模式** — 支持时间段静默，通知写入历史但不弹出

### v0.5.0 — 持久化与分析

- [ ] **SQLite 持久化** — 通知历史持久存储，跨进程可查
- [ ] **通知统计** — 按项目/工具/时间段统计通知频率
- [ ] **`search_notifications` 工具** — 支持按关键词搜索历史通知

### v1.0.0 — 发布与分发

- [ ] **PyPI 发布** — `pip install agent-notify` / `uvx agent-notify`
- [ ] **npm wrapper** — 支持 `npx agent-notify`（无需 Python 环境）
- [ ] **配置向导** — `agent-notify setup` 交互式配置通道和 AI 工具集成
- [ ] **完善文档** — 英文 README、各工具集成指南、贡献指南

## 许可证

MIT
