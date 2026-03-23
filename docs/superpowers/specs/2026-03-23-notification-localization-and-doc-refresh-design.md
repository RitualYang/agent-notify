# Notification Localization And Documentation Refresh Design

**Date:** 2026-03-23

**Goal:** Make notification copy follow the system language by default, keep user-configured notification copy as an override, and simplify the public documentation with an English root README plus a Chinese guide under `docs/`.

## Confirmed Requirements

- Notifications should follow the system language automatically.
- Supported languages are:
  - `zh`
  - `ja`
  - `en`
  - `fr`
  - `de`
  - `es`
  - `ru`
  - `ko`
- If the system language does not match one of the supported languages, the default notification copy must fall back to English.
- User-defined notification copy in `~/.agent-notify/config.json` must continue to override the system-language defaults.
- The current notification runtime should keep using the shared notification variants:
  - `complete`
  - `question`
  - `permission`
  - `input`
  - `error`
- Root `README.md` should be rewritten in English.
- A Chinese README should be added under `docs/`.
- The documentation section that describes implementation details should be reduced and refocused on user-facing behavior.

## Design

### 1. Localization Model

Notification localization remains runtime-driven rather than install-time driven.

The runtime in [notify.py](/Users/wty/agent-notify/hooks/notify.py) should resolve the active language for each invocation, then build localized default notification copy from an internal language catalog.

Supported runtime language codes:

- `zh`
- `ja`
- `en`
- `fr`
- `de`
- `es`
- `ru`
- `ko`

The catalog should cover all shared notification variants and any client-specific fallback messages that are currently hardcoded in defaults.

This keeps system-language behavior dynamic. If the user changes the macOS language later, the next notification should use the new language without reinstalling `agent-notify`.

### 2. Language Resolution Rules

Language detection should be deterministic and conservative.

Resolution order:

1. macOS preferred languages via `AppleLanguages`
2. process locale and environment fallbacks such as `LANG`
3. fallback to `en`

Normalization rules:

- compare only the base language code
- accept formats such as `zh-Hans`, `zh_CN`, `ja-JP`, and `en_US`
- map unsupported values to no match rather than guessing a nearby language

Examples:

- `zh-Hans` -> `zh`
- `ja-JP` -> `ja`
- `fr-CA` -> `fr`
- `pt-BR` -> fallback to `en`

The runtime should use the first supported language it can resolve.

### 3. Configuration And Override Behavior

Localized copy should stop being duplicated as static defaults in both the runtime and installer.

The runtime should introduce a localized default-config builder:

- non-language defaults remain static
- language-sensitive subtitle and message defaults are generated from the resolved language

The installer-side defaults in [providers.py](/Users/wty/agent-notify/scripts/providers.py) should retain only non-language defaults such as:

- `macos.sound`
- `dedupe_window_seconds`
- client enablement flags
- Cursor question-detection patterns
- OpenCode event lists

User override behavior stays unchanged:

- if `config.json` defines `notification_variants.<kind>.subtitle`, use it
- if `config.json` defines `notification_variants.<kind>.message`, use it
- if `config.json` defines client-specific fallback copy, use it
- otherwise use the localized runtime defaults

This preserves compatibility with existing installs where users already customized copy.

### 4. Runtime Structure

The localization logic should stay inside [notify.py](/Users/wty/agent-notify/hooks/notify.py) instead of introducing a new shared Python module.

Reason:

- the installer currently copies `notify.py` as a single runtime file into `~/.agent-notify/bin/notify.py`
- splitting localization into a second Python module would also require changing runtime packaging and distribution
- this request only needs localized copy and docs cleanup, not a runtime packaging refactor

Suggested runtime additions:

- a language catalog constant keyed by supported language code
- a `normalize_language_tag()` helper
- a `resolve_system_language()` helper
- a `build_default_config(language)` helper

The rest of the notification classification flow should stay unchanged.

### 5. Backward Compatibility

Existing installs must continue to work without migration.

Compatibility expectations:

- old `config.json` files that already contain Chinese default copy remain valid
- customized user copy continues to override runtime defaults
- fresh installs and upgrades should not need to rewrite every localized message into `config.json`
- a missing or partially customized config file should still produce localized notifications

This means localization becomes a runtime concern, while `config.json` becomes primarily a place for user preferences and optional overrides.

### 6. Testing Strategy

Runtime coverage in [test_notify_runtime.py](/Users/wty/agent-notify/tests/test_notify_runtime.py) should verify:

- Chinese system language resolves to Chinese notification copy
- Japanese system language resolves to Japanese notification copy
- French system language resolves to French notification copy
- unsupported system language falls back to English
- explicit config overrides beat the system-language defaults

Language detection tests should be stable and not rely on the real host language. They should simulate macOS language lookup by controlling the lookup command or environment inside the test process.

Installer coverage in [test_install_cli.py](/Users/wty/agent-notify/tests/test_install_cli.py) should verify:

- upgrade keeps existing custom overrides in `config.json`
- upgrade still writes non-language defaults that are required for runtime behavior
- installer no longer depends on shipping the full localized notification copy inside default config data

### 7. Documentation Refresh

The public docs should be reorganized around user-facing usage, not implementation detail.

Root [README.md](/Users/wty/agent-notify/README.md):

- rewrite in English
- keep the scope concise
- cover:
  - what `agent-notify` does
  - supported clients
  - install and update commands
  - config file location
  - notification localization behavior
  - important notes about Cursor heuristics and Codex experimental support

Chinese guide:

- add [README.zh-CN.md](/Users/wty/agent-notify/docs/README.zh-CN.md)
- describe the same user-facing behavior in Chinese
- mention that notification copy follows the system language by default
- explain that `config.json` can override the default copy

Implementation details should be reduced to only what helps users operate or troubleshoot the tool. The README should not read like an internal architecture log.

## Non-Goals For This Iteration

- adding more than the requested eight languages
- adding per-client translation packs outside the shared notification model
- adding a manual `language` config knob
- changing the existing notification kinds
- refactoring runtime distribution from a single copied script into a Python package
