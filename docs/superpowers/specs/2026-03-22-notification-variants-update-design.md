# Notification Variants And Update Flow Design

**Date:** 2026-03-22

**Goal:** Improve notification differentiation for question-like events and add an explicit in-place update path for installed clients.

## Confirmed Requirements

- Notification presentation should be more expressive over time.
- The long-term direction is a centralized notification variant table instead of per-client ad hoc titles and messages.
- Installer must support `./install.sh update`.
- Update must preserve the user's enabled clients.
- Update must preserve existing config values and only add newly introduced defaults.

## Design

### 1. Unified Notification Variants

Runtime notification handling is split into two phases:

- event normalization: each client maps its native events into a shared variant key
- rendering: one centralized variant table provides subtitle and default message

Shared variants:

- `complete`
- `question`
- `permission`
- `input`
- `error`

The title remains client-specific, such as `Claude Code`, `Cursor`, or `OpenCode`. Subtitle and fallback message come from the shared variant definition.

### 2. Client Event Mapping

- Claude:
  - `Stop`, `SubagentStop` -> `complete`
  - `Notification(permission_prompt)` -> `permission`
  - `Notification(idle_prompt)` -> `input`
  - `Notification(elicitation_dialog)` -> `question`
  - `Elicitation` -> `question`
- Cursor:
  - `afterAgentResponse` with question-pattern hit -> `question`
  - `stop` with completed status -> `complete`
- OpenCode:
  - `permission.asked` -> `permission`
  - `session.error` -> `error`
  - `session.idle` -> `complete`

### 3. Config Evolution

Default config gains a `notification_variants` section. Upgrade behavior merges missing defaults recursively into the existing config file while preserving user overrides.

### 4. Update Command

New commands:

- `./install.sh update`
- `python3 scripts/install.py --update-installed`

Behavior:

- detect currently installed supported clients
- fail with a clear message if none are installed
- refresh runtime files
- merge in new config defaults
- reinstall hooks/plugins for the already enabled clients only
- do not enable additional clients automatically

## Testing Strategy

- runtime tests for normalized question, permission, input, error, and complete variants
- install CLI tests for `--update-installed`
- shell entrypoint test for `./install.sh update`
- config merge test proving new defaults are added without overwriting existing values
