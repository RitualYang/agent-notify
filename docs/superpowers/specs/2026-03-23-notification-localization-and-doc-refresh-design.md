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
- Upgrade should automatically remove only legacy installer-written default copy values that still exactly match the pre-localization Chinese defaults, so upgraded installs return to system-language defaults without erasing user-edited copy.
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

For this iteration, `zh` means one shared Chinese catalog using Simplified Chinese copy. Because the requested scope is only "Chinese" rather than separate Simplified and Traditional variants, any `zh-*` system tag should resolve to `zh` instead of falling back to English.

This keeps system-language behavior dynamic. If the user changes the macOS language later, the next notification should use the new language without reinstalling `agent-notify`.

### 2. Language Resolution Rules

Language detection should be deterministic and conservative.

Resolution order:

1. run `defaults read -g AppleLanguages`
2. if that fails or yields no supported value, check `LC_ALL`
3. then check `LC_CTYPE`
4. then check `LANG`
5. fallback to `en`

Normalization rules:

- parse `defaults read -g AppleLanguages` as an ordered list of locale tags and inspect them in order
- for each candidate, strip surrounding quotes and whitespace
- lowercase the tag
- remove any charset suffix after `.`, such as `.UTF-8`
- replace `_` with `-`
- if the normalized tag starts with `zh`, resolve to `zh`
- otherwise compare only the base language code before the first `-`
- accept formats such as `zh-Hans`, `zh_CN`, `ja-JP`, and `en_US`
- map unsupported values to no match rather than guessing a nearby language

Examples:

- `zh-Hans` -> `zh`
- `zh-Hant` -> `zh`
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

Legacy-default cleanup should happen during install and update before new defaults are merged:

- inspect only language-sensitive copy fields
- if a field value exactly matches the old installer-written Chinese default string, remove that field from `config.json`
- if a field value differs from the legacy default string, keep it as a user override
- prune any now-empty nested objects after cleanup

Fields covered by this cleanup:

- `notification_variants.complete.subtitle`
- `notification_variants.complete.message`
- `notification_variants.question.subtitle`
- `notification_variants.question.message`
- `notification_variants.permission.subtitle`
- `notification_variants.permission.message`
- `notification_variants.input.subtitle`
- `notification_variants.input.message`
- `notification_variants.error.subtitle`
- `notification_variants.error.message`
- `claude.stop_message`
- `cursor.stop_message`
- `cursor.question_message`
- `opencode.stop_message`
- `codex.stop_message`

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

Existing installs must continue to work without manual migration.

Compatibility expectations:

- old `config.json` files that already contain Chinese default copy remain readable
- customized user copy continues to override runtime defaults
- fresh installs should not write every localized message into `config.json`
- upgrades should remove only legacy default copy values that still exactly match old installer defaults
- a missing or partially customized config file should still produce localized notifications

This means localization becomes a runtime concern, while `config.json` becomes primarily a place for user preferences and optional overrides.

### 6. Localized Copy Catalog

The localized catalog should be explicit and fixed for this iteration so runtime expectations and tests are stable.

Shared-variant keys:

- `notification_variants.complete.subtitle`
- `notification_variants.complete.message`
- `notification_variants.question.subtitle`
- `notification_variants.question.message`
- `notification_variants.permission.subtitle`
- `notification_variants.permission.message`
- `notification_variants.input.subtitle`
- `notification_variants.input.message`
- `notification_variants.error.subtitle`
- `notification_variants.error.message`

Client-specific fallback behavior:

- `claude.stop_message` reuses `notification_variants.complete.message`
- `codex.stop_message` reuses `notification_variants.complete.message`
- `cursor.question_message` reuses `notification_variants.question.message`
- `cursor.stop_message` has its own localized string
- `opencode.stop_message` has its own localized string
- client titles remain product names and are not localized in this iteration

Catalog values:

```text
zh
  complete.subtitle = 执行完成
  complete.message = 任务已完成，等待你查看结果。
  question.subtitle = 等待回答
  question.message = Agent 正在等待你的回答。
  permission.subtitle = 等待授权
  permission.message = Agent 正在等待你的权限确认。
  input.subtitle = 需要补充信息
  input.message = Agent 需要你补充更多信息。
  error.subtitle = 执行出错
  error.message = 运行过程中发生错误，请打开界面查看。
  cursor.stop_message = Agent 已执行完毕，等待你查看结果。
  opencode.stop_message = 会话已进入空闲状态，等待你查看结果。

ja
  complete.subtitle = 完了
  complete.message = タスクが完了しました。結果を確認してください。
  question.subtitle = 回答待ち
  question.message = Agent があなたの回答を待っています。
  permission.subtitle = 許可待ち
  permission.message = Agent が権限の確認を待っています。
  input.subtitle = 追加情報が必要
  input.message = Agent は追加の情報を必要としています。
  error.subtitle = エラー
  error.message = 実行中にエラーが発生しました。詳細はアプリで確認してください。
  cursor.stop_message = Agent の実行が完了しました。結果を確認してください。
  opencode.stop_message = セッションはアイドル状態です。結果を確認してください。

en
  complete.subtitle = Completed
  complete.message = The task is complete. Open the app to review the result.
  question.subtitle = Awaiting Reply
  question.message = The agent is waiting for your reply.
  permission.subtitle = Awaiting Permission
  permission.message = The agent is waiting for your permission.
  input.subtitle = More Information Needed
  input.message = The agent needs more information from you.
  error.subtitle = Error
  error.message = Something went wrong during execution. Open the app for details.
  cursor.stop_message = The agent has finished running. Open the app to review the result.
  opencode.stop_message = The session is idle. Open the app to review the result.

fr
  complete.subtitle = Terminé
  complete.message = La tâche est terminée. Ouvrez l'application pour voir le résultat.
  question.subtitle = Réponse attendue
  question.message = L'agent attend votre réponse.
  permission.subtitle = Autorisation requise
  permission.message = L'agent attend votre autorisation.
  input.subtitle = Informations requises
  input.message = L'agent a besoin d'informations supplémentaires.
  error.subtitle = Erreur
  error.message = Une erreur s'est produite pendant l'exécution. Ouvrez l'application pour voir les détails.
  cursor.stop_message = L'agent a terminé son exécution. Ouvrez l'application pour voir le résultat.
  opencode.stop_message = La session est inactive. Ouvrez l'application pour voir le résultat.

de
  complete.subtitle = Abgeschlossen
  complete.message = Die Aufgabe ist abgeschlossen. Öffnen Sie die App, um das Ergebnis zu prüfen.
  question.subtitle = Antwort ausstehend
  question.message = Der Agent wartet auf Ihre Antwort.
  permission.subtitle = Berechtigung erforderlich
  permission.message = Der Agent wartet auf Ihre Bestätigung.
  input.subtitle = Weitere Angaben nötig
  input.message = Der Agent benötigt weitere Informationen.
  error.subtitle = Fehler
  error.message = Während der Ausführung ist ein Fehler aufgetreten. Öffnen Sie die App für Details.
  cursor.stop_message = Der Agent ist fertig. Öffnen Sie die App, um das Ergebnis zu prüfen.
  opencode.stop_message = Die Sitzung ist im Leerlauf. Öffnen Sie die App, um das Ergebnis zu prüfen.

es
  complete.subtitle = Completado
  complete.message = La tarea ha terminado. Abre la aplicación para revisar el resultado.
  question.subtitle = Respuesta pendiente
  question.message = El agente está esperando tu respuesta.
  permission.subtitle = Permiso pendiente
  permission.message = El agente está esperando tu autorización.
  input.subtitle = Se necesita más información
  input.message = El agente necesita más información de tu parte.
  error.subtitle = Error
  error.message = Se produjo un error durante la ejecución. Abre la aplicación para ver los detalles.
  cursor.stop_message = El agente terminó de ejecutarse. Abre la aplicación para revisar el resultado.
  opencode.stop_message = La sesión está inactiva. Abre la aplicación para revisar el resultado.

ru
  complete.subtitle = Готово
  complete.message = Задача завершена. Откройте приложение, чтобы посмотреть результат.
  question.subtitle = Ожидается ответ
  question.message = Агент ждет вашего ответа.
  permission.subtitle = Требуется разрешение
  permission.message = Агент ждет вашего подтверждения.
  input.subtitle = Нужна дополнительная информация
  input.message = Агенту нужна дополнительная информация.
  error.subtitle = Ошибка
  error.message = Во время выполнения произошла ошибка. Откройте приложение, чтобы посмотреть подробности.
  cursor.stop_message = Агент завершил работу. Откройте приложение, чтобы посмотреть результат.
  opencode.stop_message = Сессия перешла в режим ожидания. Откройте приложение, чтобы посмотреть результат.

ko
  complete.subtitle = 완료됨
  complete.message = 작업이 완료되었습니다. 결과를 확인해 주세요.
  question.subtitle = 답변 대기 중
  question.message = Agent가 답변을 기다리고 있습니다.
  permission.subtitle = 권한 대기 중
  permission.message = Agent가 권한 확인을 기다리고 있습니다.
  input.subtitle = 추가 정보 필요
  input.message = Agent가 더 많은 정보를 필요로 합니다.
  error.subtitle = 오류
  error.message = 실행 중 오류가 발생했습니다. 자세한 내용은 앱에서 확인해 주세요.
  cursor.stop_message = Agent 실행이 완료되었습니다. 결과를 확인해 주세요.
  opencode.stop_message = 세션이 유휴 상태입니다. 결과를 확인해 주세요.
```

### 7. Testing Strategy

Runtime coverage in [test_notify_runtime.py](/Users/wty/agent-notify/tests/test_notify_runtime.py) should verify:

- Chinese system language resolves to Chinese notification copy
- Japanese system language resolves to Japanese notification copy
- French system language resolves to French notification copy
- unsupported system language falls back to English
- explicit config overrides beat the system-language defaults
- exact assertions are anchored to the catalog above rather than approximate translations

Language detection tests should be stable and not rely on the real host language. They should simulate macOS language lookup by controlling the lookup command or environment inside the test process.

Concrete assertions should include at least:

- `zh-Hans` -> `complete.subtitle == "执行完成"`
- `ja-JP` -> `complete.subtitle == "完了"`
- `fr-CA` -> `complete.subtitle == "Terminé"`
- `de-DE` -> `complete.subtitle == "Abgeschlossen"`
- `es-ES` -> `complete.subtitle == "Completado"`
- `ru-RU` -> `complete.subtitle == "Готово"`
- `ko-KR` -> `complete.subtitle == "완료됨"`
- `pt-BR` -> `complete.subtitle == "Completed"`

Installer coverage in [test_install_cli.py](/Users/wty/agent-notify/tests/test_install_cli.py) should verify:

- upgrade keeps existing custom overrides in `config.json`
- upgrade still writes non-language defaults that are required for runtime behavior
- installer no longer depends on shipping the full localized notification copy inside default config data
- upgrade removes only legacy default copy values that still exactly match old installer defaults

### 8. Documentation Refresh

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
