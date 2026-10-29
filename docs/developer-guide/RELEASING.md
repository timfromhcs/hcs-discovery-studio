# Releasing

Releases are built and published by `.github/workflows/release.yml` from a pushed
tag. The workflow refuses to publish unless the tagged commit already passed the
full gates, so tag only after CI is green for that exact commit.

## Tags and versions

| Tag | `project.version` in `pyproject.toml` | GitHub release |
|---|---|---|
| `vX.Y.Z-rc.N` | `X.Y.ZrcN` | Pre-release ("Release Candidate") |
| `vX.Y.Z` | `X.Y.Z` | Stable |

`CHANGELOG.md` needs a `## [X.Y.Z]` section in both cases. Check locally with:

```bash
uv run --no-project python scripts/release/verify_version.py v2.0.0
```

Release notes are taken from `docs/releases/<tag>.md` when that file exists.

## What the workflow enforces

1. **verify** (read-only token)
   - Resolves the tag to a commit SHA and runs `verify_version.py`.
   - Requires the latest completed run of both `CI` and `CodeQL` for that exact
     SHA to have concluded `success`. A green run on another commit does not
     count.
   - Fails if a release or draft for the tag already exists. Releases are never
     modified or have assets replaced.
2. **publish** (write token, runs only after `verify`)
   - Checks out the verified SHA and fails if the tag moved in the meantime.
   - Builds the SPA and the wheel, then installs the wheel into a clean
     environment. It checks the installed version, the migration revision,
     `doctor`, `/api/v1/health`, `/api/v1/ready` and that `/` serves the SPA.
   - Generates the CycloneDX SBOM and `SHA256SUMS.txt`, and attests the wheel's
     build provenance.
   - Uploads everything to a **draft** release, downloads it again and checks
     every SHA-256. Only then does it publish the draft.

If a run fails after creating the draft, delete the draft by hand after reading
the logs. Never move or reuse a tag; publish a new version or a new release
candidate instead.

## After publication

Verify the release from outside the workflow:

```bash
gh release download v2.0.0 --dir /tmp/hcs-release
cd /tmp/hcs-release && sha256sum -c SHA256SUMS.txt
gh attestation verify hcs_discovery_studio-2.0.0-py3-none-any.whl --repo timfromhcs/hcs-discovery-studio
```

Install the downloaded wheel into a fresh environment and run `hcs-discovery
version`, `hcs-discovery doctor` and `hcs-discovery serve` before announcing it.
