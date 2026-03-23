# Codex Hook Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add installable Codex support with stable completion notifications and best-effort experimental classification for permission, question, input, and error states on verified Codex CLI versions.

**Architecture:** Extend the existing provider layer so Codex is installed and detected like the other clients, while keeping its richer behavior behind a version-gated experimental path. Update the runtime to accept Codex payloads from both stable notify callbacks and experimental stop hooks, then normalize them into the existing shared notification variants through bounded transcript inspection.

**Tech Stack:** Python 3, Bash, `unittest`, Git

---

### File Structure

**Existing files to modify**

- [scripts/providers.py](/Users/wty/agent-notify/scripts/providers.py)
  Responsible for provider registration, install/uninstall logic, config defaults, runtime copy, and installed-client detection.
- [scripts/install.py](/Users/wty/agent-notify/scripts/install.py)
  Responsible for CLI wiring, CLI arguments, update mode, and status output.
- [install.sh](/Users/wty/agent-notify/install.sh)
  Responsible for interactive selection labels, numeric shortcuts, and forwarding to `scripts/install.py`.
- [hooks/notify.py](/Users/wty/agent-notify/hooks/notify.py)
  Responsible for reading hook payloads, detecting client type, mapping events to notification variants, and rendering dry-run output.
- [tests/test_notify_runtime.py](/Users/wty/agent-notify/tests/test_notify_runtime.py)
  Runtime-level verification for payload parsing and variant classification.
- [tests/test_install_cli.py](/Users/wty/agent-notify/tests/test_install_cli.py)
  Installer-level verification for config writes, detection, update mode, and shell wrapper behavior.
- [README.md](/Users/wty/agent-notify/README.md)
  User-facing install/config/support documentation.

**No new production modules are required**

- Keep Codex support inside the current provider/runtime structure.
- Add helper functions within existing files unless a function becomes too large to reason about.

### Task 1: Add Failing Codex Runtime Tests

**Files:**
- Modify: [tests/test_notify_runtime.py](/Users/wty/agent-notify/tests/test_notify_runtime.py)

- [ ] **Step 1: Add a stable Codex completion dry-run test**

Add a test that runs `notify.py --dry-run --client codex` with a Codex completion payload and asserts:

```python
self.assertEqual(output["notification"]["kind"], "complete")
self.assertEqual(output["notification"]["title"], "Codex")
```

- [ ] **Step 2: Add a Codex transcript-based permission test**

Create a temporary transcript JSONL file containing a recent `event_msg` with `payload.type == "exec_approval_request"`, then assert the dry-run output uses:

```python
self.assertEqual(output["notification"]["kind"], "permission")
```

- [ ] **Step 3: Add Codex transcript-based question, input, and error tests**

Add separate tests for:

```python
"elicitation_request" -> "question"
"request_user_input" -> "input"
"stream_error" -> "error"
```

- [ ] **Step 4: Add a safe-fallback transcript test**

Add a test where `transcript_path` is missing or unreadable and assert the runtime does not emit an inferred non-complete notification.

- [ ] **Step 5: Run the focused runtime tests to verify failure**

Run:

```bash
python3 -m unittest tests.test_notify_runtime.NotifyRuntimeTests.test_codex_completion_notification_uses_complete_variant -v
python3 -m unittest tests.test_notify_runtime.NotifyRuntimeTests.test_codex_transcript_exec_approval_maps_to_permission -v
python3 -m unittest tests.test_notify_runtime.NotifyRuntimeTests.test_codex_transcript_elicitation_maps_to_question -v
python3 -m unittest tests.test_notify_runtime.NotifyRuntimeTests.test_codex_transcript_request_user_input_maps_to_input -v
python3 -m unittest tests.test_notify_runtime.NotifyRuntimeTests.test_codex_transcript_stream_error_maps_to_error -v
python3 -m unittest tests.test_notify_runtime.NotifyRuntimeTests.test_codex_missing_transcript_falls_back_safely -v
```

Expected: FAIL because Codex is not yet accepted as a client and no Codex classifier exists.

- [ ] **Step 6: Commit the failing tests**

```bash
git add tests/test_notify_runtime.py
git commit -m "test: add failing Codex runtime coverage"
```

### Task 2: Add Failing Codex Installer Tests

**Files:**
- Modify: [tests/test_install_cli.py](/Users/wty/agent-notify/tests/test_install_cli.py)

- [ ] **Step 1: Add a helper for temporary Codex config files**

Add test helpers that create:

```python
codex_config = temp_root / ".codex" / "config.toml"
codex_hooks = temp_root / ".codex" / "hooks.json"
```

- [ ] **Step 2: Add an install test for Codex stable config writes**

Assert `scripts/install.py --client codex ...` writes an `agent-notify` owned stable notify entry without touching unrelated config keys.

- [ ] **Step 3: Add a version-gating test**

Patch the version detection helper so the installer sees an unsupported Codex version and assert:

```python
self.assertIn("completion-only", result.stdout or result.stderr)
```

and that experimental hook config is skipped.

- [ ] **Step 4: Add an uninstall-preserves-foreign-config test**

Preload foreign Codex config and hook entries, uninstall Codex, and assert only `agent-notify` owned entries are removed.

- [ ] **Step 5: Add an installed-client detection test for Codex**

Assert `--print-installed` or direct provider detection includes `codex` when the owned stable notify entry exists.

- [ ] **Step 6: Run the focused installer tests to verify failure**

Run:

```bash
python3 -m unittest tests.test_install_cli.InstallCliTests.test_install_codex_writes_stable_notify_config -v
python3 -m unittest tests.test_install_cli.InstallCliTests.test_install_codex_unsupported_version_skips_experimental_hooks -v
python3 -m unittest tests.test_install_cli.InstallCliTests.test_uninstall_codex_preserves_foreign_config -v
python3 -m unittest tests.test_install_cli.InstallCliTests.test_print_installed_includes_codex_when_config_exists -v
```

Expected: FAIL because the installer has no Codex config arguments or provider implementation.

- [ ] **Step 7: Commit the failing installer tests**

```bash
git add tests/test_install_cli.py
git commit -m "test: add failing Codex installer coverage"
```

### Task 3: Implement Codex Provider And Installer Wiring

**Files:**
- Modify: [scripts/providers.py](/Users/wty/agent-notify/scripts/providers.py)
- Modify: [scripts/install.py](/Users/wty/agent-notify/scripts/install.py)
- Modify: [install.sh](/Users/wty/agent-notify/install.sh)

- [ ] **Step 1: Add Codex default paths and supported-provider metadata**

Add defaults for:

```python
DEFAULT_CODEX_CONFIG = Path(os.path.expanduser("~/.codex/config.toml"))
DEFAULT_CODEX_HOOKS = Path(os.path.expanduser("~/.codex/hooks.json"))
```

Update provider metadata so Codex is installable and marked experimental in notes rather than unsupported.

- [ ] **Step 2: Add Codex CLI version detection helper**

Add a helper in `providers.py` that runs:

```python
subprocess.run(["codex", "--version"], ...)
```

and parses `codex-cli X.Y.Z` into a comparable version tuple.

- [ ] **Step 3: Add merge/remove helpers for Codex config ownership**

Implement focused helpers that:

- load and update `config.toml`
- load and update `hooks.json`
- mark `agent-notify` owned entries
- remove only owned entries during uninstall

- [ ] **Step 4: Add Codex install, uninstall, and detection paths**

Update:

```python
is_*_installed(...)
get_installed_clients(...)
get_interactive_default_clients(...)
install_provider(...)
uninstall_provider(...)
```

so Codex behaves like the other clients.

- [ ] **Step 5: Wire Codex CLI arguments through install.py**

Add:

```python
parser.add_argument("--codex-config", ...)
parser.add_argument("--codex-hooks", ...)
```

and pass both through every provider call.

- [ ] **Step 6: Update install.sh selection UX**

Add `codex` to:

- usage text
- numeric selection mapping
- interactive menu labeling

without breaking the existing `claude/cursor/opencode` order.

- [ ] **Step 7: Run the focused installer tests**

Run:

```bash
python3 -m unittest tests.test_install_cli.InstallCliTests.test_install_codex_writes_stable_notify_config -v
python3 -m unittest tests.test_install_cli.InstallCliTests.test_install_codex_unsupported_version_skips_experimental_hooks -v
python3 -m unittest tests.test_install_cli.InstallCliTests.test_uninstall_codex_preserves_foreign_config -v
python3 -m unittest tests.test_install_cli.InstallCliTests.test_print_installed_includes_codex_when_config_exists -v
```

Expected: PASS

- [ ] **Step 8: Commit the provider and installer implementation**

```bash
git add scripts/providers.py scripts/install.py install.sh tests/test_install_cli.py
git commit -m "feat: add Codex provider installation"
```

### Task 4: Implement Codex Runtime Classification

**Files:**
- Modify: [hooks/notify.py](/Users/wty/agent-notify/hooks/notify.py)
- Modify: [tests/test_notify_runtime.py](/Users/wty/agent-notify/tests/test_notify_runtime.py)

- [ ] **Step 1: Extend runtime argument parsing for Codex**

Update the CLI parser so `--client` accepts `codex` and add input parsing that supports either:

```python
stdin JSON
final positional JSON payload for Codex notify callbacks
```

- [ ] **Step 2: Add Codex project-name resolution**

Extend project-name inference to prefer:

```python
payload["cwd"]
os.getcwd()
```

when the client is `codex`.

- [ ] **Step 3: Add transcript-inspection helpers**

Add focused helpers that:

- open `transcript_path`
- read only a bounded recent suffix
- scan recent `event_msg.payload.type`
- return the most relevant Codex variant

- [ ] **Step 4: Add Codex classifier and safe fallback behavior**

Implement classification logic so:

```python
completion notify -> complete
exec_approval_request/apply_patch_approval_request -> permission
elicitation_request -> question
request_user_input -> input
stream_error -> error
unknown or unreadable transcript -> no-op unless completion is explicit
```

- [ ] **Step 5: Run the focused runtime tests**

Run:

```bash
python3 -m unittest tests.test_notify_runtime.NotifyRuntimeTests.test_codex_completion_notification_uses_complete_variant -v
python3 -m unittest tests.test_notify_runtime.NotifyRuntimeTests.test_codex_transcript_exec_approval_maps_to_permission -v
python3 -m unittest tests.test_notify_runtime.NotifyRuntimeTests.test_codex_transcript_elicitation_maps_to_question -v
python3 -m unittest tests.test_notify_runtime.NotifyRuntimeTests.test_codex_transcript_request_user_input_maps_to_input -v
python3 -m unittest tests.test_notify_runtime.NotifyRuntimeTests.test_codex_transcript_stream_error_maps_to_error -v
python3 -m unittest tests.test_notify_runtime.NotifyRuntimeTests.test_codex_missing_transcript_falls_back_safely -v
```

Expected: PASS

- [ ] **Step 6: Commit the runtime implementation**

```bash
git add hooks/notify.py tests/test_notify_runtime.py
git commit -m "feat: classify Codex notifications"
```

### Task 5: Document Codex Support And Verify End-To-End

**Files:**
- Modify: [README.md](/Users/wty/agent-notify/README.md)

- [ ] **Step 1: Document Codex support scope**

Update support and notes sections to state:

- completion reminders are stable
- question, permission, input, and error are experimental
- experimental verification is limited to `0.114.x` through `0.116.x`

- [ ] **Step 2: Document Codex write locations and fallback behavior**

Add:

- `~/.codex/config.toml`
- `~/.codex/hooks.json`
- unsupported versions fall back to completion-only

- [ ] **Step 3: Run the full automated verification suite**

Run:

```bash
python3 -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 4: Inspect the resulting worktree state**

Run:

```bash
git status --short
```

Expected: only intended tracked file changes remain.

- [ ] **Step 5: Commit documentation and final adjustments**

```bash
git add README.md
git commit -m "docs: document Codex notification support"
```
