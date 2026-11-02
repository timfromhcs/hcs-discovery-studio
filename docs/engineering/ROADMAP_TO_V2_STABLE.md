# Roadmap to v2.0.0 Stable — plan and competitive positioning

**Date:** 2026-11-02
**Branch:** `feat/v2-stable-readiness` (from `main` @ `e5823b8`)
**Version:** `2.0.0` release candidate — merged to `main`, not yet tagged or published.

This is the plan of record for the final step from the current verified release
candidate to a published `v2.0.0 Stable`, together with an honest positioning of
the product against the market. It follows the same evidence discipline as the
rest of the repository: every claim traces to a command, a gate, a test or a
published artifact, and "state of the art" is never asserted without a
measurement. Numbers that the repository measures are owned by
`scripts/ci/check_doc_claims.py` and `docs/engineering/RELEASE_EVIDENCE.md`, not
typed by hand here.

---

## 1. Verified baseline (reproduced 2026-11-02)

The repository already ships, on `main`:

- **Unified gate runner** `scripts/gates.py` (G0–G14) that mirrors
  `.github/workflows/ci.yml` and writes `build/gate-report.json`.
- **A hosted preview on Vercel** — `vercel.json`, a root `app.py` entrypoint and
  `src/hcs_discovery/demo.py`, which seeds a disposable synthetic workspace
  (`HCS_DEMO_MODE=true`) through the real import + worker path.
- **Targets & structures with provenance** (service + API + CLI), **HAEL**
  (experimental, library only), and a **research register**.
- **Generated documentation numbers** (`docs/engineering/evidence.json`,
  `check_doc_claims.py`) so test/coverage counts never drift from measurement.

`docs/engineering/RELEASE_EVIDENCE.md` records the measured local and cloud gate
results and states plainly that the release workflow has **not yet run end to
end**. The only remaining publication blockers are owner approval for the Stable
tag and the first real release-candidate run.

## 2. Goal and success criteria

Publish `v2.0.0 Stable` — the correctness-and-integrity release — with every
mandatory gate green on the exact tagged commit, and reconcile the remaining
documentation so the ledger tells one truth.

**Success criteria (all must hold before tagging):**

1. The unified gate runner (`scripts/gates.py --level full`) is green locally,
   and CI + CodeQL are green on the exact candidate SHA in the cloud.
2. The frontend still type-checks and builds after the browser-capability change.
3. Documentation is reconciled: `About.tsx` no longer claims features are absent
   that v1.0/v2.0 actually ship, and the changelog/README mention the hosted
   preview that `main` now contains.
4. Release workflow verifies tag/version/changelog and publishes a verified,
   attested wheel + SBOM + checksums.
5. `main` contains the release commit.

**Anti-goals (out of scope for v2.0.0):** new scientific engines, distributed
workers/PostgreSQL, multi-tenant hosting, or any new scoring claim without an
independent validation report. The hosted preview is already scoped as a
disposable demo; this plan does not turn it into a production service.

## 3. Competitive positioning — honest "state of the art"

The field splits into commercial suites (Schrödinger, OpenEye, Cresset,
Optibrium/StarDrop), graphical workbenches (DataWarrior, KNIME + RDKit) and
research libraries (RDKit, AutoDock Vina). HCS Discovery Studio does **not**
compete on raw docking throughput or trained-ADMET breadth, and must not claim
to. It leads on a different, measurable axis:

| Capability | HCS Discovery Studio | Typical alternatives |
|---|---|---|
| Reproducible provenance | Content-addressed cache keyed by engine version, package fingerprint, receptor hash; immutable manifests with SHA-256 artifacts | Partial or vendor-specific |
| Transparent ranking | Explicit rule filters, constraint/objective separation, Deb's non-dominated sorting, visible weights; rejected rows stay visible | Opaque proprietary scores common |
| Honest scope | Adapter states `implemented` / `runnable` / `reference-tested` / `planned`; ESOL publishes measured weak performance (RMSE 0.97, R² 0.07) | Accuracy often overstated |
| Local-first, zero-config | Offline CPU demo, no account/cloud key/Docker/CUDA | Licensing/cloud usually required |
| Headless parity | UI, CLI and `/api/v1` share services | Often UI-only |
| Released scientific gate | CI redocks imatinib into 1IEP and fails if top pose > 2.0 Å | Rarely a build gate |

This is a **leading position in transparent, reproducible, local-first open
science workbenches** — a real niche. It is **not** state of the art in docking
accuracy, learned ADMET or production scale; those gaps are acknowledged, not
hidden, in `SCIENTIFIC_LIMITATIONS.md` and the release evidence.

Raising the *scientific* state of the art (a docking benchmark suite, a validated
learned-ADMET adapter, structure prediction) is a separate, later program of work
that requires its own independent validation and version. It is not bundled into
v2.0.0.

## 4. Work packages (this branch)

Each package is verified by the loop **reproduce → diagnose → fix → retest →
inspect diff → record evidence**; nothing is committed until its gate passes.

### P1 — Correct stale UI claims (`apps/web/src/pages/About.tsx`)
The "Limitations register" still says "No docking, ADMET or structure
prediction" and the release-facts row says "Remote connectors: 0". Since v1.0 the
product ships Vina docking (host-dependent), reduced ESOL + CNS-MPO estimates and
PubChem/ChEMBL connectors (policy-gated). Rewrite those claims to distinguish
implemented-but-approximate from planned.

### P2 — Browser capability detection (WebGPU / WebAssembly)
Add a client-side probe (`apps/web/src/lib/browserCapabilities.ts`) that reports
whether the browser exposes WebGPU (`navigator.gpu`) and WebAssembly, mirroring
the backend Vulkan probe's rule: report hardware presence only, never imply a
scientific engine executes through it. Surface it on the Settings page. This is
meaningful on the hosted preview, where the visitor's browser — not the local
backend — is the thing to probe.

### P3 — Changelog and README reconciliation
`main` already merged the hosted preview, the gate runner and the CLI
`--no-follow` exit-code fix, but the `[Unreleased]` changelog and README do not
mention the hosted preview. Add accurate, non-inflated entries; leave generated
`<!-- gen:… -->` numbers untouched.

### P4 — Local gate verification
Run `scripts/gates.py --level full` (and the docking science gate where the Vina
binary is available), plus the frontend build, on the clean branch.

### P5 — Cloud and hosted-preview verification
Push the branch; inspect CI + CodeQL on the exact SHA. Link the Vercel project
and deploy the hosted preview, then verify the served SPA and the browser
capability probe end to end.

### P6 — Release and merge
After owner approval and a green release-candidate run, tag `v2.0.0`, verify the
published assets, and merge to `main`. (Publication is owner-gated and will not
be bypassed.)

## 5. Deployment strategy

- **Primary target:** GitHub Releases + GitHub Actions (wheel + SBOM +
  checksums + build-provenance attestation).
- **Hosted preview:** the existing Vercel integration (`vercel.json` +
  `app.py` + `HCS_DEMO_MODE=true`) serves a disposable demo workspace. It is a
  preview, not a production service: `/tmp`-backed, single-process, no durable
  state. This plan re-deploys it with the browser-capability probe and the
  corrected About page, and labels it accurately in the README.
- **WebGPU / WebAssembly:** detected client-side as platform capabilities (P2).
  No scientific engine executes in the browser in v2.0.0; that remains a
  documented, separately-validated future direction.

## 6. Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| Gate-runner audit steps need network (`pip-audit`, `npm audit`) | Local `full` may fail offline | Cloud runs them; record local skip honestly, never as "passed" |
| `gitleaks` not installed locally | `G13` skipped | Marked optional by the runner; CI runs it |
| Vina binary absent on this host | `science-vina` skipped | CI `science-vina` job is authoritative; report, do not fake |
| Release workflow never run end to end | Late publication failure | Hardened exact-SHA gate + draft-then-verify; first real run observed |
| Owner-only actions (tag, release approval, branch protection) | Block P6 | Prepare everything; report the exact required human action |

## 7. Final acceptance checklist

- [ ] Gate runner `full` green locally; CI + CodeQL green on the candidate SHA.
- [ ] Frontend typecheck/build clean with the browser probe.
- [ ] `About.tsx` claims match shipped features; changelog/README mention the
      hosted preview.
- [ ] Hosted preview deployed and smoke-tested; browser probe renders correctly.
- [ ] Version verifier passes; changelog/release notes synchronized.
- [ ] Release published with verified wheel/SBOM/checksums/attestation.
- [ ] `main` merged to the release commit.

Execution evidence is appended to `docs/engineering/AGENT_LOG.md` as each phase
completes.
