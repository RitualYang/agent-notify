# Notification Localization And Documentation Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make notifications follow the system language by default, preserve explicit user copy overrides, clean up legacy installer-written Chinese defaults on upgrade, and replace the public docs with an English root README plus a Chinese guide under `docs/`.

**Architecture:** Keep localization runtime-driven inside `hooks/notify.py` so installed runtimes change language automatically when macOS language settings change. Move installer defaults in `scripts/providers.py` to non-language settings only, add a targeted migration that removes exact-match legacy default copy during install and update, and cover both runtime and installer behavior with `unittest` before rewriting the docs.

**Tech Stack:** Python 3, Bash, `unittest`, Git

**Execution Notes:** Follow @superpowers/test-driven-development for every behavior change and use @superpowers/verification-before-completion before claiming the full regression suite is green.

---

### File Structure

**Existing files to modify**

- [hooks/notify.py](/Users/wty/agent-notify/hooks/notify.py)
  Responsible for runtime defaults, notification copy resolution, client classification, and macOS notification rendering.
- [scripts/providers.py](/Users/wty/agent-notify/scripts/providers.py)
  Responsible for installer default config data, runtime copy, update-mode config merging, and config cleanup during install.
- [tests/test_notify_runtime.py](/Users/wty/agent-notify/tests/test_notify_runtime.py)
  Responsible for dry-run runtime verification, payload fixtures, and new system-language coverage.
- [tests/test_install_cli.py](/Users/wty/agent-notify/tests/test_install_cli.py)
  Responsible for install/update regression coverage and config migration verification.
- [README.md](/Users/wty/agent-notify/README.md)
  Responsible for the main public-facing English documentation.

**New files to create**

- [README.zh-CN.md](/Users/wty/agent-notify/docs/README.zh-CN.md)
  Responsible for the Chinese user guide that mirrors the concise public documentation.

**No new production modules**

- Keep runtime localization inside `hooks/notify.py` because the installer still deploys a single copied runtime script.
- Keep installer migration logic inside `scripts/providers.py` because `copy_runtime()` already owns default-config preparation.

### Task 1: Add Failing Runtime Localization Tests

**Files:**
- Modify: [tests/test_notify_runtime.py](/Users/wty/agent-notify/tests/test_notify_runtime.py)

- [ ] **Step 1: Add a helper that fakes `defaults read -g AppleLanguages` with realistic output**

Add a test helper that writes a temporary `defaults` executable and prepends it to `PATH` so runtime tests do not depend on the real host language:

```python
def make_fake_defaults_env(self, temp_root: Path, output: str) -> dict[str, str]:
    bin_dir = temp_root / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    defaults_bin = bin_dir / "defaults"
    defaults_bin.write_text(
        "#!/bin/bash\n"
        'if [ "$1" = "read" ] && [ "$2" = "-g" ] && [ "$3" = "AppleLanguages" ]; then\n'
        "  cat <<'EOF'\n"
        f"{output}\n"
        "EOF\n"
        "  exit 0\n"
        "fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    defaults_bin.chmod(0o755)
    return {**os.environ, "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}"}
```

- [ ] **Step 2: Add plist-style `AppleLanguages` parsing tests**

Use realistic `defaults` output such as:

```text
(
    "pt-BR",
    "ja-JP",
    "en-US"
)
```

and assert the runtime picks the first supported language in order:

```python
self.assertEqual(output["notification"]["subtitle"], "agent-notify · 完了")
```

- [ ] **Step 3: Add environment-fallback tests for `LC_ALL`, `LC_CTYPE`, `LANG`, and final English fallback**

Cover cases where the fake `defaults` command exits non-zero or returns no supported language, then assert:

```python
"LC_ALL=fr_CA.UTF-8" -> "Terminé"
"LC_CTYPE=de_DE.UTF-8" -> "Abgeschlossen"
"LANG=es_ES.UTF-8" -> "Completado"
no supported env vars -> "Completed"
```

- [ ] **Step 4: Add explicit `complete` localization tests for `zh`, `ja`, and `fr`**

Add dry-run tests that force the system language and assert the `complete` subtitle matches the spec catalog. Use separate test cases or table-driven subtests so each language maps to one notification output:

```python
self.assertEqual(output["notification"]["subtitle"], "agent-notify · 执行完成")
self.assertEqual(output["notification"]["subtitle"], "agent-notify · 执行完成")  # zh-Hant -> zh
self.assertEqual(output["notification"]["subtitle"], "agent-notify · 完了")
self.assertEqual(output["notification"]["subtitle"], "agent-notify · Terminé")
```

- [ ] **Step 5: Add explicit `complete` localization tests for `de`, `es`, `ru`, `ko`, and fallback `en`**

Cover with separate test cases or table-driven subtests:

```python
"de-DE" -> "Abgeschlossen"
"es-ES" -> "Completado"
"ru-RU" -> "Готово"
"ko-KR" -> "완료됨"
"pt-BR" -> "Completed"
```

- [ ] **Step 6: Add non-`complete` variant localization tests**

Anchor at least one subtitle and one message outside the `complete` path so partial localization cannot pass:

```python
question_output = self.run_notify(...)
self.assertEqual(question_output["notification"]["subtitle"], "agent-notify · Réponse attendue")
self.assertEqual(question_output["notification"]["message"], "L'agent attend votre réponse.")

error_output = self.run_notify(...)
self.assertEqual(error_output["notification"]["subtitle"], "agent-notify · Erreur")
self.assertEqual(error_output["notification"]["message"], "Une erreur s'est produite pendant l'exécution. Ouvrez l'application pour voir les détails.")
```

Use existing event types so the tests exercise real variant selection, for example:

- a Claude `Elicitation` payload for `question`
- an OpenCode `session.error` payload for `error`
- a Claude `Notification` payload with `notification_type == "permission_prompt"` for `permission`

- [ ] **Step 7: Add a config-override test**

Write a temporary config file and assert explicit `notification_variants.complete.subtitle` still wins over the system language:

```python
config_path.write_text(
    json.dumps({"notification_variants": {"complete": {"subtitle": "My Custom Subtitle"}}}),
    encoding="utf-8",
)
self.assertEqual(output["notification"]["subtitle"], "agent-notify · My Custom Subtitle")
```

- [ ] **Step 8: Run the runtime module to verify the new tests fail**

Run:

```bash
python3 -m unittest tests.test_notify_runtime -v
```

Expected: FAIL because `hooks/notify.py` still hardcodes Chinese defaults and does not inspect the system language.

- [ ] **Step 9: Commit the failing runtime tests**

```bash
git add tests/test_notify_runtime.py
git commit -m "test: add failing runtime localization coverage"
```

### Task 2: Add Failing Installer Migration Tests

**Files:**
- Modify: [tests/test_install_cli.py](/Users/wty/agent-notify/tests/test_install_cli.py)

- [ ] **Step 1: Add a legacy-default fixture helper**

Add a helper payload representing the pre-localization installer-written Chinese defaults that should be auto-removed only when values still match exactly:

```python
LEGACY_DEFAULT_COPY = {
    "notification_variants": {
        "complete": {"subtitle": "执行完成", "message": "任务已完成，等待你查看结果。"},
        "question": {"subtitle": "等待回答", "message": "Agent 正在等待你的回答。"},
        "permission": {"subtitle": "等待授权", "message": "Agent 正在等待你的权限确认。"},
        "input": {"subtitle": "需要补充信息", "message": "Agent 需要你补充更多信息。"},
        "error": {"subtitle": "执行出错", "message": "运行过程中发生错误，请打开界面查看。"},
    },
    "claude": {"stop_message": "任务已完成，等待你查看结果。"},
    "cursor": {
        "stop_message": "Agent 已执行完毕，等待你查看结果。",
        "question_message": "Agent 正在等待你的回答。",
    },
    "opencode": {"stop_message": "会话已进入空闲状态，等待你查看结果。"},
    "codex": {"stop_message": "任务已完成，等待你查看结果。"},
}
```

- [ ] **Step 2: Add an update test that removes exact-match legacy copy**

Seed `config.json` with legacy defaults plus unrelated non-language settings, run `--update-installed`, and assert:

```python
self.assertNotIn("notification_variants", config)
self.assertEqual(config["macos"]["sound"], "Glass")
self.assertEqual(config["cursor"]["notify_on_question"], True)
self.assertNotIn("stop_message", config["claude"])
self.assertNotIn("stop_message", config["cursor"])
self.assertNotIn("question_message", config["cursor"])
self.assertNotIn("stop_message", config["opencode"])
self.assertNotIn("stop_message", config["codex"])
```

- [ ] **Step 3: Add an update test that preserves custom overrides**

Seed `config.json` with a custom value that differs from the legacy default and assert it survives update:

```python
self.assertEqual(config["cursor"]["question_message"], "Keep my custom prompt")
```

- [ ] **Step 4: Add a mixed-subtree migration test**

Seed one branch with both exact-match legacy defaults and one user-edited value, then assert cleanup removes only the exact matches:

```python
self.assertNotIn("complete", config["notification_variants"])
self.assertEqual(config["notification_variants"]["question"]["message"], "Keep my custom prompt")
```

- [ ] **Step 5: Add a fresh-install test that no longer writes localized default copy into `config.json`**

Install into an empty temp tree and assert the generated config contains non-language defaults such as:

```python
self.assertEqual(config["macos"]["sound"], "Glass")
self.assertEqual(config["dedupe_window_seconds"], 2)
self.assertIn("question_patterns", config["cursor"])
self.assertEqual(config["opencode"]["notification_events"], ["permission.asked", "session.error"])
```

and does not eagerly write:

```python
self.assertNotIn("notification_variants", config)
```

- [ ] **Step 6: Run the focused installer tests to verify failure**

Run:

```bash
python3 -m unittest tests.test_install_cli.InstallCliTests.test_update_installed_removes_legacy_default_copy -v
python3 -m unittest tests.test_install_cli.InstallCliTests.test_update_installed_preserves_custom_override_copy -v
python3 -m unittest tests.test_install_cli.InstallCliTests.test_update_installed_removes_only_exact_match_legacy_values -v
python3 -m unittest tests.test_install_cli.InstallCliTests.test_install_writes_only_non_language_default_config -v
```

Expected: FAIL because `scripts/providers.py` still merges the old language-bearing defaults into `config.json` and has no legacy-copy cleanup step.

- [ ] **Step 7: Commit the failing installer tests**

```bash
git add tests/test_install_cli.py
git commit -m "test: add failing installer localization coverage"
```

### Task 3: Implement Runtime Localization

**Files:**
- Modify: [hooks/notify.py](/Users/wty/agent-notify/hooks/notify.py)
- Modify: [tests/test_notify_runtime.py](/Users/wty/agent-notify/tests/test_notify_runtime.py)

- [ ] **Step 1: Split static defaults from localized copy**

Replace the single hardcoded `DEFAULT_CONFIG` with a non-language base config plus an explicit per-language catalog:

```python
BASE_CONFIG = {
    "macos": {"sound": "Glass"},
    "dedupe_window_seconds": 2,
    "claude": {"notify_on_stop": True, "notify_on_notification": True, ...},
    "cursor": {"notify_on_stop": True, "notify_on_question": True, ...},
    "opencode": {"notify_on_stop": True, "notify_on_notification": True, ...},
    "codex": {"notify_on_stop": True, "stop_title": "Codex", "notification_title": "Codex"},
}

LOCALIZED_COPY = {
    "en": {"notification_variants": {...}, "cursor": {"stop_message": ...}, "opencode": {"stop_message": ...}},
    "zh": {"notification_variants": {...}, "cursor": {"stop_message": ...}, "opencode": {"stop_message": ...}},
    ...
}
```

- [ ] **Step 2: Add language normalization and system-language resolution helpers**

Implement helpers that:

```python
def normalize_language_tag(value: str | None) -> str | None: ...
def parse_apple_languages(output: str) -> list[str]: ...
def resolve_system_language() -> str: ...
```

Requirements:

- run `defaults read -g AppleLanguages`
- inspect candidates in order
- normalize `zh-Hans`, `zh_Hant`, `fr-CA`, `en_US.UTF-8`
- fall back through `LC_ALL`, `LC_CTYPE`, and `LANG`
- default to `"en"`

- [ ] **Step 3: Build localized runtime defaults and merge user config on top**

Update config loading so runtime defaults are built per invocation:

```python
def build_default_config(language: str) -> dict[str, Any]:
    return deep_merge(BASE_CONFIG, LOCALIZED_COPY[language])

def load_config(config_path: Path) -> dict[str, Any]:
    language = resolve_system_language()
    return deep_merge(build_default_config(language), load_json(config_path, {}))
```

- [ ] **Step 4: Keep existing message-resolution behavior while using the localized defaults**

Confirm `resolve_notification_message()` and `resolve_notification_subtitle()` still prioritize explicit payload and config values before falling back to localized defaults:

```python
if normalized:
    return normalized
if kind == "complete" and isinstance(client_config.get("stop_message"), str):
    return str(client_config["stop_message"])
```

Only adjust logic if a localized path cannot be reached through the new config structure.

- [ ] **Step 5: Run the runtime module to verify the localization tests pass**

Run:

```bash
python3 -m unittest tests.test_notify_runtime -v
```

Expected: PASS, including the new per-language assertions and existing client-classification coverage.

- [ ] **Step 6: Commit the runtime localization implementation**

```bash
git add hooks/notify.py tests/test_notify_runtime.py
git commit -m "feat: localize runtime notification defaults"
```

### Task 4: Implement Installer Default Cleanup And Minimal Config Writes

**Files:**
- Modify: [scripts/providers.py](/Users/wty/agent-notify/scripts/providers.py)
- Modify: [tests/test_install_cli.py](/Users/wty/agent-notify/tests/test_install_cli.py)

- [ ] **Step 1: Trim installer defaults down to non-language settings**

Update `scripts/providers.py` so installer defaults no longer include `notification_variants` or other localized copy, but do retain every non-language runtime dependency required by the spec:

```python
DEFAULT_CONFIG = {
    "macos": {"sound": "Glass"},
    "dedupe_window_seconds": 2,
    "claude": {
        "notify_on_stop": True,
        "notify_on_notification": True,
        "notification_types": ["permission_prompt", "idle_prompt", "elicitation_dialog"],
    },
    "cursor": {
        "notify_on_stop": True,
        "notify_on_question": True,
        "suppress_stop_after_question_seconds": 8,
        "question_patterns": [...],
    },
    "opencode": {
        "notify_on_stop": True,
        "notify_on_notification": True,
        "notification_events": ["permission.asked", "session.error"],
    },
    "codex": {"notify_on_stop": True},
}
```

- [ ] **Step 2: Add exact-match legacy-copy cleanup helpers**

Implement nested-path cleanup so install/update removes only stale defaults:

```python
LEGACY_DEFAULT_COPY_PATHS = {
    ("notification_variants", "complete", "subtitle"): "执行完成",
    ("notification_variants", "complete", "message"): "任务已完成，等待你查看结果。",
    ("notification_variants", "question", "subtitle"): "等待回答",
    ("notification_variants", "question", "message"): "Agent 正在等待你的回答。",
    ("notification_variants", "permission", "subtitle"): "等待授权",
    ("notification_variants", "permission", "message"): "Agent 正在等待你的权限确认。",
    ("notification_variants", "input", "subtitle"): "需要补充信息",
    ("notification_variants", "input", "message"): "Agent 需要你补充更多信息。",
    ("notification_variants", "error", "subtitle"): "执行出错",
    ("notification_variants", "error", "message"): "运行过程中发生错误，请打开界面查看。",
    ("claude", "stop_message"): "任务已完成，等待你查看结果。",
    ("cursor", "stop_message"): "Agent 已执行完毕，等待你查看结果。",
    ("cursor", "question_message"): "Agent 正在等待你的回答。",
    ("opencode", "stop_message"): "会话已进入空闲状态，等待你查看结果。",
    ("codex", "stop_message"): "任务已完成，等待你查看结果。",
}

def remove_legacy_default_copy(config: dict[str, Any]) -> dict[str, Any]:
    cleaned = deepcopy(config)
    for path, legacy_value in LEGACY_DEFAULT_COPY_PATHS.items():
        if get_nested_value(cleaned, path) == legacy_value:
            delete_nested_value(cleaned, path)
    return prune_empty_dicts(cleaned)
```

- [ ] **Step 3: Run cleanup before merging non-language defaults**

Update `merge_default_config()` so it:

```python
current = load_json(config_path, {})
cleaned = remove_legacy_default_copy(current)
merged = merge_missing_defaults(cleaned, DEFAULT_CONFIG)
```

This makes fresh installs light and lets upgrades return to system-language runtime defaults.

- [ ] **Step 4: Run the installer module to verify the new tests pass**

Run:

```bash
python3 -m unittest tests.test_install_cli -v
```

Expected: PASS, including the new cleanup tests and existing installer coverage.

- [ ] **Step 5: Commit the installer migration changes**

```bash
git add scripts/providers.py tests/test_install_cli.py
git commit -m "feat: migrate legacy notification copy defaults"
```

### Task 5: Refresh Public Documentation And Run Final Verification

**Files:**
- Modify: [README.md](/Users/wty/agent-notify/README.md)
- Create: [README.zh-CN.md](/Users/wty/agent-notify/docs/README.zh-CN.md)

- [ ] **Step 1: Rewrite the root README in English**

Restructure the root README around user-facing sections:

```markdown
# agent-notify

macOS notifications for Claude Code, Cursor, OpenCode, and Codex.

## Quick Start
## Install From A Release
## Supported Clients
## Configuration
## Notes
```

Keep implementation detail brief and document that notification copy follows the system language by default.

- [ ] **Step 2: Add a Chinese guide under `docs/README.zh-CN.md`**

Create a concise Chinese document that mirrors the public usage guidance:

```markdown
# agent-notify 中文说明

- 支持的客户端
- 安装与升级
- 配置文件位置
- 通知默认跟随系统语言
- 自定义文案会覆盖默认值
```

- [ ] **Step 3: Add cross-links between the English and Chinese docs**

Ensure:

```markdown
[简体中文说明](docs/README.zh-CN.md)
[English README](../README.md)
```

The exact relative links should match the final file locations.

- [ ] **Step 4: Run the full regression suite after the documentation update**

Run:

```bash
python3 -m unittest tests.test_notify_runtime tests.test_install_cli -v
```

Expected: PASS

- [ ] **Step 5: Commit the docs refresh**

```bash
git add README.md docs/README.zh-CN.md
git commit -m "docs: refresh localized notification documentation"
```
