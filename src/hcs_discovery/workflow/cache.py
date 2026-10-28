"""Content-addressed node output cache.

A cache key covers the node implementation version, its configuration, the exact
input table content, the pinned scientific engine versions and the workflow schema
version. Any change invalidates the entry, so results cannot silently mix
incompatible scientific versions.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.hashing import stable_json_hash
from ..core.paths import safe_join
from .table import Column, Table


def cache_key(
    *,
    node_type: str,
    node_version: str,
    config: dict[str, Any],
    input_hash: str,
    engine_versions: dict[str, str],
    schema_version: int = 1,
    implementation_hash: str | None = None,
) -> str:
    return stable_json_hash(
        {
            "node_type": node_type,
            "node_version": node_version,
            "implementation_hash": implementation_hash,
            "config": config,
            "input_hash": input_hash,
            "engines": engine_versions,
            "schema_version": schema_version,
        }
    )


@dataclass
class CachedOutput:
    table: Table
    artifacts: list[dict[str, Any]]
    summary: dict[str, Any]


class NodeCache:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _entry_dir(self, key: str) -> Path:
        return safe_join(self.root, key[:2], key)

    def get(self, key: str) -> CachedOutput | None:
        entry = self._entry_dir(key)
        manifest = entry / "entry.json"
        if not manifest.exists():
            return None
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            columns = [Column(**column) for column in payload["columns"]]
            table = Table(rows=payload["rows"], columns=columns)
        except (KeyError, TypeError, json.JSONDecodeError, ValueError):
            return None
        return CachedOutput(
            table=table,
            artifacts=payload.get("artifacts", []),
            summary=payload.get("summary", {}),
        )

    def put(self, key: str, output: CachedOutput, artifact_files: dict[str, Path]) -> None:
        entry = self._entry_dir(key)
        entry.mkdir(parents=True, exist_ok=True)
        artifacts_dir = entry / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        stored: list[dict[str, Any]] = []
        for artifact in output.artifacts:
            name = artifact["filename"]
            source = artifact_files.get(name)
            if source is None or not source.exists():
                continue
            destination = safe_join(artifacts_dir, name)
            shutil.copy2(source, destination)
            stored.append({**artifact, "cache_file": name})
        payload = {
            "columns": [column.as_dict() for column in output.table.columns],
            "rows": output.table.rows,
            "artifacts": stored,
            "summary": output.summary,
        }
        tmp = entry / "entry.json.tmp"
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(entry / "entry.json")

    def artifact_path(self, key: str, filename: str) -> Path:
        return safe_join(self._entry_dir(key) / "artifacts", filename)

    def clear(self) -> tuple[int, int]:
        """Remove all cache entries. Returns (entries, bytes) removed."""
        entries = 0
        total = 0
        if not self.root.exists():
            return (0, 0)
        for child in sorted(self.root.rglob("entry.json")):
            entries += 1
            for file in child.parent.rglob("*"):
                if file.is_file():
                    total += file.stat().st_size
        for item in list(self.root.iterdir()):
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
        return (entries, total)

    def stats(self) -> dict[str, Any]:
        entries = 0
        total = 0
        if self.root.exists():
            for _manifest in self.root.rglob("entry.json"):
                entries += 1
            for file in self.root.rglob("*"):
                if file.is_file():
                    total += file.stat().st_size
        return {"entries": entries, "bytes": total}
