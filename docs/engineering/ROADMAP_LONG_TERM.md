# Long-term roadmap (2026 H2 → 2027)

This is the forward-looking plan, written after the v2.0.0 release candidate, the
GPU similarity path, the offline browser lab and the container/MCP work. It is
deliberately smaller than a wish list: each item has an evidence gate, and anything
that cannot be measured stays out.

The repository rules apply unchanged: no claim without a command, honest
degradation, local first, no invented SOTA.

## 1. What the research says about sustaining software like this

- **Tests are the technical foundation of sustainability.** The US-RSE 2026
  programme and the Princeton RSE handbook describe reliable tests as what makes
  iterative refactoring, feature work and agent-assisted development safe. This
  repo already gates on tests, coverage, lint, types and E2E; the long-term work is
  to keep those gates fast enough that they are actually run.
- **Citability and releases matter as much as code.** Sustainable research
  software ships citable, versioned artifacts (DOI, SBOM, checksums) and releases
  often enough that users can pick one. The wheel/executable already carry
  provenance; a DOI and a PyPI release are missing.
- **Maintenance dominates.** The 2026 State of Open Source report puts maintenance
  above new features as the capacity bottleneck. Fewer, better-supported engines
  beat a long list of `planned` cards.
- **Algorithmic headroom is still real in similarity search.** chemfp reports that
  popcount bounds (BitBound: `a·T ≤ b ≤ a/T`) give roughly an order of magnitude
  on high-threshold searches, and ~10 ms for 1M fingerprints on one core. Our kernel
  currently scans the whole library.

## 2. Horizons

### Now (0–4 weeks) — close the measurable gaps

| Item | Why | Acceptance |
|---|---|---|
| **BitBound prefilter** (done 2026-11-03) | The kernel scans everything; the bound is proven and cheap | `threshold_hits` returns exactly the full-search hits (differential test), candidate fraction and time reported in `docs/validation/gpu-tanimoto.md` |
| **Exact bound-pruned k-NN** (done 2026-11-04) | A threshold-only bound leaves plain k-NN scanning the library | `knn_hits` equals the full scan (ties included); staged dispatches; 6.0×/3.9× on a clustered synthetic library, 0.85× when unclustered — both published |
| **Batched multi-query kernel** (done 2026-11-04) | Screening asks hundreds of queries; one dispatch per query wastes the uploading | `tanimoto_batch.wgsl`, `search_many`, `similarity screen`; 10.9×/9.7×, parity per query |
| **Dataset fingerprint cache** (done 2026-11-03, measured 43× on a 5k synthetic library) | Similarity re-fingerprints on every call; the dominant cost at library scale | Packed fingerprints stored once per dataset (content-hashed), reused across runs; cache hit measured |
| **Metric and audit endpoints** (metrics done 2026-11-03) | Operators cannot see queue depth, cache hit rate or run latency today | `/api/v1/metrics` (Prometheus text) + a test for each series; no external dependency |
| **Lighthouse/CLI budgets** | The SPA bundle is ~550 kB and unmonitored | **axe + bundle budget done 2026-11-03**; Lighthouse/LCP/CLS thresholds still open |
| **Accessibility audit of the new pages** | The lab and the SEO pages shipped after the 192-capture QA | axe-core run over every route, zero serious/critical findings, documented exceptions |

### Next (1–3 months) — depth instead of breadth

| Item | Why | Acceptance |
|---|---|---|
| **v3.0.0 release on every platform** (prepared 2026-11-04) | Sustainability: one artifact per platform, citable release | Release matrix builds Windows/Linux/macOS binaries, GHCR image and wheel; PyPI + DOI are owner-gated |
| **RO-Crate provenance** (done 2026-11-04) | A run manifest only this app reads is not provenance | RO-Crate 1.1 + PROV JSON-LD with artifact hashes; CLI/API/UI; not WRROC-profile conformant |
| **MCP `2026-07-28`** (done 2026-11-04) | Legacy handshake clients and modern stateless clients both exist | `server/discover`, `_meta` versioning, `ttlMs`/`cacheScope`, legacy fallback, tests for both |
| **PyPI + DOI** | Sustainability: installable, citable artifacts | Trusted-publishing job and runbook exist; the upload and a Zenodo DOI stay owner-gated |
| **Observability in the UI** | Run health is only visible as raw events | **Done 2026-11-04** — run timeline from persisted timestamps (queue, node durations, cache marker) |

### Later (3–12 months) — scientific breadth, only with evidence

| Item | Why / condition | Acceptance |
|---|---|---|
| **Property model on a public benchmark** | The Delaney reproduction is measured (RMSE 1.099, R² 0.725) but is a 2004 linear baseline. A learned model without a measured baseline would repeat the ESOL mistake | A pinned TDC endpoint, scaffold split, RMSE/MAE with bootstrap CI, and a report that names the baseline it beats |
| **Multi-target docking benchmark** | One redocking complex is a regression test, not accuracy | Pose recovery over a fixed, licensed complex set; per-target results, failures included |
| **Conformer generation (ETKDG) + shape similarity** | 3D is a real gap; RDKit already provides ETKDG | Deterministic seed, runtime fingerprint, a measured comparison against the 2D fingerprint ranking |
| **PostgreSQL backend (optional)** | Multi-user is explicitly out of scope today | A tested adapter and queue semantics, or an explicit "not planned" decision recorded |

### Not planned

- MD (OpenMM), structure prediction (Boltz-2/Chai-1), learned ADMET as a bundled
  default, multi-tenant hosting, telemetry, CUDA-only acceleration.
- A second chemistry engine. RDKit is the contract; a second implementation would
  double the validation surface without a user asking for it.

## 3. Order and dependencies

```text
BitBound ──► dataset fingerprint cache ──► batched multi-query
   │
metrics/audit ──► UI observability
Lighthouse/axe ──► release 2.1 ──► DOI
SAT node ──► (independent)
Benchmark-first science (ESOL replacement, docking set) ──► only then a claim
```

## 4. Risks

| Risk | Mitigation |
|---|---|
| Optimisations that change numbers | Differential tests against the unoptimised path, exact equality, never a tolerance |
| Scope creep into model hosting | Every scientific item needs a pinned benchmark and a baseline before it is scheduled |
| CI time growth | Gates stay tiered (`fast` / `full` / `release`); new heavy checks go to `release` |
| Release credentials | PyPI/DOI steps are prepared and documented, executed only with owner approval |
| Browser/storage APIs vary | Every browser capability is probed and labelled; no silent fallback |

## 5. Quarterly review questions

1. Which row in `IMPLEMENTATION_STATUS.md` moved from `planned` to `available`, and
   what command proves it?
2. Which measured number got worse? (If none, the benchmarks are not being run.)
3. What was deliberately deleted? A roadmap without deletions grows into a museum.

## 6. Sources

- US-RSE 2026 programme, research-software sustainability handbook —
  <https://us-rse.org/usrse26/program/talks>
- Open Source Initiative, *2026 State of Open Source Report* —
  <https://opensource.org/blog/the-2026-state-of-open-source-report>
- A. Dalke, *The chemfp project* and *Simple BitBound ChEMBL similarity search* —
  <https://jcheminf.biomedcentral.com/articles/10.1186/s13321-019-0398-8>,
  <http://www.dalkescientific.com/writings/diary/archive/2020/10/01/simple_bitbound_search.html>
- Swamidass & Baldi, *Bounds and algorithms for fast exact searches of chemical
  fingerprints* (the `a·T ≤ b ≤ a/T` bound), as summarised in Dalke's slides —
  <https://www.c-inf.net/slides/dalke.pdf>
