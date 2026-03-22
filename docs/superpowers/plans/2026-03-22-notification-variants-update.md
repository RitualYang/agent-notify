# Notification Variants And Update Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add centralized notification variants and an explicit update flow that upgrades installed clients without resetting user config.

**Architecture:** `hooks/notify.py` will normalize client events into shared variant keys and then render through a central variant table sourced from config defaults. `scripts/install.py` and `install.sh` will gain an update mode that detects currently installed clients, refreshes runtime files, merges new config defaults, and reapplies their hooks/plugins.

**Tech Stack:** Python 3, Bash, `unittest`

---

### Task 1: Write Failing Runtime Tests

**Files:**
- Modify: `tests/test_notify_runtime.py`

- [ ] **Step 1: Add a failing test for Claude permission notification**

Assert a Claude `Notification` with `notification_type=permission_prompt` renders subtitle `等待授权`.

- [ ] **Step 2: Add a failing test for Claude elicitation/question notification**

Assert a Claude `Elicitation` event renders subtitle `等待回答`.

- [ ] **Step 3: Add a failing test for OpenCode error notification**

Assert `session.error` renders subtitle `执行出错`.

- [ ] **Step 4: Run the focused runtime tests to verify failure**

Run:

```bash
python3 -m unittest tests.test_notify_runtime.NotifyRuntimeTests.test_claude_permission_notification_uses_permission_variant -v
python3 -m unittest tests.test_notify_runtime.NotifyRuntimeTests.test_claude_elicitation_uses_question_variant -v
python3 -m unittest tests.test_notify_runtime.NotifyRuntimeTests.test_opencode_error_uses_error_variant -v
```

Expected: FAIL against current static subtitles.

### Task 2: Write Failing Update Tests

**Files:**
- Modify: `tests/test_install_cli.py`
- Modify: `scripts/providers.py`

- [ ] **Step 1: Add a failing test for `--update-installed`**

Create an installed Claude runtime and settings, then assert `scripts/install.py --update-installed ...` succeeds and reports `Enabled clients: claude`.

- [ ] **Step 2: Add a failing test for missing installed clients**

Assert `scripts/install.py --update-installed ...` returns non-zero with a clear install-first message.

- [ ] **Step 3: Add a failing test for config merge**

Pre-create `config.json` with a customized cursor question message and assert update adds `notification_variants` without overwriting the custom value.

- [ ] **Step 4: Run focused install tests to verify failure**

Run:

```bash
python3 -m unittest tests.test_install_cli.InstallCliTests.test_update_installed_refreshes_existing_client -v
python3 -m unittest tests.test_install_cli.InstallCliTests.test_update_installed_requires_existing_installation -v
python3 -m unittest tests.test_install_cli.InstallCliTests.test_update_installed_merges_new_config_defaults -v
```

Expected: FAIL because update mode does not exist yet.

### Task 3: Implement Unified Notification Variants

**Files:**
- Modify: `hooks/notify.py`

- [ ] **Step 1: Add centralized default variant definitions**
- [ ] **Step 2: Normalize per-client events into shared variant keys**
- [ ] **Step 3: Render title/subtitle/message from the shared variant table**
- [ ] **Step 4: Re-run the focused runtime tests**

### Task 4: Implement Update Flow

**Files:**
- Modify: `scripts/providers.py`
- Modify: `scripts/install.py`
- Modify: `install.sh`

- [ ] **Step 1: Add recursive config-default merge helper**
- [ ] **Step 2: Add `--update-installed` behavior to `scripts/install.py`**
- [ ] **Step 3: Add `update` passthrough support to `install.sh`**
- [ ] **Step 4: Re-run the focused install tests**

### Task 5: Document And Verify

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document `./install.sh update`**
- [ ] **Step 2: Document that updates preserve current enabled clients and existing config**
- [ ] **Step 3: Run full verification**

Run:

```bash
python3 -m unittest discover -s tests -v
git status --short
```

Expected: tests pass and only intended tracked file changes remain.
