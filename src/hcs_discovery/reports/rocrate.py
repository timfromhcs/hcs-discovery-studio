"""RO-Crate export: run provenance as machine-readable JSON-LD in a ZIP.

The crate follows RO-Crate 1.1 and maps the run to W3C PROV terms
(``CreateAction``, ``prov:Activity``, ``prov:Plan``, ``File``). It does not claim
conformance to the Workflow Run RO-Crate profile: that profile requires fields this
export does not yet emit (for example per-step actions), and claiming it without the
validator would be worse than saying what is actually there.

Every artifact is copied from the run directory, checksummed and listed. A missing
artifact aborts the export instead of producing a crate that references a file nobody
can open.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from .. import CREDIT, PRODUCT_NAME, __version__
from ..core.config import Settings
from ..core.errors import NotFoundError
from ..core.paths import safe_join
from .render import CAVEAT, load_report_data

RO_CRATE_CONTEXT = "https://w3id.org/ro/crate/1.1/context"
RO_CRATE_PROFILE = "https://w3id.org/ro/crate/1.1"
SCHEMA = "hcs.ro-crate.v1"
LICENSE = "Apache-2.0"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _status_action(status: str) -> str:
    if status in {"succeeded", "partial"}:
        return "http://schema.org/CompletedActionStatus"
    if status in {"cancelled"}:
        return "http://schema.org/AbortedActionStatus"
    return "http://schema.org/FailedActionStatus"


def _environment_entity(manifest: dict[str, Any]) -> dict[str, Any]:
    properties = []
    for name, value in (manifest.get("environment") or {}).items():
        properties.append({"@type": "PropertyValue", "name": str(name), "value": str(value)})
    for name, value in (manifest.get("hardware") or {}).items():
        properties.append({"@type": "PropertyValue", "name": f"hardware.{name}", "value": str(value)})
    return {
        "@id": "#environment",
        "@type": "CreativeWork",
        "name": "Execution environment",
        "additionalProperty": properties,
    }


def build_crate(data: dict[str, Any], settings: Settings) -> tuple[dict[str, Any], list[tuple[Path, str]]]:
    """Return the RO-Crate JSON-LD document and the ``(source, archive path)`` files."""
    run = data["run"]
    project = data["project"] or {"id": "unknown", "name": "unknown"}
    run_dir = safe_join(settings.runs_dir, run["id"])
    if not run_dir.is_dir():
        raise NotFoundError("The run directory no longer exists.", details={"run_id": run["id"]})

    files: list[tuple[Path, str]] = []
    file_entities: list[dict[str, Any]] = []
    missing: list[str] = []
    for artifact in data["artifacts"]:
        source = safe_join(run_dir, artifact["rel_path"])
        if not source.is_file():
            missing.append(artifact["rel_path"])
            continue
        archive_path = f"artifacts/{artifact['rel_path']}"
        files.append((source, archive_path))
        file_entities.append(
            {
                "@id": archive_path,
                "@type": "File",
                "name": Path(artifact["rel_path"]).name,
                "encodingFormat": artifact["media_type"] or "application/octet-stream",
                "contentSize": source.stat().st_size,
                "sha256": _sha256(source),
                "description": f"Artifact produced by node in run {run['id']}.",
            }
        )
    if missing:
        raise NotFoundError(
            "The run references artifacts that are not on disk; refusing to write an incomplete crate.",
            details={"missing": missing, "run_id": run["id"]},
        )

    dataset = (data.get("manifest") or {}).get("dataset") or {}
    dataset_entity: dict[str, Any] = {
        "@id": "#input-dataset",
        "@type": "File",
        "name": "Input dataset",
        "description": "Dataset the workflow read; identified by its stored checksum.",
    }
    if dataset.get("sha256"):
        dataset_entity["sha256"] = dataset["sha256"]
    if dataset.get("id"):
        dataset_entity["identifier"] = dataset["id"]

    root: dict[str, Any] = {
        "@id": "./",
        "@type": "Dataset",
        "name": f"{run['workflow_name']} - run {run['id']}",
        "description": (
            f"Provenance crate for a {PRODUCT_NAME} run. {CAVEAT} "
            "Computational outputs are prioritisation signals, not experimental evidence."
        ),
        "datePublished": run["finished_at"] or run["created_at"],
        "license": LICENSE,
        "creator": {"@id": "#hcsmedia"},
        "publisher": {"@id": "#hcsmedia"},
        "hasPart": [{"@id": entity["@id"]} for entity in file_entities]
        + ([{"@id": "#input-dataset"}] if dataset else []),
        "conformsTo": [{"@id": RO_CRATE_PROFILE}],
        "keywords": ["drug discovery", "cheminformatics", "reproducibility", "provenance"],
    }

    action: dict[str, Any] = {
        "@id": "#run",
        "@type": ["CreateAction", "prov:Activity"],
        "name": f"Run {run['id']} of {run['workflow_name']}",
        "startTime": run["started_at"],
        "endTime": run["finished_at"],
        "actionStatus": {"@id": _status_action(run["status"])},
        "instrument": {"@id": "#workflow"},
        "agent": {"@id": "#software"},
        "object": [{"@id": "#input-dataset"}] if dataset else [],
        "result": [{"@id": entity["@id"]} for entity in file_entities],
        "additionalProperty": [
            {"@type": "PropertyValue", "name": "run.status", "value": run["status"]},
            {"@type": "PropertyValue", "name": "run.workflow_hash", "value": run["workflow_hash"]},
            {"@type": "PropertyValue", "name": "run.seed", "value": str(run["seed"])},
            {"@type": "PropertyValue", "name": "run.nodes", "value": str(len(data["nodes"]))},
        ],
    }
    if run.get("error"):
        action["error"] = run["error"]

    workflow: dict[str, Any] = {
        "@id": "#workflow",
        "@type": ["SoftwareApplication", "prov:Plan"],
        "name": run["workflow_name"],
        "identifier": run["workflow_hash"],
        "applicationCategory": "Scientific workflow",
        "softwareVersion": __version__,
        "description": "Immutable workflow snapshot stored with the run.",
        "hasPart": [
            {
                "@id": f"#node-{node['node_id']}",
                "@type": "HowToStep",
                "name": node["node_id"],
                "description": node["type"],
                "additionalProperty": [
                    {"@type": "PropertyValue", "name": "status", "value": node["status"]},
                    {"@type": "PropertyValue", "name": "cached", "value": str(node["cached"])},
                    {"@type": "PropertyValue", "name": "cache_key", "value": node["cache_key"] or ""},
                ],
            }
            for node in data["nodes"]
        ],
    }

    graph: list[dict[str, Any]] = [
        {
            "@id": "ro-crate-metadata.json",
            "@type": "CreativeWork",
            "about": {"@id": "./"},
            "conformsTo": [{"@id": RO_CRATE_PROFILE}],
            "description": f"RO-Crate 1.1 metadata for run {run['id']}. Schema {SCHEMA}.",
        },
        root,
        action,
        workflow,
        {
            "@id": "#software",
            "@type": "SoftwareApplication",
            "name": PRODUCT_NAME,
            "softwareVersion": __version__,
            "applicationCategory": "Scientific software",
            "description": CREDIT,
            "license": LICENSE,
        },
        {
            "@id": "#hcsmedia",
            "@type": "Organization",
            "name": "hcsmedia",
            "description": CREDIT,
        },
        {
            "@id": "#project",
            "@type": "Project",
            "name": project["name"],
            "identifier": project["id"],
        },
        _environment_entity(data.get("manifest") or {}),
        *file_entities,
    ]
    if dataset:
        graph.append(dataset_entity)

    document = {"@context": RO_CRATE_CONTEXT, "@graph": graph}
    return document, files


def export_ro_crate(session: Session, settings: Settings, run_id: str, output: Path) -> Path:
    """Write ``<run>.crate.zip`` with ``ro-crate-metadata.json`` and every artifact."""
    data = load_report_data(session, run_id)
    document, files = build_crate(data, settings)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        payload = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
        info = zipfile.ZipInfo("ro-crate-metadata.json", date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, payload)
        for source, archive_path in files:
            info = zipfile.ZipInfo(archive_path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, source.read_bytes())
    return output
