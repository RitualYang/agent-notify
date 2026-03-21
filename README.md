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
