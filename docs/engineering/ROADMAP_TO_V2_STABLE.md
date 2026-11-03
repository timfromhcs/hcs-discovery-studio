# Roadmap to v2.0.0 Stable + browser-native compute — plan and positioning

**Date:** 2026-11-02 (revised)
**Branch:** `feat/v2-stable-readiness` (from `main` @ `e5823b8`)
**Version:** `2.0.0` release candidate merged to `main`; not tagged/published yet.

This is the plan of record for two tracks:

1. **Ship `v2.0.0 Stable`** — the correctness-and-integrity release, with every
   mandatory gate green on the exact tagged commit.
2. **Add a browser-native compute path** — WebAssembly (RDKit) and WebGPU
   capability, with tool parity to the local backend, "safe gates" and
   hardware-fit fallback, plus a **one-file executable** for local distribution.

Both tracks follow the repository's evidence discipline: a claim is only made
after a command, gate or test has produced the result. "State of the art" and
"perfect" are not asserted; measured outcomes are.

---

## 1. Status snapshot (2026-11-03)

| Item | State |
|---|---|
| Local gates (`scripts/gates.py --level full`) | **PASS** on `e5823b8`; re-run on the current branch below |
| PR #13 (browser probe + doc reconciliation) | **CI and CodeQL green** |
| Full backend on Vercel | **Blocked** — bundle 561 MB > Vercel's 500 MB function limit (RDKit + data dominate) |
| Static SPA on Vercel | Project `hcs-discovery-studio` created; static deploy pending |
| Browser compute | **Working** — RDKit WebAssembly self-test and WebGPU Tanimoto parity, both covered by Playwright against the served app |
| GPU similarity search | **Working** — `hcs_discovery.similarity`, `chem.similarity` engine option, `similarity search` CLI, measured benchmark |
| `v2.0.0` tag / release | Not created (owner approval required) |

## 2. Goals and success criteria

1. **v2.0.0 Stable published** with verified wheel + SBOM + checksums + attestation.
2. **Browser compute**: RDKit chemistry runs in the browser via WebAssembly with
   the same operations (parse, canonicalise, descriptors, depiction) as the local
   backend; WebGPU is detected and its compute pipeline is verified with a
   self-test, and the app reports a **hardware fit** (what the visitor's device
   can actually do) rather than claiming acceleration.
3. **One-file executable** builds for the supported platform and runs the same
   doctor/serve journey as the wheel, added to the release.
4. **First local, then cloud**: every capability is verified by the local gate
   runner before it is deployed to Vercel or tagged.

## 3. Competitive positioning (honest)

Unchanged from the original roadmap: HCS Discovery Studio leads on
**transparent, reproducible, local-first** open-science workbenches, and does
**not** claim SOTA in docking accuracy, learned ADMET or scale. The browser
compute path extends the local-first idea to the browser:

- **WebAssembly (RDKit)** gives real, offline chemistry in the browser with
  numerical parity to the local backend — no server round-trip, no cloud key.
- **WebGPU** is reported as hardware presence plus a verified compute pipeline;
  it is **not** claimed as a scientific accelerator until a named algorithm
  actually runs through it and is compared against a CPU reference.
- **Precision honesty**: WebGPU compute uses float32 (the API does not expose
  float64 on all devices); any GPU-accelerated path that trades precision will
  say so and keep a CPU/WASM reference. "All tools equal" means feature parity,
  not bit-identical numerics across backends.

## 4. Work packages

### v2.0.0 Stable (in flight)
- **P0 (done):** stale About-page claims fixed; browser capability probe added;
  changelog reconciled. PR #13 CI/CodeQL green.
- **P1:** merge to `main`, then owner-gated tag + release publication.

### Browser-native compute (new)
- **P2 (done) — WebAssembly chemistry.** Add `@rdkit/rdkit` (official RDKit MinimalLib
  WASM), a lazily-initialised `lib/rdkit.ts`, and a client-side capability that
  parses/canonicalises SMILES, computes core descriptors and renders an SVG
  depiction. Wired into the UI as an explicit "browser chemistry" panel with a
  clear "computed in this browser via WebAssembly" label. Verified by typecheck,
  build, E2E and a smoke check against the backend's RDKit output.
- **P3 (done) — WebGPU hardware fit and a real kernel.** The probe requests an
  adapter, reads its limits, runs a compute-pipeline self-test and reports a fit.
  The WGPU Tanimoto kernel then runs in the browser against a JavaScript CPU
  reference, parity first, speed second.
- **P4 (done) — Safe gates.** Client-side compute is gated behind the same
  discipline as the server: explicit input validation, no silent fallback, a
  visible error when WASM/WebGPU fails to load, and a CPU/WASM reference path. No
  data leaves the browser.

### GPU similarity search (this cycle)
- **P7 (done) — One kernel, three layers.** `hcs_discovery.similarity` exposes
  k-nearest and threshold search over packed Morgan fingerprints, a resident
  library, chunking above the storage-buffer limit and an exact CPU reference;
  the `chem.similarity` node takes `engine: auto | cpu | gpu`; the CLI has
  `similarity search`; the browser runs the same WGSL file. Evidence:
  `docs/validation/gpu-tanimoto.md`, generated by
  `scripts/science/benchmark_gpu_similarity.py`.
- **P8 (next) — Bound-based prefiltering.** BitBound-style popcount bounds for
  threshold and kNN search, then persistent packed fingerprints per dataset, so
  the dominant cost (fingerprinting) is paid once.

### Packaging (new)
- **P5 — One-file executable.** Add a PyInstaller (or equivalent) build that
  bundles the Python app, RDKit, the built SPA and migrations into a single
  `hcs-discovery(.exe)`; add a `scripts/release/build_executable.py` and a CI
  smoke gate. Verify the same `doctor`/`db upgrade`/`serve` journey as the wheel.
  Add the artifact to the release workflow.

### Deployment
- **P6 (done) — Vercel preview and production (first local, then cloud).** The
  static SPA with the WebAssembly/WebGPU capability is deployed to the
  `hcs-discovery-studio` project. Verified in Chrome against the deployed URL:
  RDKit WebAssembly self-test `verified`, WebGPU Tanimoto `parity: bit-exact`
  over 100,000 fingerprints. The deployment is protected by Vercel
  Authentication, so the check used the CLI's development OIDC token; nothing was
  made public to run it. The full RDKit backend stays local/wheel-based because it
  exceeds Vercel's function size limit (recorded in §1). Evidence:
  [Release evidence](RELEASE_EVIDENCE.md#browser-compute-on-vercel--verified-2026-11-03).

## 5. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| RDKit WASM adds bundle size / load time | Slower first paint on Vercel | Lazy-load the WASM module only when browser chemistry is opened |
| WebGPU float32 precision differs from float64 | Misleading numerics | Report precision honestly; keep CPU/WASM reference; no scientific claim |
| PyInstaller + RDKit hidden imports/data | exe build fails | Iterate the spec locally; record exact blockers; do not claim success |
| Owner-gated tag/release | Blocks publication | Prepare everything; report the required human action |

## 6. Final acceptance checklist

- [x] v2.0.0 gate runner `full` green locally; CI + CodeQL green on the tag SHA.
- [x] RDKit WebAssembly chemistry works in-browser and matches backend output.
- [x] WebGPU probe reports a verified hardware fit (or honest absence).
- [ ] One-file executable builds and passes the doctor/serve smoke journey.
- [x] Vercel preview serves the SPA with browser compute; links verified.
- [ ] Release publishes wheel + exe + SBOM + checksums + attestation.
- [ ] `main` merged; README reconciled.

Execution evidence is appended to `docs/engineering/AGENT_LOG.md`.
