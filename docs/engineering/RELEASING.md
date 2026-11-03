# Releasing HCS Discovery Studio

Two kinds of steps: **machine steps** (already automated and verified in CI) and
**owner steps** (credentials, approval, a registered publisher). Nothing here is
executed by an agent.

## 1. Prepare the release commit

1. Version in `pyproject.toml`, `src/hcs_discovery/__init__.py`,
   `apps/web/package.json` (+ lockfile) and `CITATION.cff` agree.
2. `CHANGELOG.md` has a `## [X.Y.Z] - YYYY-MM-DD` section (the release workflow
   refuses a tag whose version has no changelog heading).
3. `docs/releases/vX.Y.Z.md` exists; the workflow uses it as the release body and
   falls back to generated notes if it is missing.
4. Regenerate the measured numbers:
   ```bash
   uv run pytest -q --cov=hcs_discovery --cov-branch \
     --junitxml=build/junit.xml --cov-report=json:build/coverage.json
   uv run python scripts/ci/check_doc_claims.py --write
   uv run python scripts/science/benchmark_gpu_similarity.py
   ```

## 2. Local gates (machine)

```bash
uv run python scripts/gates.py --level full
uv run python scripts/gates.py --level release --only G15   # one-file executable
docker build -t hcs-discovery-studio:local .                # container, if available
```

All must pass on the release commit. `G13` (gitleaks) is skipped where the tool is
not installed; CI runs it.

## 3. Tag and approve (owner)

```bash
git tag -a v2.1.0 -m "HCS Discovery Studio 2.1.0"
git push origin v2.1.0
```

The tag starts `.github/workflows/release.yml`, which:

1. verifies that CI and CodeQL succeeded for the exact commit;
2. builds the SPA, the wheel and downloads the executable artifact;
3. smoke-tests the wheel in a clean environment (version, `db upgrade`, `doctor`,
   served `/api/v1/health`, SPA);
4. writes the SBOM and `SHA256SUMS.txt`, attests build provenance;
5. creates a **draft** release, downloads its own assets and verifies the
   checksums, then publishes it;
6. skips the PyPI job unless `PYPI_PUBLISH` is `true` (see below).

A tag whose version has no changelog section, or whose CI for that SHA is missing,
fails before anything is published.

## 4. PyPI with trusted publishing (owner, optional)

PyPI uploads are permanent; a filename can never be reused. That is why this is a
separate, gated job.

1. On PyPI, add a trusted publisher for `hcs-discovery-studio`:
   - owner: `timfromhcs`, repository: `hcs-discovery-studio`
   - workflow: `release.yml`, environment: `pypi`
2. In the GitHub repository, create the environment `pypi` (optionally with a
   required reviewer) and set the variable `PYPI_PUBLISH=true`.
3. Re-run the release workflow. The job requests an OIDC token
   (`id-token: write`), `pypa/gh-action-pypi-publish` exchanges it for a
   short-lived credential, and PEP 740 attestations are attached automatically.
4. Verify afterwards:
   ```bash
   pip install hcs-discovery-studio==2.1.0
   hcs-discovery version
   ```

No API token is stored in the repository. Without the variable the job is
skipped, so an unconfigured registry never breaks a release.

## 5. DOI (owner, optional)

1. Enable the repository in Zenodo (or another DOI provider).
2. Publish the GitHub Release; the archive is minted automatically.
3. Add the DOI to `CITATION.cff` (`doi:` field) and to the release notes.

## 6. Post-release checks

- Download the wheel and the executable from the release, verify `SHA256SUMS.txt`
  and `gh attestation verify`.
- `docker run` the published image tag, if one was pushed.
- Confirm the hosted SPA still serves `/sw.js`, the manifest and the offline lab.
- Announce with the evidence links, not with adjectives.

## 7. Rollback

- A bad GitHub Release can be edited (assets replaced) but not deleted from
  history in a way that hides it; mark it as a pre-release and publish a fixed
  patch version.
- A bad PyPI upload can only be yanked, not deleted. Ship `X.Y.Z+1`.
- Never move a tag. The workflow checks that the tag still points at the verified
  commit.
