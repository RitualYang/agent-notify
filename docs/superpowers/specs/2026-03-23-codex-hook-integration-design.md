# Codex Hook Integration Design

**Date:** 2026-03-23

**Goal:** Add installable Codex notification support to `agent-notify`, with stable completion notifications and best-effort experimental classification for question, permission, input, and error states on supported Codex CLI versions.

## Confirmed Requirements

- `codex` should move from a reserved provider to an installable provider.
- `scripts/install.py` must be able to install and uninstall Codex integration.
- `hooks/notify.py` must recognize Codex events and map them into the existing shared notification variants:
  - `complete`
  - `question`
  - `permission`
  - `input`
  - `error`
- Stable support is required for completion notifications.
- Additional Codex classifications beyond completion may use experimental hooks as a best-effort path.
- Experimental hook installation must be gated to Codex CLI versions `0.114.x` through `0.116.x`.
- If experimental integration is unavailable or incompatible, installation must fall back to stable completion-only behavior instead of failing hard.
- Codex config edits must be non-destructive and only remove `agent-notify` owned entries on uninstall.

## Design

### 1. Support Tier Model

Codex support is split into two tiers:

- stable tier:
  - install a Codex `notify` callback through `~/.codex/config.toml`
  - use it for completion notifications only
- experimental tier:
  - additionally install Codex hook configuration
  - enable `codex_hooks` in Codex config
  - use the `Stop` hook payload plus transcript inspection to infer `permission`, `question`, `input`, and `error`

This keeps the minimum supported experience reliable while allowing richer notifications on the verified Codex versions.

### 2. Installation Architecture

Codex installation extends the existing provider architecture in [providers.py](/Users/wty/agent-notify/scripts/providers.py) rather than adding a one-off path.

New Codex-specific installation targets:

- `~/.codex/config.toml`
- `~/.codex/hooks.json`

The provider should:

- treat Codex as supported, but mark richer hook-based behavior as experimental in user-facing notes
- add a Codex config path argument to [install.py](/Users/wty/agent-notify/scripts/install.py)
- detect the installed Codex CLI version before writing experimental hook configuration
- only enable experimental hook config when the detected version is within `0.114.x` to `0.116.x`
- always install the stable `notify` callback when Codex is selected

Config writes must be merge-based, not overwrite-based:

- preserve unrelated user config in `config.toml`
- preserve unrelated user hook entries in `hooks.json`
- tag all `agent-notify` owned entries so uninstall can remove only those entries

### 3. Runtime Entry Paths

Codex events reach the runtime through two paths:

1. Stable notify path
   - Codex invokes the configured notify command for completion-oriented notifications
   - `notify.py` must accept Codex payloads in addition to the existing stdin-driven clients

2. Experimental hook path
   - Codex invokes a `Stop` hook command with structured payload data
   - the payload includes Codex context such as `cwd`, `transcript_path`, `turn_id`, and `last_assistant_message`
   - `notify.py` uses `transcript_path` to inspect recent Codex session events and classify the stop reason

To support both paths, [notify.py](/Users/wty/agent-notify/hooks/notify.py) should accept input from either:

- stdin JSON
- a final CLI argument containing serialized JSON payload

The runtime should normalize both into one internal Codex payload shape before classification.

### 4. Codex Event Normalization

Codex maps into the shared variant table using the following rules.

Stable path:

- notify payload for turn completion -> `complete`

Experimental `Stop` hook path:

- transcript contains `task_complete` -> `complete`
- transcript contains `exec_approval_request` or `apply_patch_approval_request` -> `permission`
- transcript contains `elicitation_request` -> `question`
- transcript contains `request_user_input` -> `input`
- transcript contains `stream_error` -> `error`

Classification should inspect only a small recent suffix of the transcript so runtime cost stays bounded.

Project name resolution for Codex should use:

- payload `cwd` when present
- process cwd as a fallback

The rendered title should default to `Codex`, while subtitle and fallback message continue to come from the shared `notification_variants` table already used by the other clients.

### 5. Failure Handling And Fallback

Codex support must degrade safely.

Installation-time fallback:

- if `codex` is not installed or version detection fails, print a note and install only the stable completion path when possible
- if the version is outside `0.114.x` to `0.116.x`, skip experimental hook config and keep stable completion notifications only
- if hook config merge fails, do not block stable notify installation

Runtime fallback:

- if transcript data is missing, unreadable, or unrecognized, do not guess a non-complete notification
- when an experimental classification cannot be made, emit no notification unless the stable path explicitly indicates completion
- avoid heuristic text parsing for Codex beyond the transcript event names to reduce false positives

This ensures upstream Codex changes degrade the experience to completion-only rather than causing noisy or broken notifications.

### 6. User-Facing Positioning

README should describe Codex support explicitly as two-tiered:

- completion reminders: stable
- question, permission, input, and error reminders: experimental, verified against Codex CLI `0.114.x` to `0.116.x`

Documentation should also state:

- which files are written for Codex
- that unsupported versions fall back to completion-only behavior
- that uninstall removes only `agent-notify` owned Codex entries
- that richer classification depends on Codex experimental hooks and transcript event names, so it may regress if Codex changes upstream behavior

## Testing Strategy

- Runtime tests in [test_notify_runtime.py](/Users/wty/agent-notify/tests/test_notify_runtime.py):
  - stable Codex completion payload -> `complete`
  - experimental transcript classification for `permission`
  - experimental transcript classification for `question`
  - experimental transcript classification for `input`
  - experimental transcript classification for `error`
  - missing or unreadable transcript falls back safely
- Install CLI tests in [test_install_cli.py](/Users/wty/agent-notify/tests/test_install_cli.py):
  - Codex install writes owned config entries
  - repeated install is idempotent
  - uninstall removes only owned Codex entries
  - unsupported Codex versions skip experimental hooks and keep stable notify only
  - installed-client detection recognizes Codex
- Integration-style tests should use temporary Codex config and transcript files instead of the real `~/.codex` tree.

## Non-Goals For This Iteration

- supporting all Codex hook event types
- relying on undocumented agent hooks or prompt hooks
- making unsupported Codex versions fail open for experimental classification
- introducing a separate Codex-only notification renderer
