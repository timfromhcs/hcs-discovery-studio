"""SQLAlchemy models for the local-first domain model.

Design notes:
- Primary keys are prefixed strings (``prj_...``) so artefacts stay self-describing.
- All timestamps are naive UTC (see ``db_now``).
- Structured payloads that are queried use columns; free-form provenance uses JSON.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from ..core.timeutil import db_now


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    purpose: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=db_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=db_now, onupdate=db_now, nullable=False)

    datasets: Mapped[list[Dataset]] = relationship(back_populates="project", cascade="all, delete-orphan")
    compounds: Mapped[list[Compound]] = relationship(back_populates="project", cascade="all, delete-orphan")
    runs: Mapped[list[Run]] = relationship(back_populates="project", cascade="all, delete-orphan")
    workflows: Mapped[list[Workflow]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Target(Base):
    __tablename__ = "targets"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    gene_symbol: Mapped[str | None] = mapped_column(String(64))
    uniprot_id: Mapped[str | None] = mapped_column(String(32))
    organism: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=db_now, nullable=False)


class Structure(Base):
    __tablename__ = "structures"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    target_id: Mapped[str | None] = mapped_column(ForeignKey("targets.id", ondelete="SET NULL"))
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    accession: Mapped[str | None] = mapped_column(String(64))
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    rel_path: Mapped[str] = mapped_column(String(400), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    quality: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=db_now, nullable=False)


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_format: Mapped[str] = mapped_column(String(16), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    imported_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500))
    license: Mapped[str] = mapped_column(String(120), default="unknown", nullable=False)
    transformation_log: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    column_mapping: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=db_now, nullable=False)

    project: Mapped[Project] = relationship(back_populates="datasets")
    rows: Mapped[list[DatasetRow]] = relationship(back_populates="dataset", cascade="all, delete-orphan")


class DatasetRow(Base):
    __tablename__ = "dataset_rows"
    __table_args__ = (Index("ix_dataset_rows_dataset_status", "dataset_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    raw: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    compound_id: Mapped[str | None] = mapped_column(String(40))

    dataset: Mapped[Dataset] = relationship(back_populates="rows")


class Compound(Base):
    __tablename__ = "compounds"
    __table_args__ = (Index("ix_compounds_project_canonical", "project_id", "canonical_smiles"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    dataset_id: Mapped[str | None] = mapped_column(ForeignKey("datasets.id", ondelete="SET NULL"), index=True)
    source_row_index: Mapped[int | None] = mapped_column(Integer)
    source_id: Mapped[str | None] = mapped_column(String(120), index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    input_smiles: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_smiles: Mapped[str] = mapped_column(Text, nullable=False)
    isomeric_smiles: Mapped[str] = mapped_column(Text, nullable=False)
    inchi: Mapped[str | None] = mapped_column(Text)
    inchikey: Mapped[str | None] = mapped_column(String(64), index=True)
    formula: Mapped[str | None] = mapped_column(String(200))
    formal_charge: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=db_now, nullable=False)

    project: Mapped[Project] = relationship(back_populates="compounds")


class Workflow(Base):
    __tablename__ = "workflows"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_workflow_project_name"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=db_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=db_now, onupdate=db_now, nullable=False)

    project: Mapped[Project] = relationship(back_populates="workflows")


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (Index("ix_runs_status_created", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    workflow_id: Mapped[str | None] = mapped_column(ForeignKey("workflows.id", ondelete="SET NULL"))
    dataset_id: Mapped[str | None] = mapped_column(ForeignKey("datasets.id", ondelete="SET NULL"))
    workflow_name: Mapped[str] = mapped_column(String(200), nullable=False)
    workflow_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    workflow_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="queued", nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    seed: Mapped[int | None] = mapped_column(Integer)
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String(120))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=db_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    project: Mapped[Project] = relationship(back_populates="runs")
    nodes: Mapped[list[RunNode]] = relationship(back_populates="run", cascade="all, delete-orphan")


class RunNode(Base):
    __tablename__ = "run_nodes"
    __table_args__ = (UniqueConstraint("run_id", "node_id", name="uq_run_node"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    node_id: Mapped[str] = mapped_column(String(64), nullable=False)
    node_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    progress: Mapped[float | None] = mapped_column(Float)
    cache_key: Mapped[str | None] = mapped_column(String(64))
    cached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    run: Mapped[Run] = relationship(back_populates="nodes")


class RunEvent(Base):
    __tablename__ = "run_events"
    __table_args__ = (UniqueConstraint("run_id", "seq", name="uq_run_event_seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime, default=db_now, nullable=False)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    level: Mapped[str] = mapped_column(String(10), default="info", nullable=False)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    node_id: Mapped[str | None] = mapped_column(String(64))
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class RunResult(Base):
    __tablename__ = "run_results"
    __table_args__ = (Index("ix_run_results_run_rank", "run_id", "rank"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    compound_id: Mapped[str] = mapped_column(String(40), nullable=False)
    rank: Mapped[int | None] = mapped_column(Integer)
    composite_score: Mapped[float | None] = mapped_column(Float)
    pareto_front: Mapped[int | None] = mapped_column(Integer)
    rejected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (Index("ix_predictions_compound_endpoint", "compound_id", "endpoint"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    node_id: Mapped[str] = mapped_column(String(64), nullable=False)
    compound_id: Mapped[str] = mapped_column(String(40), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(40))
    score_direction: Mapped[str | None] = mapped_column(String(16))
    method: Mapped[str] = mapped_column(String(120), nullable=False)
    method_version: Mapped[str] = mapped_column(String(40), nullable=False)
    uncertainty: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=db_now, nullable=False)


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (UniqueConstraint("run_id", "rel_path", name="uq_artifact_path"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    node_id: Mapped[str | None] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    rel_path: Mapped[str] = mapped_column(String(400), nullable=False)
    media_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=db_now, nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=db_now, nullable=False)
    actor: Mapped[str] = mapped_column(String(80), default="local", nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    object_type: Mapped[str] = mapped_column(String(40), nullable=False)
    object_id: Mapped[str | None] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(20), default="ok", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
