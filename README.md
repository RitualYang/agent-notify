# agent-notify

为 `Claude Code`、`Cursor`、`OpenCode` 提供 macOS 系统通知。

一个脚本即可同步状态：勾选的客户端会启用通知，取消勾选的客户端会被移除。

通知副标题会尽量携带当前项目文件夹名，便于同时操作多个项目时区分来源。

## Quick Start

克隆仓库后执行：

```bash
./install.sh
```

## Release 安装

如果希望按已发布版本安装，可以直接使用对应 release：

方式一，下载版本压缩包后安装：

```bash
curl -fsSLO https://github.com/RitualYang/agent-notify/releases/download/v0.1.0/agent-notify-v0.1.0.tar.gz
tar -xzf agent-notify-v0.1.0.tar.gz
cd agent-notify-v0.1.0
./install.sh
```

方式二，下载 release 安装脚本并指定精确版本：

```bash
curl -fsSLO https://github.com/RitualYang/agent-notify/releases/download/v0.1.0/install-release.sh
bash install-release.sh v0.1.0
```

如果已经安装过旧版本，升级时可以直接保留当前启用状态：

```bash
curl -fsSLO https://github.com/RitualYang/agent-notify/releases/download/v0.1.1/install-release.sh
bash install-release.sh v0.1.1 update
```

说明：

- `install-release.sh` 只支持精确版本，例如 `v0.1.0`
- 不支持 `latest`、`v0.1.x`、`^0.1` 这类范围写法
- 安装脚本会下载对应版本的 `agent-notify-v0.1.0.tar.gz`，解压后执行其中的 `install.sh`
- 传入 `update` 时，会按当前已安装客户端原地升级，不会自动启用新的客户端

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
./install.sh update        # 升级当前已安装客户端
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
- `notification_variants.<kind>.subtitle`：统一通知副标题模板
- `notification_variants.<kind>.message`：统一通知消息模板
- `claude.notify_on_stop`：Claude 完成提醒开关
- `cursor.notify_on_question`：Cursor 提问提醒开关
- `cursor.question_patterns`：Cursor 提问关键词
- `opencode.notify_on_notification`：OpenCode 事件提醒开关
- `dedupe_window_seconds`：去重窗口

其中 `<kind>` 当前包括：

- `complete`
- `question`
- `permission`
- `input`
- `error`

## 进阶

底层脚本仍可直接调用：

```bash
python3 scripts/install.py --client claude --client opencode
python3 scripts/install.py --update-installed
python3 scripts/install.py --client none
python3 scripts/install.py --print-installed
python3 scripts/install.py --print-interactive-defaults
```

## 说明

- `Cursor` 的“需要确认”目前是文本启发式判断，可能有少量误报或漏报
- `Codex` 目前只预留了扩展位，尚未接入稳定的 hooks / plugin 配置
- `./install.sh update` 会保留当前已启用客户端，并只补齐新版运行时与新增默认配置，不会覆盖你的已有自定义配置

## 发布 Release

发布一个新版本时：

```bash
git tag v0.1.0
git push origin v0.1.0
```

GitHub Actions 会在 tag push 后自动：

- 运行测试
- 构建 `agent-notify-v0.1.0.tar.gz`
- 创建或更新同名 GitHub Release
- 上传 `agent-notify-v0.1.0.tar.gz` 和 `install-release.sh`

如果需要补发某个已存在 tag 的 release 资产，也可以手动触发仓库里的 `Release` workflow，并传入精确版本号。
