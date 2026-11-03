"""Persist packed fingerprints per dataset so a search does not re-fingerprint.

Fingerprinting is the dominant cost of a similarity search over an imported library,
and the same dataset is searched repeatedly. This service stores the packed Morgan
fingerprints once and rebuilds them only when the compound set changes or the stored
bytes no longer match their checksum.

Correctness rules, all covered by tests:

- compounds are read in a stable order (``ORDER BY id``) and the stored compound ids
  are returned with the matrix, so hit indices always map back to the right row;
- a checksum over ``id<TAB>smiles`` lines detects an added, removed or edited
  compound;
- a checksum over the packed bytes detects a truncated or tampered blob;
- only radius 2 / 2048 bits have a kernel; other shapes are a validation error
  instead of a silent CPU fallback.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import NotFoundError, ValidationError
from ..core.hashing import sha256_text
from ..database.models import Compound, Dataset, DatasetFingerprints
from ..gpu.fingerprints import BITS, RADIUS, WORDS, pack_smiles

__all__ = ["DatasetFingerprintSet", "fingerprint_cache_stats", "load_dataset_fingerprints"]


@dataclass(frozen=True)
class DatasetFingerprintSet:
    packed: np.ndarray
    compound_ids: list[str]
    checksum: str
    compounds_checksum: str
    cached: bool
    radius: int
    bits: int

    @property
    def count(self) -> int:
        return int(self.packed.shape[0])


def _checksum_bytes(packed: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(packed, dtype="<u4").tobytes()).hexdigest()


def load_dataset_fingerprints(
    session: Session,
    dataset_id: str,
    *,
    radius: int = RADIUS,
    bits: int = BITS,
) -> DatasetFingerprintSet:
    """Return the packed fingerprint matrix for a dataset, building it on first use."""
    if (radius, bits) != (RADIUS, BITS):
        raise ValidationError(
            "Only Morgan/ECFP radius 2 with 2048 bits is supported by the kernel.",
            details={"radius": radius, "bits": bits},
        )
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise NotFoundError("Dataset not found.", details={"dataset_id": dataset_id})
    rows = session.execute(
        select(Compound.id, Compound.isomeric_smiles).where(Compound.dataset_id == dataset_id).order_by(Compound.id)
    ).all()
    if not rows:
        raise ValidationError("The dataset has no compounds to fingerprint.", details={"dataset_id": dataset_id})
    compound_ids = [str(row.id) for row in rows]
    compounds_checksum = sha256_text("\n".join(f"{row.id}\t{row.isomeric_smiles}" for row in rows))

    existing = session.execute(
        select(DatasetFingerprints).where(DatasetFingerprints.dataset_id == dataset_id)
    ).scalar_one_or_none()
    if (
        existing is not None
        and existing.radius == radius
        and existing.bits == bits
        and existing.compound_count == len(compound_ids)
        and existing.compounds_checksum == compounds_checksum
    ):
        blob = bytes(existing.packed)
        if len(blob) == len(compound_ids) * WORDS * 4 and hashlib.sha256(blob).hexdigest() == existing.checksum:
            packed = np.frombuffer(blob, dtype="<u4").reshape(len(compound_ids), WORDS).astype(np.uint32, copy=True)
            return DatasetFingerprintSet(
                packed=packed,
                compound_ids=compound_ids,
                checksum=existing.checksum,
                compounds_checksum=compounds_checksum,
                cached=True,
                radius=radius,
                bits=bits,
            )

    packed, _valid = pack_smiles([row.isomeric_smiles for row in rows])
    checksum = _checksum_bytes(packed)
    blob = np.ascontiguousarray(packed, dtype="<u4").tobytes()
    if existing is None:
        existing = DatasetFingerprints(
            id=f"dfp_{hashlib.sha256(dataset_id.encode()).hexdigest()[:20]}",
            dataset_id=dataset_id,
        )
        session.add(existing)
    existing.radius = radius
    existing.bits = bits
    existing.compound_count = len(compound_ids)
    existing.compounds_checksum = compounds_checksum
    existing.checksum = checksum
    existing.packed = blob
    session.commit()
    return DatasetFingerprintSet(
        packed=packed,
        compound_ids=compound_ids,
        checksum=checksum,
        compounds_checksum=compounds_checksum,
        cached=False,
        radius=radius,
        bits=bits,
    )


def fingerprint_cache_stats(session: Session) -> dict[str, int]:
    from sqlalchemy import func

    entries = int(session.execute(select(func.count()).select_from(DatasetFingerprints)).scalar() or 0)
    total = session.execute(select(func.coalesce(func.sum(DatasetFingerprints.compound_count), 0))).scalar()
    compounds = int(total or 0)
    return {"entries": entries, "compounds": compounds}
