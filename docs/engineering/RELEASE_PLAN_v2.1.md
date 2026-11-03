# Release plan v2.1.0 — local, cloud, web, exe, GitHub

**Date:** 2026-11-03
**Owner:** hcsmedia
**Status:** executing
**Scope:** turn the current `main` into a *release-candidate quality* `2.1.0`
without inventing approvals the owner has not given.

## 1. Why 2.1.0 and not 2.0.0

`2.0.0` was prepared as a release candidate and never tagged or published. Since
that candidate the tree gained a GPU similarity engine, an offline browser lab, a
similarity API, an MCP server, a SAT solver, a container image, a service worker,
SEO and three translated guides. That is a minor version by SemVer, so the next
release is **2.1.0**; the changelog says explicitly that `2.0.0` was never
published, so nobody looks for a tag that does not exist.

Publishing a tag, a GitHub Release, a PyPI package or a production promotion is
**owner-gated**. This plan prepares every step and verifies everything that can be
verified locally; it does not push a tag.

## 2. The loop

Each round ends with: the gates for that round green, a docs/changelog line, and a
commit. A round that cannot be verified is not marked done.

```text
R0 baseline ─► R1 version/metadata ─► R2 GitHub/release ─► R3 web/a11y
   ▲                                                          │
   └──────────── R6 release gate ◄─ R5 desktop/cloud ◄─ R4 README ◄┘
```

### R0 — Baseline (evidence first)

- `git status` clean, `scripts/gates.py --level full` green, CI green on `main`.
- Record the starting SHA in the release notes draft.

### R1 — Version and metadata

| File | Change | Check |
|---|---|---|
| `pyproject.toml` | `version = "2.1.0"` | `uv run python -c "import hcs_discovery; print(hcs_discovery.__version__)"` |
| `apps/web/package.json` + lockfile | `2.1.0` | `npm run build` embeds nothing version-specific, but keep them aligned |
| `CITATION.cff` | version + release date | `cffconvert`-shaped YAML parses (checked by the docs test) |
| `CHANGELOG.md` | `## [2.1.0] - 2026-11-03` with the real changes | every bullet is traceable to a commit |
| `docs/releases/v2.1.0.md` | release notes: highlights, install, evidence, limitations | linked from README |
| `README.md` | status line, badges, capability table | numbers come from generated blocks, not from hand |

### R2 — GitHub and release automation

- Confirm the PR/issue templates exist and still match the process (they do; only
  update if the process changed).
- Add a **PyPI trusted-publishing job** to `release.yml` that runs only when the
  repository variable `PYPI_PUBLISH` is `true`. Trusted publishing needs an
  OIDC token (`id-token: write`), no long-lived secret, and a registered publisher
  on PyPI; until the owner registers one and sets the variable, the job stays
  skipped — a release does not fail because of an unconfigured registry.
- Verify `SHA256SUMS`, SBOM and build-provenance attestation steps still run.
- Add a short `docs/engineering/RELEASING.md` runbook: the human steps (tag,
  approval, PyPI publisher, Zenodo DOI) and the machine steps.

### R3 — Web, design and accessibility

Research basis: WCAG 2.2 adds *Focus Not Obscured* (2.4.11, AA), *Target Size*
(2.5.8, AA) and *Dragging Movements* (2.5.7, AA); focus must survive a sticky
header, and touch targets need 24×24 CSS px minimum (we aim for 44).

- The offline lab announces its result region with `aria-live="polite"`, moves
  focus to the region after an import, and labels the busy state.
- Sticky header: `scroll-padding-top` so a focused element is never hidden
  (2.4.11).
- Touch targets on the lab and settings pages: primary controls ≥ 44 px.
- Playwright checks for the announcement, the focus move and the scroll padding;
  the existing visual QA remains the broader sweep.

### R4 — README and docs truth

- Status line, capability table and testing table reflect the code (generated
  numbers regenerated, no hand-written counts).
- Quick start: executable, wheel, Docker, browser-only — four honest paths.
- Link the release notes, the long-term roadmap, the SOTA gap analysis and the
  three guides.

### R5 — Desktop and cloud verification

- `scripts/gates.py --level release --only G15` (one-file executable, including a
  verified GPU search inside the frozen binary).
- Wheel build + install smoke (part of `--level full`, G8).
- Docker image build and a health/SPA/similarity smoke.
- Production deploy: **blocked on 2026-11-03** by the Vercel free-plan daily
  deployment limit (`api-deployments-free-per-day`). The hosted build still serves
  the previous commit; the release notes say so instead of claiming the new UI is
  live.

### R6 — Release gate

- `--level full` and G15 green on the release commit.
- CI + CodeQL green on that SHA.
- Evidence regenerated (`docs/validation/gpu-tanimoto.md`,
  `docs/engineering/evidence.json`).
- Tag/release/PyPI/DOI remain **pending owner approval**; the runbook lists the
  exact commands.

## 3. What this plan deliberately does not do

- No tag, no GitHub Release, no PyPI upload, no DOI without the owner.
- No new scientific claim. The ESOL estimate stays labelled weak; docking stays a
  one-complex regression check.
- No UI redesign for its own sake: only changes that fix an accessibility or
  clarity defect found by a test or a documented rule.
- No dependency added for a11y or SEO; the checks are written with what is
  already installed.

## 4. Acceptance checklist

- [x] R0 baseline recorded
- [x] R1 version 2.1.0 everywhere, changelog + release notes written
- [x] R2 PyPI job (gated), runbook, release steps reviewed
- [x] R3 aria-live, focus move, scroll padding, target sizes; tests green
- [x] R4 README regenerated and truthful
- [x] R5 exe + wheel + container verified
- [x] R6 full gates + G15 green on the release commit
- [ ] Tag/PyPI/DOI listed as owner-gated, not done — **pending owner approval**

## 5. References

- PyPI, *Publishing with a Trusted Publisher* — <https://docs.pypi.org/trusted-publishers/using-a-publisher>
- PEP 740 attestations and the `pypa/gh-action-pypi-publish` action —
  <https://buildwithfern.com/post/automating-pypi-releases-python-sdks>
- W3C, *WCAG 2.2* — <https://www.w3.org/TR/WCAG22/>
- Understanding SC 2.4.11 *Focus Not Obscured* —
  <https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html>
- GitHub, *Releasing projects* — <https://docs.github.com/en/repositories/releasing-projects-on-github>
