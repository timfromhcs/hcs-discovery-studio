"""Node registry and adapter-style contracts for workflow steps.

Node implementations are plain Python objects with a typed config model, declared
inputs/outputs and a handler. Third-party code can register additional nodes; the
registry is the single source of truth used by validation, the API and the UI.
"""

from __future__ import annotations

import builtins
import functools
import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from ..core.errors import ValidationError
from .table import Column, Table


class NodeConfig(BaseModel):
    """Base class for node configuration models."""


ArtifactWriter = Callable[[str, str | bytes, str], dict[str, Any]]


@dataclass
class NodeContext:
    run_id: str
    node_id: str
    work_dir: Path
    emit: Callable[[str, str, dict[str, Any] | None, str], None]
    report_progress: Callable[[float | None], None]
    check_cancel: Callable[[], None]
    write_artifact: ArtifactWriter
    engine_versions: dict[str, str] = field(default_factory=dict)
    incoming_tables: dict[str, Any] = field(default_factory=dict)

    def log(self, message: str, *, level: str = "info", data: dict[str, Any] | None = None) -> None:
        self.emit(level, message, data, "log")


@dataclass(frozen=True)
class NodeDefinition:
    type: str
    title: str
    category: str
    version: str
    description: str
    config_model: builtins.type[BaseModel]
    handler: Callable[[Table, Any, NodeContext], Table]
    requires: tuple[str, ...] = ()
    extra_requires: Callable[[Any], tuple[str, ...]] | None = None
    outputs: Callable[[Any], list[Column]] = lambda _config: []
    documentation: str = ""
    # Host-dependent inputs that change output for a given config (for example the
    # installed engine version or the content of a referenced file). Included in
    # the node cache key.
    runtime_fingerprint: Callable[[Any], dict[str, str]] | None = None

    def parse_config(self, config: dict[str, Any]) -> Any:
        try:
            return self.config_model.model_validate(config)
        except PydanticValidationError as exc:
            raise ValidationError(
                f"Invalid configuration for '{self.type}'.",
                details={"issues": exc.errors(include_url=False)},
            ) from exc

    def produces(self, config: Any) -> list[Column]:
        return list(self.outputs(config))

    def required_columns(self, config: Any) -> tuple[str, ...]:
        extra = self.extra_requires(config) if self.extra_requires else ()
        return (*self.requires, *extra)

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "title": self.title,
            "category": self.category,
            "version": self.version,
            "description": self.description,
            "requires": list(self.requires),
            "config_schema": self.config_model.model_json_schema(),
            "documentation": self.documentation,
        }

    @property
    def implementation_hash(self) -> str:
        """Fingerprint of the handler and config contract.

        Cache keys include this so editing a handler cannot silently reuse old
        results that were produced by different code.
        """
        import inspect

        from ..core.hashing import sha256_text

        source = inspect.getsource(self.handler)
        schema = self.config_model.model_json_schema()
        import json

        return sha256_text(f"{self.type}|{self.version}|{source}|{json.dumps(schema, sort_keys=True)}")


@functools.cache
def package_fingerprint() -> str:
    """Hash of every source and data file shipped in the ``hcs_discovery`` package.

    The handler-only ``implementation_hash`` misses helper modules, model
    coefficients and preprocessing code. Including this fingerprint in cache keys
    means any change to the installed code invalidates cached scientific output.
    The trade-off is deliberate: an unrelated code edit also forces recomputation.
    The bundled SPA and migration scripts cannot change node output and are skipped.
    """
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file() or relative.parts[0] in {"web", "_alembic"}:
            continue
        if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(bytes(1))
        # Normalise line endings so a CRLF checkout and an LF wheel agree.
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
        digest.update(bytes(1))
    return digest.hexdigest()


class NodeRegistry:
    def __init__(self) -> None:
        self._nodes: dict[str, NodeDefinition] = {}

    def register(self, definition: NodeDefinition, *, replace: bool = False) -> None:
        if definition.type in self._nodes and not replace:
            raise ValidationError(f"Node type '{definition.type}' is already registered.")
        self._nodes[definition.type] = definition

    def has(self, node_type: str) -> bool:
        return node_type in self._nodes

    def get(self, node_type: str) -> NodeDefinition:
        try:
            return self._nodes[node_type]
        except KeyError as exc:
            raise ValidationError(
                f"Unknown node type '{node_type}'.",
                details={"available": sorted(self._nodes)},
            ) from exc

    def types(self) -> list[str]:
        return sorted(self._nodes)

    def catalog(self) -> list[dict[str, Any]]:
        return [self._nodes[key].as_dict() for key in sorted(self._nodes)]

    def engine_versions(self) -> dict[str, str]:
        return {key: self._nodes[key].version for key in sorted(self._nodes)}


_REGISTRY: NodeRegistry | None = None


def default_registry() -> NodeRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        from .nodes import register_builtin_nodes

        registry = NodeRegistry()
        register_builtin_nodes(registry)
        _REGISTRY = registry
    return _REGISTRY
