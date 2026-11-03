# GPU Similarity (WebGPU + Vulkan) and Release-Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** One WGSL compute kernel (bit-packed Tanimoto similarity) that runs unchanged in the browser (WebGPU), natively through Vulkan (wgpu-py), inside the one-file `.exe`, with a CPU reference, a measured speed-up, and a release gate that proves parity first and reports speed second.

**Architecture:** A single source of truth `src/hcs_discovery/gpu/kernels/tanimoto.wgsl` is (a) loaded by `hcs_discovery.gpu` (Python, optional `gpu` extra, Vulkan backend forced) and (b) imported by the SPA via Vite `?raw`. Fingerprints are 2048-bit Morgan (r=2) packed into 64 × u32; the kernel computes `popcount(a&b) / popcount(a|b)` per (query, library) pair using integer arithmetic only, so GPU intersection/union counts are **bit-exact** against the CPU reference; the final division is float32 and compared with a stated tolerance. Browser path: RDKit WASM produces fingerprints (`get_morgan_fp`), WebGPU scores them, a JS/WASM CPU loop is the reference.

**Tech Stack:** wgpu-py 0.32 (native WebGPU over Vulkan/D3D12/Metal), numpy, RDKit, WGSL, WebGPU, RDKit MinimalLib WASM, PyInstaller, Vite/React/TS, Playwright, GitHub Actions, Vercel.

**Spec:** user request 2026-11-03 + `docs/engineering/ROADMAP_TO_V2_STABLE.md` §3–§4 (WebGPU "not a scientific accelerator until a named algorithm runs through it and is compared against a CPU reference" — this plan delivers exactly that algorithm).

## Research summary (what SOTA does, what we copy, what we do not claim)

- Exact fingerprint search at scale (chemfp, FPSim2, SIMD popcount) wins by **bit-packing + hardware popcount + bounds-based pruning**. We copy bit-packing + popcount (`countOneBits` in WGSL maps to `OpTypeBitCount` in SPIR-V / native popcnt) on GPU. Threshold pruning (Swamidass-Baldi bounds) is a documented follow-up, not in this plan.
- wgpu-py exposes the same WebGPU API natively on Vulkan/D3D12/Metal, so **one WGSL kernel serves browser and desktop** (verified by spike: Vulkan adapter "AMD Radeon(TM) Graphics", `backend_type='Vulkan'` on the target machine).
- WebGPU compute is float32/u32 only → we use integer popcounts for exactness and keep a CPU reference. No claim of docking/ADMET acceleration; claim is limited to "Tanimoto screening throughput, measured".
- Honesty rules (from repo): speed-ups are **reported as measured numbers on named hardware**, never asserted; parity failure fails the gate; absence of a GPU is `skipped` with reason, never `passed`.

## Global Constraints

- Python 3.12–3.13; wheel stays pure-Python + RDKit; `wgpu` and `numpy` only under optional extra `gpu` (core install must not require them).
- PyInstaller stays out of `uv.lock` (GPL bootloader exception, commit bf775ef) — keep that pattern.
- Backend forced to Vulkan when available: `WGPU_BACKEND_TYPE=Vulkan`; fall back order Vulkan → D3D12 → Metal; software/CPU adapters are rejected for speed claims (`adapter_type == "CPU"` ⇒ `skipped`).
- Fingerprint: Morgan radius 2, 2048 bits, packed little-endian into 64 u32 words per molecule.
- Parity rule: `intersection` and `union` integer counts equal CPU reference exactly; similarity float32 within `1e-6` of RDKit `BulkTanimotoSimilarity`.
- Never point gates at `./data`; use throw-away `HCS_DATA_DIR`.
- Docs numbers come from `build/gate-report.json` / `build/gpu-bench.json`, not typed by hand (`scripts/ci/check_doc_claims.py` must stay green).
- Commits end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.

## Review Focus

- Library size not a multiple of workgroup size (e.g. 1, 63, 65, 100_001) → no out-of-bounds writes, exact tail results.
- All-zero fingerprint on both sides → union 0 → similarity defined as `0.0` (RDKit returns 0.0), no NaN.
- Library larger than `maxStorageBufferBindingSize`/`maxComputeWorkgroupsPerDimension` → chunked dispatch, results identical to unchunked.
- No GPU / software adapter / `wgpu` not installed → clear `unavailable` status, CLI exit 0 for `bench` with `status: skipped`, exe still starts.
- Invalid SMILES in library → row excluded from GPU batch, index mapping preserved and reported (no silent shift).

## File Structure

| File | Responsibility |
|---|---|
| `src/hcs_discovery/gpu/__init__.py` | public API: `probe_gpu()`, `gpu_tanimoto()`, `cpu_tanimoto()` |
| `src/hcs_discovery/gpu/kernels/tanimoto.wgsl` | the one shader (shared with web) |
| `src/hcs_discovery/gpu/fingerprints.py` | SMILES → packed `uint32[N,64]` + validity mask |
| `src/hcs_discovery/gpu/cpu.py` | numpy popcount reference |
| `src/hcs_discovery/gpu/device.py` | adapter selection, Vulkan preference, probe dict |
| `src/hcs_discovery/gpu/engine.py` | buffers, chunked dispatch, timing |
| `src/hcs_discovery/gpu/bench.py` | benchmark + parity → `build/gpu-bench.json` (schema `hcs.gpu-bench.v1`) |
| `src/hcs_discovery/cli/main.py` | `hcs-discovery gpu probe|bench` |
| `src/hcs_discovery/api/routes/system.py` | `/api/v1/system/gpu` |
| `apps/web/src/lib/gpuTanimoto.ts` | WebGPU engine + CPU reference (imports `tanimoto.wgsl?raw`) |
| `apps/web/src/components/GpuBenchmark.tsx` | UI panel: run, parity badge, timings |
| `tests/gpu/…`, `apps/web/e2e/gpu.spec.ts` | tests |
| `scripts/gates.py`, `.github/workflows/ci.yml`, `release.yml` | gate G14 + exe smoke + release assets |

---

### Task 1: Shared WGSL kernel + CPU reference

**Files:** Create `src/hcs_discovery/gpu/{__init__,cpu,fingerprints}.py`, `kernels/tanimoto.wgsl`; Test `tests/gpu/test_cpu_reference.py`; Modify `pyproject.toml` (extra `gpu = ["wgpu>=0.32","numpy>=2"]`, include `.wgsl` in wheel).

**Interfaces:** Produces `pack_smiles(smiles: Sequence[str]) -> tuple[np.ndarray[uint32,(N,64)], np.ndarray[bool,(N,)]]`; `cpu_counts(q: ndarray(64,), lib: ndarray(N,64)) -> tuple[ndarray[uint32], ndarray[uint32]]` (intersection, union); `cpu_tanimoto(q, lib) -> ndarray[float32]`.

- [ ] Write failing tests: `test_pack_matches_rdkit_bits` (set-bit count equals `GetNumOnBits`), `test_cpu_tanimoto_matches_rdkit_bulk` (≤1e-6 on 200 demo SMILES), `test_zero_fingerprint_gives_zero_not_nan`, `test_invalid_smiles_flagged_in_mask`.
- [ ] Run `uv run pytest tests/gpu/test_cpu_reference.py -q` → FAIL (module missing).
- [ ] Implement packing via `rdFingerprintGenerator.GetMorganGenerator(radius=2,fpSize=2048)` and numpy popcount (lookup table on uint8 view).
- [ ] Write WGSL: `@workgroup_size(64)`, bindings `query: array<u32>(64)`, `lib: array<u32>`, `out_inter`, `out_union: array<u32>`, uniform `{count:u32, offset:u32}`; guard `i >= count`; loop 64 words with `countOneBits`.
- [ ] Run tests → PASS. Commit `feat(gpu): shared WGSL Tanimoto kernel and numpy reference`.

### Task 2: Native Vulkan engine (wgpu-py)

**Files:** Create `gpu/device.py`, `gpu/engine.py`; Test `tests/gpu/test_engine.py` (marked `gpu`, auto-skip without adapter).

**Interfaces:** Consumes Task 1 packers. Produces `probe_gpu() -> dict` (`status: available|unavailable|software_only`, `backend`, `adapter`, `limits`), `gpu_counts(q, lib, *, chunk=1<<20) -> GpuResult(inter, union, kernel_ms, total_ms, adapter, backend)`.

- [ ] Failing tests: parity (exact inter/union vs `cpu_counts`) for N in {1, 63, 65, 100_001}; chunked == unchunked with `chunk=1000`; `probe_gpu()` returns `unavailable` (no raise) when `wgpu` import is monkeypatched away.
- [ ] Implement adapter choice: enumerate, prefer `backend_type=="Vulkan"` and non-`CPU` adapter; reject software; timestamp-free timing via `perf_counter` around submit+readback, plus `kernel_ms` from repeated dispatch minus transfer (document method).
- [ ] Tests PASS locally (Radeon 680M Vulkan). Commit.

### Task 3: Benchmark, CLI, API, doctor

**Files:** Create `gpu/bench.py`; Modify `cli/main.py`, `api/routes/system.py`, `core/doctor.py`; Test `tests/gpu/test_bench_cli.py`.

**Interfaces:** `run_bench(n_library: int = 200_000, repeats: int = 5, seed: int = 0) -> dict` schema `hcs.gpu-bench.v1`: `{status, parity:{exact_counts:bool,max_abs_err:float}, cpu_ms, gpu_ms, speedup, adapter, backend, n_library, commit}`; CLI `hcs-discovery gpu bench [--json] [--out build/gpu-bench.json]` exits 1 only on **parity failure**, 0 on pass/skipped.

- [ ] Failing tests: CLI `--json` on a machine without wgpu returns `status: skipped` exit 0 (monkeypatch); with wgpu `parity.exact_counts is True`; API route returns the probe.
- [ ] Implement; library generated by deterministically mutating bit patterns of demo-compound fingerprints (seeded) so no data download is needed.
- [ ] PASS. Commit.

### Task 4: Browser WebGPU engine (shares the shader)

**Files:** Create `apps/web/src/lib/gpuTanimoto.ts`, `components/GpuBenchmark.tsx`; Modify `pages/About.tsx` or the BrowserChemistry panel mount, `vite.config.ts` (allow `server.fs` to read `../../src/hcs_discovery/gpu/kernels`); Test `apps/web/e2e/gpu.spec.ts`.

**Interfaces:** `runGpuTanimoto(query: Uint32Array, lib: Uint32Array): Promise<{inter:Uint32Array;union:Uint32Array;ms:number}>`; `cpuTanimoto(...)` same signature; `compareEngines(n: number): Promise<{status;parity;cpuMs;gpuMs;speedup;adapter}>`. Fingerprints from `mol.get_morgan_fp({radius:2,nBits:2048})` bit-string → packed u32.

- [ ] Failing Playwright test (Chromium with `--enable-unsafe-webgpu --use-angle=vulkan --enable-features=Vulkan`): panel shows `parity: exact`; when WebGPU absent, panel shows `unavailable` and CPU result still renders (no silent fallback claim).
- [ ] Implement with the same buffer layout as native; reuse structural GPU types already in `browserCapabilities.ts`.
- [ ] `npm run typecheck && npm run build && npm run test:e2e` green. Commit.

### Task 5: Release gate G14 and executable

**Files:** Modify `scripts/gates.py` (gate `G14 gpu-parity`, levels `release`,`science`; `skipped` with reason when no hardware adapter), `scripts/release/hcs_discovery.spec` (hidden import `wgpu`, collect `wgpu` native DLL + `.wgsl`), `scripts/release/build_executable.py` (smoke: `hcs-discovery.exe gpu bench --json` must return valid JSON), `.github/workflows/ci.yml`, `release.yml` (upload `gpu-bench.json`), `scripts/ci/check_doc_claims.py`.

- [ ] Failing test `tests/test_gates_gpu.py`: gate list contains G14; report entry has `status in {passed, skipped}`.
- [ ] Implement; rebuild exe locally; run `build/exe-dist/hcs-discovery.exe gpu bench --json` → parity true, record speedup.
- [ ] `uv run python scripts/gates.py --level full` and `--level release` green. Commit.

### Task 6: Docs, evidence, cloud

**Files:** Modify `docs/engineering/ROADMAP_TO_V2_STABLE.md` (check boxes with evidence), `IMPLEMENTATION_STATUS.md`, `RELEASE_EVIDENCE.md`, `README.md`, `CHANGELOG.md`, `AGENT_LOG.md`; Create `docs/research/GPU_SIMILARITY.md` (method, measured table from `build/gpu-bench.json`, limitations, follow-ups: threshold pruning, top-k reduction, fp16 packing).

- [ ] Doc-claims check green. Push branch, open PR, watch CI/CodeQL via `gh run watch`; fix-and-push loop until green.
- [ ] Vercel preview deploy of SPA; verify served page loads and shows GPU panel (WebGPU absent in headless ⇒ honest `unavailable` expected).
- [ ] All cloud checks green ⇒ merge PR to `main`. **Not** tagging/publishing v2.0.0 (owner-gated per roadmap).

## Self-review

Spec coverage: WebGPU ✓ T4; WASM ✓ T4 (RDKit fingerprints) ; local exe solo-file ✓ T5; Vulkan boost measured ✓ T2/T3/T5; release gate ✓ T5; plan file ✓; push loop + cloud + merge ✓ T6. Names consistent across tasks (`cpu_counts`, `gpu_counts`, `run_bench`, schema `hcs.gpu-bench.v1`).
