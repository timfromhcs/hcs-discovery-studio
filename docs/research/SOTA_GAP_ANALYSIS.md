# SOTA gap analysis — what "state of the art" means here, and what we changed

**Date:** 2026-11-03
**Branch:** `feat/v2-stable-readiness`
**Scope:** a survey of the public state of the art in the areas this workbench
touches, an honest comparison with what this repository actually does, and the
one gap this cycle closes. Everything below is a reading of public sources on the
date above; no benchmark number is copied into a claim about HCS Discovery
Studio unless it was re-measured on this host.

## 1. Method

Searched for (a) GPU-accelerated molecular similarity, (b) open ADMET / property
prediction, (c) structure prediction and docking at scale, (d) GPU compute in the
browser, and (e) the benchmark conventions those fields use. The primary sources
are listed in §6. "SOTA" is used in its literal sense — the best publicly
documented result in a named benchmark — and never as a description of this
project.

## 2. What SOTA looks like, area by area

| Area | What the state of the art does | Reference points |
|---|---|---|
| Molecular similarity search | GPU kernels for Morgan generation and Tanimoto; all-to-all and k-nearest-neighbour search over 10⁶–10⁹ fingerprints; popcount bounds (BitBound) to skip comparisons; throughput quoted in Tanimotos per second, not "seconds per screen" | NVIDIA **nvMolKit** (2025): GPU Morgan + Tanimoto, up to ~4000× a single CPU core for 10k⁺ cross-Tanimoto matrices on an H100; **chemfp**: ~130M 1024-bit Tanimotos/s on one x86-64 core, k=1000 over 1.8M ChEMBL fingerprints in ~27 ms with BitBound; **molprint** (Rust, 2026): ~36 ns per 2048-bit comparison, explicitly memory-bandwidth bound |
| GPU portability | The fast similarity stacks are CUDA-only. Vendor-neutral GPU path means Vulkan/D3D12/Metal through `wgpu`, or WebGPU in the browser | nvMolKit requires a CUDA toolkit and an NVIDIA GPU; Datagrok ships **WebGPU** chemistry acceleration in a commercial web client |
| Browser chemistry | RDKit compiled to WebAssembly for parse/standardise/descriptors; WebGPU compute for the heavy inner loops; strict numerical honesty because WebGPU has no portable float64 | RDKit MinimalLib (`@rdkit/rdkit`), Datagrok Chem 1.10 (WebGPU for chem space), W3C WebGPU spec (compute pipelines, precision caveats) |
| ADMET / property prediction | Message-passing GNNs (Chemprop-RDKit and successors) on TDC endpoints; specialised small language models now reported at SOTA on 28 ADMET tasks; calibrated uncertainty is expected | Therapeutics Data Commons (TDC) as the shared benchmark; Chemprop; Insilico MMAI specialist models (2026) |
| Structure prediction | Co-folding models (Boltz-2, Chai-1, OpenFold3) run as external services or on GPU workers; they are shipped as adapters, not reimplemented | NovoMCP's open engine wires AutoDock-GPU, GROMACS and OpenFold3 behind one interface |
| Packaging and delivery | One-file desktop binaries, static web previews, container images, signed artifacts | Common practice; this repository ships wheel + one-file executable + a static SPA preview |

## 3. Where this repository stands

| Capability | Our status before this cycle | Gap to the references |
|---|---|---|
| Similarity search | RDKit `BulkTanimotoSimilarity` per row in the `chem.similarity` node; a GPU kernel existed but only as a benchmark (`hcs-discovery gpu bench`) | **Large.** The GPU kernel was not reachable from any product feature, there was no k/threshold search API, no throughput number and no vendor-neutral alternative to CUDA |
| GPU portability | Vulkan through `wgpu-py`, shared WGSL kernel, hardware adapters only | Ahead of the CUDA-only stacks on portability, behind them on scale and throughput |
| Browser chemistry | RDKit WASM for parse/descriptors, WebGPU probe, WebGPU parity benchmark (uncommitted) | Comparable in kind; no server-scale library in the browser, which is a deliberate scope choice |
| Property prediction | Reduced ESOL (RMSE 0.97, R² 0.07 on 45 compounds) and a CNS-MPO approximation | **Large and unchanged.** A GNN on TDC endpoints is not implemented; our estimate barely beats a constant baseline |
| Docking | AutoDock Vina CPU, one-complex redocking regression check | Correct but not benchmarked across targets |
| Structure prediction, MD | Registry cards marked `planned` | **Large and deliberate.** Out of scope for a local CPU workbench |
| Reproducibility and provenance | Content-hashed cache, run manifests, engine versions, hardware description | Ahead of most open tools; this is the repository's actual differentiator |

## 4. The gap this cycle closes

Of the gaps above, exactly one can be closed in a way that is verifiable on this
host, deployable to both a local backend and a browser, and honest about its
limits: **similarity search on a vendor-neutral GPU, with an exact CPU reference.**

What changed:

1. **A real search path, not a benchmark.** `hcs_discovery.similarity` turns the
   shared WGSL kernel into `tanimoto_search(...)` with k-nearest and threshold
   semantics, a resident library, chunking above the storage-buffer limit, and a
   CPU fallback. The GPU result is compared against the CPU reference on every
   search before it is returned; a mismatch raises instead of returning a number.
2. **The product uses it.** The `chem.similarity` workflow node accepts
   `engine: auto | cpu | gpu`. `auto` selects the hardware adapter when present,
   records the adapter in a run event, and includes the engine in the cache
   runtime fingerprint so a CPU result is never silently reused as a GPU result.
3. **The same capability in the browser.** The Settings page runs the same WGSL
   kernel through WebGPU against a JavaScript CPU reference over 100,000
   fingerprints and reports parity before speed.
4. **Throughput, measured.** `scripts/science/benchmark_gpu_similarity.py`
   reports Tanimotos per second against numpy and RDKit `BulkTanimotoSimilarity`
   on the named adapter, plus the parity result. The report in
   [`docs/validation/gpu-tanimoto.md`](../validation/gpu-tanimoto.md) is generated
   by that script.

What it does **not** claim:

- No comparison with nvMolKit. That library needs CUDA and an NVIDIA GPU; this
  host has neither. Quoting its H100 numbers against an integrated AMD GPU would
  be meaningless.
- No BitBound-style prefiltering yet. The kernel scans the whole library; the
  skip-based bound is the next algorithmic step, not something this cycle did.
- No GPU Morgan fingerprint *generation*. Fingerprints are still computed by
  RDKit on the CPU and the packed bit vectors are moved to the device.
- No learned ADMET, no structure prediction, no MD. Those stay `planned`, and the
  README continues to say so.

## 5. Next steps, in the order they would actually pay off

1. **Popcount-bound prefiltering (BitBound) for threshold and kNN search.** chemfp
   shows an order-of-magnitude effect on CPUs; the same bound reduces GPU work.
2. **Resident fingerprint storage per dataset.** The index is rebuilt from SMILES
   on every run; packing once into the content-addressed store would remove the
   dominant cost for large libraries.
3. **A TDC-based property model.** Chemprop-RDKit on a pinned TDC endpoint, with
   a scaffold split, a measured baseline and a bootstrap interval — the same
   evidence discipline the ESOL report already uses.
4. **A multi-target docking benchmark** (pose recovery over a fixed set) before
   any docking accuracy claim is made.

## 6. Sources

- NVIDIA Digital Biology Labs, *nvMolKit: a core set of GPU-accelerated RDKit
  functions*, 2025-09-10 — <https://research.nvidia.com/labs/dbr/blog/nvMolKit/>
- nvMolKit documentation, molecular similarity —
  <https://nvidia-bionemo.github.io/nvMolKit/similarity.html>
- A. Dalke, *The chemfp project*, Journal of Cheminformatics 11:76, 2019 —
  <https://jcheminf.biomedcentral.com/articles/10.1186/s13321-019-0398-8>
- molprint, *Similarity & Screening* (Rust implementation notes) —
  <https://mariusrueve.github.io/molprint/architecture/similarity-screening.html>
- Datagrok Chem plugin release notes (WebGPU acceleration) —
  <https://datagrok.ai/help/deploy/releases/plugins/Chem>
- W3C, *WebGPU* Candidate Recommendation Draft, 2026 —
  <https://www.w3.org/TR/2026/CRD-webgpu-20260102>
- Therapeutics Data Commons — <https://tdcommons.ai>
- Insilico Medicine, MMAI specialist models (ADMET across 28 tasks), 2026-09-02 —
  <https://insilico.com/news/tvb0jud0y1-insilico-medicine-releases-sota-mmai-spe>

Sources were read on 2026-11-03. Where a source reports a speed-up, this document
repeats the source's own conditions (hardware, baseline, matrix size) and does
not generalise them.
