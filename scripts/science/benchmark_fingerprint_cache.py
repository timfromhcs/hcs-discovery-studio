"""Measure what the dataset fingerprint cache saves.

The claim "the cache avoids re-fingerprinting" is only worth something with a
number. This script builds a throwaway database with a synthetic library, then times:

1. ``pack_smiles`` alone (what a cold search does every time),
2. the first ``load_dataset_fingerprints`` (fingertips + checksums + store),
3. the second call (checksum verify + blob read).

The library is synthetic and the report says so. Run from the repository root:

    uv run python scripts/science/benchmark_fingerprint_cache.py
    uv run python scripts/science/benchmark_fingerprint_cache.py --compounds 20000
"""

from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from hcs_discovery.database.models import Base, Compound, Dataset, Project
from hcs_discovery.gpu.fingerprints import pack_smiles
from hcs_discovery.services import load_dataset_fingerprints

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW = REPO_ROOT / "build" / "fingerprint-cache.json"

BASE = [
    "c1ccccc1",
    "CC(=O)Oc1ccccc1C(=O)O",
    "CCO",
    "CCN",
    "CN1CCC[C@H]1c1cccnc1",
    "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
    "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
    "c1ccc2c(c1)cc[nH]2",
    "COc1ccc2[nH]cc(CCNC(C)=O)c2c1",
    "CC1=CC=C(C=C1)S(=O)(=O)N",
]


def build_library(session: Session, n: int) -> None:
    project = Project(id="prj_bench", name="fingerprint cache benchmark", description="synthetic")
    dataset = Dataset(
        id="dts_bench",
        project_id=project.id,
        name="synthetic library",
        source_format="csv",
        original_filename="benchmark.csv",
        sha256="0" * 64,
        record_count=n,
        imported_count=n,
        error_count=0,
        column_mapping={},
        transformation_log=[],
    )
    session.add_all([project, dataset])
    session.flush()
    session.add_all(
        Compound(
            id=f"cmp_{index:06d}",
            project_id=project.id,
            dataset_id=dataset.id,
            source_row_index=index,
            name=f"compound {index}",
            input_smiles=BASE[index % len(BASE)],
            canonical_smiles=BASE[index % len(BASE)],
            isomeric_smiles=BASE[index % len(BASE)],
            formal_charge=0,
            warnings=[],
        )
        for index in range(n)
    )
    session.commit()


def median_ms(fn, repeats: int) -> float:
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - started) * 1000.0)
    return statistics.median(samples)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compounds", type=int, default=5_000)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--raw", type=Path, default=RAW)
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="hcs-fpbench-") as directory:
        database = Path(directory) / "bench.sqlite3"
        engine = create_engine(f"sqlite:///{database.as_posix()}")
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine)
        smiles = [BASE[index % len(BASE)] for index in range(args.compounds)]

        with factory() as session:
            build_library(session, args.compounds)

        cold_ms = median_ms(lambda: pack_smiles(smiles), args.repeats)

        with factory() as session:
            first_started = time.perf_counter()
            first = load_dataset_fingerprints(session, "dts_bench")
            first_ms = (time.perf_counter() - first_started) * 1000.0
        with factory() as session:
            second_ms = median_ms(lambda: load_dataset_fingerprints(session, "dts_bench"), args.repeats)
            second = load_dataset_fingerprints(session, "dts_bench")
        engine.dispose()

    report = {
        "schema": "hcs.fingerprint-cache-bench.v1",
        "compounds": args.compounds,
        "repeats": args.repeats,
        "library": "synthetic (10 base SMILES cycled)",
        "cold_fingerprint_ms": round(cold_ms, 2),
        "first_load_ms": round(first_ms, 2),
        "cached_load_ms": round(second_ms, 2),
        "speedup_cached_vs_cold": round(cold_ms / second_ms, 1) if second_ms else None,
        "first_cached_flag": first.cached,
        "second_cached_flag": second.cached,
        "checksum_stable": first.checksum == second.checksum,
    }
    args.raw.parent.mkdir(parents=True, exist_ok=True)
    args.raw.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover - measurement entry point
    raise SystemExit(main())
