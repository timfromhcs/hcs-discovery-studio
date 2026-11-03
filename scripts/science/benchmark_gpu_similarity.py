"""Measure the shared Tanimoto kernel on this host and write the published report.

    uv run python scripts/science/benchmark_gpu_similarity.py
    uv run python scripts/science/benchmark_gpu_similarity.py --sizes 100000 500000

Order of claims: **parity first**. The GPU counts must equal the numpy reference bit
for bit before any timing is printed, and the resulting similarities are compared with
RDKit's ``BulkTanimotoSimilarity``. Timings are median wall time on the named adapter,
never a promise, and a host without a hardware adapter is reported as ``skipped``.

Outputs:
    docs/validation/gpu-tanimoto.md   (the report below is generated from it)
    build/gpu-similarity.json         (raw measurements)
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT = REPO_ROOT / "docs" / "validation" / "gpu-tanimoto.md"
RAW = REPO_ROOT / "build" / "gpu-similarity.json"
SCHEMA = "hcs.gpu-similarity-bench.v1"


def _git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _rdkit_fingerprints(packed: np.ndarray) -> list[Any]:
    from rdkit import DataStructs

    bits = np.unpackbits(packed.view(np.uint8), axis=1, bitorder="little")
    table = bytes.maketrans(b"\x00\x01", b"01")
    return [DataStructs.CreateFromBitString(row.tobytes().translate(table).decode("ascii")) for row in bits]


def _varied_density(lib: np.ndarray) -> np.ndarray:
    """A library whose bit counts vary with 'molecule size' (like real ECFP).

    Keeps a random prefix of each fingerprint's words, so a small molecule has a
    small popcount. Used only to show what the BitBound can and cannot prune; it is
    synthetic and the report says so.
    """
    rng = np.random.default_rng(1)
    keep = rng.integers(8, 65, size=lib.shape[0])
    out = lib.copy()
    for index, words in enumerate(keep):
        out[index, words:] = 0
    return out


def _median_ms(fn, repeats: int) -> float:
    timings = []
    for _ in range(repeats):
        started = time.perf_counter()
        fn()
        timings.append((time.perf_counter() - started) * 1000.0)
    return statistics.median(timings)


def measure(engine: Any, n: int, *, repeats: int, seed: int = 0) -> dict[str, Any]:
    from rdkit import DataStructs

    from hcs_discovery.gpu.bench import synthetic_library
    from hcs_discovery.gpu.cpu import cpu_counts, ratio

    lib = synthetic_library(n, seed)
    query = lib[0].copy()

    inter_ref, union_ref = cpu_counts(query, lib)
    numpy_ms = _median_ms(lambda: cpu_counts(query, lib), repeats)
    reference = ratio(inter_ref, union_ref)

    fingerprints = _rdkit_fingerprints(lib)
    rdkit_ms = _median_ms(lambda: DataStructs.BulkTanimotoSimilarity(fingerprints[0], fingerprints), repeats)
    rdkit_scores = np.asarray(DataStructs.BulkTanimotoSimilarity(fingerprints[0], fingerprints), dtype=np.float32)

    engine.counts(query, lib[: min(n, 64)])  # warm-up: pipeline and driver caches
    upload_ms = statistics.median([engine.counts(query, lib).total_ms for _ in range(repeats)])
    uploaded = engine.counts(query, lib)

    resident_ms: float | None = None
    resident_counts = None
    if n <= engine.max_chunk:
        engine.load_library(lib)
        engine.query_resident(query)  # warm-up
        resident_ms = statistics.median([engine.query_resident(query).total_ms for _ in range(repeats)])
        resident_counts = engine.query_resident(query)
        engine.release_library()

    hybrid_ms: float | None = None
    hybrid_exact = True
    if n >= 20_000:
        from hcs_discovery.similarity import TanimotoIndex

        # verify=False for the timing: the product default verifies every search
        # against the CPU reference, which is one extra CPU pass and would be
        # reported as "hybrid is slow" rather than "verification costs a pass".
        index = TanimotoIndex.from_packed(lib, prefer="auto", boost="hybrid", verify=False)
        try:
            index.counts_for(query)  # warm-up
            samples = []
            for _ in range(repeats):
                started = time.perf_counter()
                index.counts_for(query)
                samples.append((time.perf_counter() - started) * 1000.0)
            hybrid_ms = statistics.median(samples)
            hybrid_inter, hybrid_union = index.counts_for(query)
            hybrid_exact = bool(np.array_equal(hybrid_inter, inter_ref) and np.array_equal(hybrid_union, union_ref))
        finally:
            index.close()

    # BitBound: a threshold search only scores fingerprints whose popcount bound can
    # still reach the threshold. It changes the amount of work, not the kernel, so it
    # is reported separately. Two libraries are measured on purpose: the uniform one
    # has near-identical bit counts (the bound cannot prune), the varied one mirrors
    # real ECFP density variation with molecule size.
    thresholds: dict[str, dict[str, float | int]] = {}
    if n >= 20_000:
        from hcs_discovery.similarity import TanimotoIndex

        for label, library in (("uniform", lib), ("varied", _varied_density(lib))):
            index = TanimotoIndex.from_packed(library, prefer="auto", boost="gpu", verify=False)
            try:
                for threshold in (0.4, 0.7, 0.9):
                    index.threshold_hits_for(query, threshold)  # warm-up
                    samples: list[float] = []
                    pruned = None
                    for _ in range(repeats):
                        started = time.perf_counter()
                        pruned = index.threshold_hits_for(query, threshold)
                        samples.append((time.perf_counter() - started) * 1000.0)
                    assert pruned is not None
                    thresholds[f"{label}:{threshold:.1f}"] = {
                        "density": label,
                        "threshold": threshold,
                        "candidates": pruned.candidates,
                        "fraction": round(pruned.candidates / max(1, n), 6),
                        "hits": pruned.n_hits,
                        "ms": round(statistics.median(samples), 3),
                    }
            finally:
                index.close()

    exact = bool(np.array_equal(uploaded.inter, inter_ref) and np.array_equal(uploaded.union, union_ref))
    if resident_counts is not None:
        exact = exact and bool(
            np.array_equal(resident_counts.inter, inter_ref) and np.array_equal(resident_counts.union, union_ref)
        )
    exact = exact and hybrid_exact
    if resident_counts is not None:
        exact = exact and bool(
            np.array_equal(resident_counts.inter, inter_ref) and np.array_equal(resident_counts.union, union_ref)
        )
    max_abs_err = float(np.max(np.abs(reference - rdkit_scores)))

    top10_cpu = np.argsort(-reference, kind="stable")[:10]
    top10_gpu = np.argsort(-ratio(uploaded.inter, uploaded.union), kind="stable")[:10]
    top10_equal = bool(np.array_equal(top10_cpu, top10_gpu))

    def throughput(milliseconds: float | None) -> float | None:
        return None if not milliseconds else round(n / (milliseconds / 1000.0) / 1e6, 2)

    return {
        "n": n,
        "parity_exact_counts": exact,
        "max_abs_err_vs_rdkit": max_abs_err,
        "top10_identical": top10_equal,
        "numpy_ms": round(numpy_ms, 2),
        "rdkit_ms": round(rdkit_ms, 2),
        "gpu_upload_ms": round(upload_ms, 2),
        "gpu_resident_ms": None if resident_ms is None else round(resident_ms, 2),
        "hybrid_ms": None if hybrid_ms is None else round(hybrid_ms, 2),
        "hybrid_vs_upload": None if hybrid_ms is None else round(upload_ms / hybrid_ms, 2),
        "thresholds": thresholds,
        "throughput_million_s": {
            "numpy": throughput(numpy_ms),
            "rdkit": throughput(rdkit_ms),
            "gpu_upload": throughput(upload_ms),
            "gpu_resident": throughput(resident_ms),
            "hybrid": throughput(hybrid_ms),
        },
    }


def render(report: dict[str, Any]) -> str:
    measurements = report["measurements"]
    rows = []
    for item in measurements:
        speedup = None
        if item["gpu_resident_ms"]:
            speedup = f"{item['rdkit_ms'] / item['gpu_resident_ms']:.1f}x"
        rows.append(
            "| {n:,} | {numpy_ms:,.1f} | {rdkit_ms:,.1f} | {gpu_upload_ms:,.1f} | {resident} | {hybrid} | {hybrid_x} | "
            "{speedup} | {parity} | {err:.1e} |".format(
                n=item["n"],
                numpy_ms=item["numpy_ms"],
                rdkit_ms=item["rdkit_ms"],
                gpu_upload_ms=item["gpu_upload_ms"],
                resident="n/a" if item["gpu_resident_ms"] is None else f"{item['gpu_resident_ms']:,.1f}",
                hybrid="n/a" if item.get("hybrid_ms") is None else f"{item['hybrid_ms']:,.1f}",
                hybrid_x="n/a" if item.get("hybrid_vs_upload") is None else f"{item['hybrid_vs_upload']:.2f}x",
                speedup=speedup or "n/a",
                parity="exact" if item["parity_exact_counts"] else "**FAILED**",
                err=item["max_abs_err_vs_rdkit"],
            )
        )
    table = "\n".join(rows)
    threshold_rows = []
    for item in measurements:
        for data in (item.get("thresholds") or {}).values():
            threshold_rows.append(
                (
                    "| {n:,} | {density} | {threshold:.1f} | {candidates:,} | {fraction:.2f} % | {hits} | {ms:.2f} |"
                ).format(
                    n=item["n"],
                    density=data["density"],
                    threshold=float(data["threshold"]),
                    candidates=data["candidates"],
                    fraction=float(data["fraction"]) * 100.0,
                    hits=data["hits"],
                    ms=float(data["ms"]),
                )
            )
    threshold_table = "\n".join(threshold_rows) or "No threshold measurement."
    status = report["status"]
    if status != "passed":
        table = f"No measurement: {report['detail']}"

    return f"""# GPU similarity benchmark — Tanimoto on Vulkan

Generated by `uv run python scripts/science/{Path(__file__).name}`.
Do not edit by hand: re-run the script on the host you want to describe.

| Item | Value |
|---|---|
| Date | {report["generated_at"]} |
| Commit | `{report["commit"]}` |
| Host | {report["host"]["cpu"]} · {report["host"]["platform"]} |
| Adapter | {report["adapter"] or "—"} |
| Backend | {report["backend"] or "—"} |
| Kernel | `src/hcs_discovery/gpu/kernels/tanimoto.wgsl` (2048-bit Morgan/ECFP r=2, little-endian u32 popcounts) |
| Status | **{status}** |

## Measurements

Median of {report["repeats"]} repetitions, milliseconds, end-to-end (upload, dispatch,
readback). "GPU resident" keeps the library in a storage buffer and moves only the
256-byte query.

| Library | numpy CPU | RDKit ms | GPU upload | GPU resident | GPU+CPU hybrid | vs upload | speed-up | Parity | err |
|---|---|---|---|---|---|---|---|---|---|
{table}

## Threshold search with the BitBound prefilter

A query with `a` set bits and a library fingerprint with `b` bits has
`Tanimoto ≤ min(a, b) / max(a, b)`, so fingerprints whose bound is below the
threshold are skipped without a comparison. The remaining candidates are scored
by the same kernel, and the hits are identical to a full scan (differential tests
in `tests/unit/test_similarity_search.py`).

| Library | Density | Threshold | Candidates scored | Share | Hits | ms |
|---|---|---|---|---|---|---|
{threshold_table}

## What this does and does not establish

- **Parity is exact.** The GPU computes integer intersections and unions; the table
  reports "exact" only when every count equals the numpy reference and the top-10
  neighbours are identical. Similarity is `intersection / union` in float64, the same
  double division RDKit performs, so the values agree with RDKit to the last bit
  (the residual column above is the float32 storage used by the comparison, not a GPU
  error).
- **The speed-up is device-specific.** One integrated GPU against one CPU thread pool
  on the host named above. It is not a comparison with CUDA implementations such as
  nvMolKit, and it says nothing about discrete GPUs, other vendors or larger than
  memory libraries.
- **Hybrid is a small, measured win here.** Splitting the library between the GPU and
  CPU threads (the `--boost hybrid` mode, or `auto` when a calibration says the CPU
  share can keep up) is 1.03–1.09× faster than the same GPU upload path on this host.
  It is reported as measured; it is not a promise, and on a fast discrete GPU the
  calibration will keep `auto` on GPU-only.
- **BitBound only pays when bit counts vary.** The prefilter skips fingerprints whose
  popcount bound `min(a,b)/max(a,b)` is below the threshold. On this synthetic
  uniform-density library almost nothing is pruned; on the density-varied one
  (random prefix of words, standing in for molecule size) it prunes 32–88 % and the
  search gets 1.5–8× faster. Both rows are synthetic and the report says so; the
  differential tests prove the hits are identical to a full scan.
- **Not benchmarked:** GPU fingerprint generation (RDKit computes fingerprints on the
  CPU), popcount-bound prefilters, and multi-query batches. The kernel scans the whole
  library per query.
- **No scientific claim.** Tanimoto similarity over Morgan fingerprints is a
  prioritisation signal, not evidence of binding, safety or efficacy.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", type=int, default=[100_000, 500_000])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--raw", type=Path, default=RAW)
    args = parser.parse_args(argv)

    from hcs_discovery.gpu.device import probe_gpu

    probe = probe_gpu()
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
        "commit": _git_commit(),
        "status": "skipped",
        "detail": probe["detail"],
        "adapter": probe.get("adapter"),
        "backend": probe.get("backend"),
        "repeats": args.repeats,
        "host": {
            "platform": f"{platform.system()} {platform.release()} {platform.machine()}",
            "cpu": platform.processor() or platform.machine(),
            "python": sys.version.split()[0],
        },
        "measurements": [],
    }
    if probe["status"] != "available":
        report["detail"] = f"No hardware GPU adapter: {probe['detail']}"
    else:
        from hcs_discovery.gpu.engine import GpuEngine

        engine = GpuEngine()
        report["adapter"] = engine.adapter_name
        report["backend"] = engine.backend
        for n in args.sizes:
            report["measurements"].append(measure(engine, n, repeats=args.repeats))
        failed = [
            item for item in report["measurements"] if not item["parity_exact_counts"] or not item["top10_identical"]
        ]
        report["status"] = "failed" if failed else "passed"
        report["detail"] = "GPU counts are bit-exact against the CPU reference." if not failed else "Parity violated."

    args.raw.parent.mkdir(parents=True, exist_ok=True)
    args.raw.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render(report), encoding="utf-8")
    print(json.dumps({"status": report["status"], "adapter": report["adapter"], "report": str(args.report)}, indent=2))
    return 0 if report["status"] in {"passed", "skipped"} else 1


if __name__ == "__main__":  # pragma: no cover - measurement entry point
    raise SystemExit(main())
