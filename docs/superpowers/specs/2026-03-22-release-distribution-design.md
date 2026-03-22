# Release Distribution Design

**Date:** 2026-03-22

**Goal:** Provide GitHub Release based distribution for `agent-notify`, with both a versioned source package and a direct install script.

## Confirmed Requirements

- Use GitHub Release as the public delivery channel.
- Publish two release assets:
  - `agent-notify-${version}.tar.gz`
  - `install-release.sh`
- The install script must support exact versions only.
- Version format is constrained to Git tags like `v0.1.0`.
- Automatic release creation should happen from GitHub Actions.

## Design

### Versioning

- Release tags use semantic version tags with a leading `v`.
- Supported examples:
  - `v0.1.0`
  - `v0.1.1`
- Unsupported forms:
  - `latest`
  - `v0.1.x`
  - `^0.1`
  - `>=0.1.0 <0.2.0`

### Release Assets

`agent-notify-${version}.tar.gz` contains a versioned top-level directory and only the files required for installation:

- `install.sh`
- `install-release.sh`
- `hooks/`
- `scripts/`
- `plugins/`
- `README.md`
- `LICENSE`

`install-release.sh` is a thin downloader:

- validates the exact version tag
- downloads the matching tarball from GitHub Releases
- extracts it to a temporary directory
- runs the packaged `install.sh`
- forwards remaining arguments to `install.sh`

### Automation

GitHub Actions will:

- trigger on pushed tags matching `v*`
- optionally support manual re-run via `workflow_dispatch`
- run the test suite before release publication
- build the tarball asset from the tagged source
- create the release if missing, or upload refreshed assets if it already exists

## Testing Strategy

- Unit/integration test the release tarball builder:
  - accepts exact tags
  - rejects invalid version strings
  - produces the expected archive layout
- Test the release installer wrapper:
  - rejects missing/invalid versions
  - downloads the requested exact-version archive
  - forwards arguments to the packaged installer

## Non-Goals For This Iteration

- version range resolution
- automatic changelog generation policy
- Homebrew packaging
- checksums, signatures, notarization
