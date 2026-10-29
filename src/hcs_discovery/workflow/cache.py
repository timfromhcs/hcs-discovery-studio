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

from ..core.hashing import sha256_file, stable_json_hash
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
            content_hash = payload["content_hash"]
            artifacts = payload.get("artifacts", [])
            summary = payload.get("summary", {})
        except (KeyError, TypeError, json.JSONDecodeError, ValueError):
            shutil.rmtree(entry, ignore_errors=True)
            return None
        if content_hash != table.content_hash():
            shutil.rmtree(entry, ignore_errors=True)
            return None
        for artifact in artifacts:
            cache_file = artifact.get("cache_file")
            expected_sha = artifact.get("sha256")
            if not isinstance(cache_file, str) or not isinstance(expected_sha, str):
                shutil.rmtree(entry, ignore_errors=True)
                return None
            path = safe_join(entry / "artifacts", cache_file)
            if not path.is_file() or sha256_file(path) != expected_sha:
                shutil.rmtree(entry, ignore_errors=True)
                return None
        return CachedOutput(
            table=table,
            artifacts=artifacts,
            summary=summary,
        )

    def put(self, key: str, output: CachedOutput, artifact_files: dict[str, Path]) -> bool:
        entry = self._entry_dir(key)
        entry.mkdir(parents=True, exist_ok=True)
        artifacts_dir = entry / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        stored: list[dict[str, Any]] = []
        for artifact in output.artifacts:
            name = artifact["filename"]
            source = artifact_files.get(name)
            if source is None or not source.exists():
                # Never publish a partial cache entry: it would replay a run with
                # missing artifacts while still reporting success.
                shutil.rmtree(entry, ignore_errors=True)
                return False
            destination = safe_join(artifacts_dir, name)
            shutil.copy2(source, destination)
            stored.append({**artifact, "cache_file": name, "sha256": sha256_file(destination)})
        payload = {
            "columns": [column.as_dict() for column in output.table.columns],
            "rows": output.table.rows,
            "content_hash": output.table.content_hash(),
            "artifacts": stored,
            "summary": output.summary,
        }
        tmp = entry / "entry.json.tmp"
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(entry / "entry.json")
        return True

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

    def prune(
        self,
        *,
        max_mb: int | None = None,
        max_age_days: int | None = None,
        dry_run: bool = False,
    ) -> tuple[int, int]:
        """Prune cache entries based on maximum size (LRU) and/or maximum age.

        Returns (removed_entries, removed_bytes).
        """
        if not self.root.exists():
            return (0, 0)

        import time

        now = time.time()
        entries_info: list[dict[str, Any]] = []

        for manifest in sorted(self.root.rglob("entry.json")):
            entry_dir = manifest.parent
            try:
                mtime = manifest.stat().st_mtime
                entry_bytes = sum(f.stat().st_size for f in entry_dir.rglob("*") if f.is_file())
            except OSError:
                continue
            age_days = (now - mtime) / 86400.0
            entries_info.append(
                {
                    "dir": entry_dir,
                    "mtime": mtime,
                    "bytes": entry_bytes,
                    "age_days": age_days,
                }
            )

        to_remove: set[Path] = set()

        if max_age_days is not None and max_age_days > 0:
            for info in entries_info:
                if info["age_days"] > max_age_days:
                    to_remove.add(info["dir"])

        if max_mb is not None and max_mb >= 0:
            max_bytes = max_mb * 1024 * 1024
            active_entries = [e for e in sorted(entries_info, key=lambda x: x["mtime"]) if e["dir"] not in to_remove]
            current_total = sum(e["bytes"] for e in active_entries)
            for e in active_entries:
                if current_total <= max_bytes:
                    break
                to_remove.add(e["dir"])
                current_total -= e["bytes"]

        removed_entries = len(to_remove)
        removed_bytes = sum(info["bytes"] for info in entries_info if info["dir"] in to_remove)

        if not dry_run:
            for entry_dir in to_remove:
                shutil.rmtree(entry_dir, ignore_errors=True)
                parent = entry_dir.parent
                if parent.exists() and not any(parent.iterdir()):
                    shutil.rmtree(parent, ignore_errors=True)

        return (removed_entries, removed_bytes)

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
