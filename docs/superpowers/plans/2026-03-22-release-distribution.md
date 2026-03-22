# Release Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add GitHub Release automation with a versioned archive and an exact-version installer entrypoint.

**Architecture:** A Python release builder creates a deterministic tarball from the repository tree. A shell installer downloads the tarball for an exact Git tag and runs the packaged installer. A GitHub Actions workflow runs tests, builds assets, and creates or updates the matching release.

**Tech Stack:** Python 3, POSIX shell, GitHub Actions, `gh` CLI on Actions runners, `unittest`

---

### Task 1: Release Builder Tests

**Files:**
- Create: `tests/test_release_distribution.py`
- Modify: `tests/test_install_cli.py` (only if shared helpers become necessary)

- [ ] **Step 1: Write a failing test for archive creation**

Write a test that runs:

```bash
python3 scripts/build_release.py --version v0.1.0 --output-dir <tmp>
```

and asserts the archive exists and contains:

- `agent-notify-v0.1.0/install.sh`
- `agent-notify-v0.1.0/install-release.sh`
- `agent-notify-v0.1.0/scripts/install.py`
- `agent-notify-v0.1.0/hooks/notify.py`
- `agent-notify-v0.1.0/plugins/opencode/agent-notify.js.template`

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_release_distribution.ReleaseDistributionTests.test_build_release_creates_expected_archive -v
```

Expected: FAIL because `scripts/build_release.py` does not exist yet.

- [ ] **Step 3: Write a failing test for version validation**

Write a test asserting:

```bash
python3 scripts/build_release.py --version 0.1.0 --output-dir <tmp>
```

returns a non-zero exit code and mentions exact `vX.Y.Z` tags.

- [ ] **Step 4: Run the focused validation test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_release_distribution.ReleaseDistributionTests.test_build_release_requires_exact_version_tag -v
```

Expected: FAIL because the builder does not exist yet.

### Task 2: Release Installer Tests

**Files:**
- Create: `tests/test_release_distribution.py`
- Create: `install-release.sh`

- [ ] **Step 1: Write a failing test for installer delegation**

Create a fake release archive under a temporary `v0.1.0/` directory with a stub `install.sh`, then assert:

```bash
./install-release.sh v0.1.0 --flag demo
```

downloads the archive and forwards `--flag demo` to the stub installer.

- [ ] **Step 2: Run the focused installer test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_release_distribution.ReleaseDistributionTests.test_install_release_downloads_exact_version_archive_and_runs_installer -v
```

Expected: FAIL because `install-release.sh` does not exist yet.

- [ ] **Step 3: Write a failing test for exact-version enforcement**

Assert:

```bash
./install-release.sh latest
```

returns a non-zero exit code and mentions exact versions.

- [ ] **Step 4: Run the focused validation test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_release_distribution.ReleaseDistributionTests.test_install_release_requires_exact_version_tag -v
```

Expected: FAIL because the installer script does not exist yet.

### Task 3: Implement Release Tooling

**Files:**
- Create: `scripts/build_release.py`
- Create: `install-release.sh`

- [ ] **Step 1: Implement `scripts/build_release.py`**

Use Python to:

- validate `--version` with `^v\d+\.\d+\.\d+$`
- build `dist/agent-notify-${version}.tar.gz`
- archive only install-time files under `agent-notify-${version}/`

- [ ] **Step 2: Run focused builder tests**

Run:

```bash
python3 -m unittest tests.test_release_distribution.ReleaseDistributionTests.test_build_release_creates_expected_archive -v
python3 -m unittest tests.test_release_distribution.ReleaseDistributionTests.test_build_release_requires_exact_version_tag -v
```

Expected: PASS

- [ ] **Step 3: Implement `install-release.sh`**

Use shell to:

- require an exact version argument
- build the GitHub release asset URL
- download and extract the matching tarball
- run packaged `install.sh` with forwarded arguments

- [ ] **Step 4: Run focused installer tests**

Run:

```bash
python3 -m unittest tests.test_release_distribution.ReleaseDistributionTests.test_install_release_downloads_exact_version_archive_and_runs_installer -v
python3 -m unittest tests.test_release_distribution.ReleaseDistributionTests.test_install_release_requires_exact_version_tag -v
```

Expected: PASS

### Task 4: Automate GitHub Release Publishing

**Files:**
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Add the workflow**

Implement a workflow that:

- triggers on `push.tags: ['v*']`
- supports `workflow_dispatch` with a `version` input
- runs `python3 -m unittest discover -s tests -v`
- runs `python3 scripts/build_release.py --version "$VERSION" --output-dir dist`
- creates or updates the matching GitHub Release with both assets

- [ ] **Step 2: Verify workflow YAML locally**

Run:

```bash
sed -n '1,240p' .github/workflows/release.yml
```

Expected: valid-looking workflow with correct triggers, permissions, and asset upload commands.

### Task 5: Document Release Usage

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add release install instructions**

Document:

- download tarball from a tagged release and run `install.sh`
- use `install-release.sh` with an exact version

- [ ] **Step 2: Add release publishing instructions**

Document:

```bash
git tag v0.1.0
git push origin v0.1.0
```

and explain that GitHub Actions will run tests, build assets, and create or refresh the release.

- [ ] **Step 3: Run full verification**

Run:

```bash
python3 -m unittest discover -s tests -v
git status --short
```

Expected: tests pass and only intended tracked file changes remain.
