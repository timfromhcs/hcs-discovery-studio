"""Target and structure services.

These activate the reserved ``targets`` and ``structures`` tables with the minimum
needed for a defensible docking setup: a target identity with provenance, a
structure file with a checksum and source, and an inspection of what the file
actually contains.

Nothing here prepares a receptor, strips a cofactor or guesses protonation. Those
are separate, explicit steps; this layer stores what was imported and says what it
found, including the warnings.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.config import Settings, get_settings
from ..core.errors import ConflictError, NotFoundError, ValidationError
from ..core.hashing import new_id
from ..core.paths import safe_filename, safe_join
from ..database.models import Structure, Target
from ..structures.pdb import MAX_STRUCTURE_BYTES, detect_format, inspect_pdb
from .projects import audit, get_project

MAX_NAME = 200
MAX_NOTES = 10_000


def create_target(
    session: Session,
    *,
    project_id: str,
    name: str,
    gene_symbol: str | None = None,
    uniprot_id: str | None = None,
    organism: str | None = None,
    notes: str = "",
    provenance: dict[str, Any] | None = None,
) -> Target:
    get_project(session, project_id)
    name = (name or "").strip()
    if not name:
        raise ValidationError("Target name must not be empty.")
    if len(name) > MAX_NAME:
        raise ValidationError(f"Target name is too long (max {MAX_NAME} characters).")
    if len(notes) > MAX_NOTES:
        raise ValidationError(f"Target notes are too long (max {MAX_NOTES} characters).")

    duplicate = session.execute(
        select(Target).where(Target.project_id == project_id, func.lower(Target.name) == name.lower())
    ).scalar_one_or_none()
    if duplicate is not None:
        raise ConflictError(f"A target named '{name}' already exists in this project.")

    target = Target(
        id=new_id("tgt"),
        project_id=project_id,
        name=name,
        gene_symbol=(gene_symbol or "").strip() or None,
        uniprot_id=(uniprot_id or "").strip().upper() or None,
        organism=(organism or "").strip() or None,
        notes=notes.strip(),
        provenance=dict(provenance or {}),
    )
    session.add(target)
    audit(session, "target.create", "target", target.id, {"name": name})
    session.commit()
    session.refresh(target)
    return target


def list_targets(session: Session, project_id: str) -> list[dict[str, Any]]:
    get_project(session, project_id)
    structure_counts = dict(
        session.execute(
            select(Structure.target_id, func.count(Structure.id))
            .where(Structure.project_id == project_id)
            .group_by(Structure.target_id)
        ).all()
    )
    targets = (
        session.execute(select(Target).where(Target.project_id == project_id).order_by(Target.created_at.desc()))
        .scalars()
        .all()
    )
    return [{**_target_dict(target), "structure_count": int(structure_counts.get(target.id, 0))} for target in targets]


def get_target(session: Session, target_id: str) -> Target:
    target = session.get(Target, target_id)
    if target is None:
        raise NotFoundError(f"Target '{target_id}' does not exist.")
    return target


def target_detail(session: Session, target_id: str) -> dict[str, Any]:
    target = get_target(session, target_id)
    structures = (
        session.execute(select(Structure).where(Structure.target_id == target.id).order_by(Structure.created_at.desc()))
        .scalars()
        .all()
    )
    return {
        **_target_dict(target),
        "structures": [_structure_dict(structure) for structure in structures],
    }


def update_target(
    session: Session,
    target_id: str,
    *,
    name: str | None = None,
    gene_symbol: str | None = None,
    uniprot_id: str | None = None,
    organism: str | None = None,
    notes: str | None = None,
) -> Target:
    target = get_target(session, target_id)
    if name is not None:
        cleaned = name.strip()
        if not cleaned:
            raise ValidationError("Target name must not be empty.")
        clash = session.execute(
            select(Target).where(
                Target.project_id == target.project_id,
                func.lower(Target.name) == cleaned.lower(),
                Target.id != target.id,
            )
        ).scalar_one_or_none()
        if clash is not None:
            raise ConflictError(f"A target named '{cleaned}' already exists in this project.")
        target.name = cleaned[:MAX_NAME]
    if gene_symbol is not None:
        target.gene_symbol = gene_symbol.strip() or None
    if uniprot_id is not None:
        target.uniprot_id = uniprot_id.strip().upper() or None
    if organism is not None:
        target.organism = organism.strip() or None
    if notes is not None:
        if len(notes) > MAX_NOTES:
            raise ValidationError(f"Target notes are too long (max {MAX_NOTES} characters).")
        target.notes = notes.strip()
    audit(session, "target.update", "target", target.id, {"name": target.name})
    session.commit()
    session.refresh(target)
    return target


def delete_target(session: Session, target_id: str, *, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    target = get_target(session, target_id)
    structures = session.execute(select(Structure).where(Structure.target_id == target.id)).scalars().all()
    # Deleting a target keeps its structures but detaches them (ON DELETE SET NULL).
    for structure in structures:
        structure.target_id = None
    removed = {"id": target.id, "name": target.name, "detached_structures": len(structures)}
    audit(session, "target.delete", "target", target_id, removed)
    session.delete(target)
    session.commit()
    return removed


def import_structure(
    session: Session,
    *,
    project_id: str,
    filename: str,
    data: bytes,
    target_id: str | None = None,
    source: str = "upload",
    accession: str | None = None,
    license: str = "unknown",
    settings: Settings | None = None,
) -> Structure:
    """Store a structure file, hash it, and record what it contains.

    The file is inspected *before* the database row is written, so a rejected file
    leaves neither a row nor a stray artifact.
    """
    settings = settings or get_settings()
    get_project(session, project_id)
    if target_id is not None:
        target = get_target(session, target_id)
        if target.project_id != project_id:
            raise ValidationError("The target belongs to a different project.")
    if not data:
        raise ValidationError("The structure file is empty.")
    if len(data) > MAX_STRUCTURE_BYTES:
        raise ValidationError(
            f"The structure file is too large ({len(data)} bytes).",
            details={"size_bytes": len(data), "limit_bytes": MAX_STRUCTURE_BYTES},
        )
    fmt = detect_format(filename)
    if not source or len(source) > 80:
        raise ValidationError("Source must be a short non-empty label (max 80 characters).")

    structure_id = new_id("str")
    upload_dir = safe_join(settings.uploads_dir, project_id, "structures")
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored = upload_dir / f"{structure_id}-{safe_filename(filename, fallback='structure.pdb')}"
    stored.write_bytes(data)

    try:
        inspection = inspect_pdb(stored, filename=filename)
    except Exception:
        stored.unlink(missing_ok=True)
        raise

    digest = hashlib.sha256(data).hexdigest()
    structure = Structure(
        id=structure_id,
        project_id=project_id,
        target_id=target_id,
        source=source,
        accession=(accession or "").strip() or None,
        format=fmt,
        rel_path=stored.relative_to(settings.data_dir).as_posix(),
        sha256=digest,
        quality=inspection.as_dict(),
    )
    session.add(structure)
    audit(
        session,
        "structure.import",
        "structure",
        structure_id,
        {"target_id": target_id, "source": source, "sha256": digest, "license": license},
    )
    session.commit()
    session.refresh(structure)
    return structure


def list_structures(session: Session, project_id: str) -> list[dict[str, Any]]:
    get_project(session, project_id)
    structures = (
        session.execute(
            select(Structure).where(Structure.project_id == project_id).order_by(Structure.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [_structure_dict(structure) for structure in structures]


def get_structure(session: Session, structure_id: str) -> Structure:
    structure = session.get(Structure, structure_id)
    if structure is None:
        raise NotFoundError(f"Structure '{structure_id}' does not exist.")
    return structure


def structure_detail(session: Session, structure_id: str) -> dict[str, Any]:
    structure = get_structure(session, structure_id)
    return _structure_dict(structure, include_inspection=True)


def structure_path(structure: Structure, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return safe_join(settings.data_dir, structure.rel_path)


def delete_structure(session: Session, structure_id: str, *, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    structure = get_structure(session, structure_id)
    path = structure_path(structure, settings)
    path.unlink(missing_ok=True)
    removed = {"id": structure.id, "sha256": structure.sha256, "file_removed": True}
    audit(session, "structure.delete", "structure", structure_id, removed)
    session.delete(structure)
    session.commit()
    return removed


def copy_structure_to(structure: Structure, destination: Path, settings: Settings | None = None) -> Path:
    """Copy a stored structure to a caller-chosen path (export/preparation hand-off)."""
    source = structure_path(structure, settings)
    if not source.exists():
        raise NotFoundError(
            f"The file for structure '{structure.id}' is missing on disk.",
            details={"rel_path": structure.rel_path},
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def _target_dict(target: Target) -> dict[str, Any]:
    return {
        "id": target.id,
        "project_id": target.project_id,
        "name": target.name,
        "gene_symbol": target.gene_symbol,
        "uniprot_id": target.uniprot_id,
        "organism": target.organism,
        "notes": target.notes,
        "provenance": dict(target.provenance or {}),
        "created_at": target.created_at.isoformat() + "Z",
    }


def _structure_dict(structure: Structure, *, include_inspection: bool = True) -> dict[str, Any]:
    payload = {
        "id": structure.id,
        "project_id": structure.project_id,
        "target_id": structure.target_id,
        "source": structure.source,
        "accession": structure.accession,
        "format": structure.format,
        "sha256": structure.sha256,
        "created_at": structure.created_at.isoformat() + "Z",
        "summary": {
            key: (structure.quality or {}).get(key)
            for key in ("pdb_id", "title", "atom_count", "model_count", "waters", "ligands", "warnings")
        },
    }
    if include_inspection:
        payload["inspection"] = dict(structure.quality or {})
    return payload
