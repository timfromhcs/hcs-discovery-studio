"""A dependency-free MCP server (stdio, JSON-RPC 2.0) for local automation.

Why hand-rolled: an MCP server that pulls a new runtime dependency into a package
whose selling point is "installs and runs offline with no account" would be a poor
trade. The protocol surface this needs is small and stable — ``initialize``,
``tools/list``, ``tools/call``, ``ping`` — and JSON-RPC over stdin/stdout is
easy to test without a transport library.

Contract:

- **stdout carries protocol messages only.** Diagnostics and errors go to stderr;
  a stray ``print`` would corrupt the stream, so nothing in the tool path prints.
- **Read-only tools.** No shell, no writes outside a temporary directory, no
  network. A tool that needs data takes an explicit file path or inline values.
- **Bounded inputs.** Row counts and library sizes are capped; exceeding a cap is
  a tool error, not a long-running surprise.
- **Same payloads as the CLI.** ``hcs_similarity_search`` returns the
  ``hcs.similarity-search.v1`` shape, so an agent and a shell get the same answer.
"""

from __future__ import annotations

import json
import sys
import traceback
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from hcs_discovery import __version__
from hcs_discovery.core.config import get_settings
from hcs_discovery.core.doctor import run_diagnostics
from hcs_discovery.core.errors import AppError
from hcs_discovery.similarity import GpuUnavailableError, ParityError, TanimotoIndex
from hcs_discovery.workflow.schema import validate_workflow

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "hcs-discovery"
MAX_INLINE_SMILES = 50_000
MAX_BENCH_LIBRARY = 200_000
MAX_FILE_BYTES = 64 * 1024 * 1024


class ToolError(Exception):
    """A tool call that failed for a reason the caller can act on."""


def _text(payload: Any, *, is_error: bool = False) -> dict[str, Any]:
    body = payload if isinstance(payload, str) else json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    return {"content": [{"type": "text", "text": body}], "isError": is_error}


def _read_structures(path: Path) -> list[str]:
    if not path.is_file():
        raise ToolError(f"File not found: {path}")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ToolError(f"File exceeds the {MAX_FILE_BYTES} byte cap: {path}")
    suffix = path.suffix.lower()
    if suffix == ".smi":
        lines = [line.split()[0] for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return lines
    if suffix in {".sdf", ".mol"}:
        from rdkit import Chem

        supplier = Chem.ForwardSDMolSupplier(str(path), sanitize=False)
        smiles = ["" if mol is None else Chem.MolToSmiles(mol) for mol in supplier]
        return [value for value in smiles if value]
    if suffix == ".csv":
        import csv

        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ToolError("CSV file has no header row.")
            column = next((name for name in reader.fieldnames if name.strip().lower() == "smiles"), None)
            if column is None:
                raise ToolError("CSV file has no 'smiles' column.")
            return [row[column].strip() for row in reader if (row.get(column) or "").strip()]
    raise ToolError("Unsupported structure file. Use .smi, .csv or .sdf.")


def tool_doctor(_: dict[str, Any]) -> dict[str, Any]:
    report = run_diagnostics(get_settings())
    return {
        "status": report["status"],
        "product": report.get("product"),
        "environment": report.get("environment"),
        "checks": [{key: check.get(key) for key in ("id", "status", "detail")} for check in report.get("checks", [])],
    }


def tool_similarity_search(arguments: dict[str, Any]) -> dict[str, Any]:
    query = str(arguments.get("query") or arguments.get("query_smiles") or "").strip()
    if not query:
        raise ToolError("'query' (SMILES) is required.")
    inline = arguments.get("smiles")
    file_name = arguments.get("file")
    if inline is not None and file_name is not None:
        raise ToolError("Provide either 'smiles' or 'file', not both.")
    if isinstance(inline, list):
        structures = [str(item) for item in inline]
    elif isinstance(inline, str):
        structures = [item.strip() for item in inline.splitlines() if item.strip()]
    elif file_name:
        structures = _read_structures(Path(str(file_name)).expanduser())
    else:
        raise ToolError("Provide 'smiles' (a list or newline-separated string) or a 'file' path.")
    if not structures:
        raise ToolError("No structures were supplied.")
    if len(structures) > MAX_INLINE_SMILES:
        raise ToolError(f"At most {MAX_INLINE_SMILES} structures per call.")
    k = int(arguments.get("k", 10))
    threshold = arguments.get("threshold")
    engine = str(arguments.get("engine", "auto"))
    boost = str(arguments.get("boost", "auto"))
    if engine not in {"auto", "cpu", "gpu"}:
        raise ToolError("engine must be auto, cpu or gpu.")
    if boost not in {"auto", "gpu", "cpu", "hybrid"}:
        raise ToolError("boost must be auto, gpu, cpu or hybrid.")
    try:
        with TanimotoIndex(structures, prefer=engine, boost=boost) as index:  # type: ignore[arg-type]
            result = index.search(query, k=k, threshold=None if threshold is None else float(threshold))
            resolved = index.engine
    except GpuUnavailableError as exc:
        raise ToolError(f"No hardware GPU adapter: {exc}") from exc
    except ParityError as exc:
        raise ToolError(f"GPU parity check failed, no result returned: {exc}") from exc
    return {
        "schema": "hcs.similarity-search.v1",
        "query": query,
        "n_library": len(structures),
        "engine": {
            "name": resolved.name,
            "mode": resolved.mode,
            "adapter": resolved.adapter,
            "backend": resolved.backend,
            "detail": resolved.detail,
        },
        "parity_checked": result.parity_checked,
        "hits": [
            {"rank": rank, "index": hit.index, "similarity": round(hit.similarity, 6)}
            for rank, hit in enumerate(result.hits, start=1)
        ],
    }


def tool_gpu_bench(arguments: dict[str, Any]) -> dict[str, Any]:
    from hcs_discovery.gpu.bench import run_bench

    n = int(arguments.get("n", 100_000))
    repeats = int(arguments.get("repeats", 3))
    if not 64 <= n <= MAX_BENCH_LIBRARY:
        raise ToolError(f"n must be between 64 and {MAX_BENCH_LIBRARY}.")
    if not 1 <= repeats <= 10:
        raise ToolError("repeats must be between 1 and 10.")
    return run_bench(n_library=n, repeats=repeats)


def tool_workflow_validate(arguments: dict[str, Any]) -> dict[str, Any]:
    workflow = arguments.get("workflow")
    if not isinstance(workflow, dict):
        raise ToolError("'workflow' must be a workflow object (schema_version, name, nodes, edges).")
    try:
        validated = validate_workflow(workflow)
    except AppError as exc:
        return {"valid": False, "error": exc.to_dict()}
    return {
        "valid": True,
        "name": validated.spec.name,
        "content_hash": validated.content_hash,
        "order": [node.id for node in validated.order],
    }


def tool_models_list(_: dict[str, Any]) -> dict[str, Any]:
    from hcs_discovery.workflow.registry import default_registry

    registry = default_registry()
    return {"nodes": registry.catalog(), "types": registry.types()}


TOOLS: dict[str, tuple[dict[str, Any], Callable[[dict[str, Any]], dict[str, Any]]]] = {
    "hcs_doctor": (
        {
            "description": "Report what this machine can actually do (data dir, database, RDKit, GPU probe).",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        tool_doctor,
    ),
    "hcs_similarity_search": (
        {
            "description": (
                "Tanimoto similarity search over an inline SMILES library or a .smi/.csv/.sdf file. "
                "Returns the hcs.similarity-search.v1 payload; GPU results are parity-checked."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Query SMILES."},
                    "smiles": {
                        "oneOf": [
                            {"type": "array", "items": {"type": "string"}},
                            {"type": "string", "description": "Newline-separated SMILES."},
                        ]
                    },
                    "file": {"type": "string"},
                    "k": {"type": "integer", "minimum": 1, "maximum": 10000},
                    "threshold": {"type": "number", "minimum": 0, "maximum": 1},
                    "engine": {"type": "string", "enum": ["auto", "cpu", "gpu"]},
                    "boost": {"type": "string", "enum": ["auto", "gpu", "cpu", "hybrid"]},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
        tool_similarity_search,
    ),
    "hcs_gpu_bench": (
        {
            "description": "Parity-first Tanimoto benchmark on this host's adapter (bounded size).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer", "minimum": 64, "maximum": MAX_BENCH_LIBRARY},
                    "repeats": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                "additionalProperties": False,
            },
        },
        tool_gpu_bench,
    ),
    "hcs_workflow_validate": (
        {
            "description": "Validate a workflow object without queueing it.",
            "inputSchema": {
                "type": "object",
                "properties": {"workflow": {"type": "object"}},
                "required": ["workflow"],
                "additionalProperties": False,
            },
        },
        tool_workflow_validate,
    ),
    "hcs_models_list": (
        {
            "description": "List the registered workflow node types and their configuration schemas.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        tool_models_list,
    ),
}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_message(message: dict[str, Any]) -> dict[str, Any] | None:
    """Handle one JSON-RPC message. Returns None for notifications."""
    if message.get("jsonrpc") != "2.0":
        return _error(message.get("id"), -32600, "Invalid Request: jsonrpc must be '2.0'.")
    method = message.get("method")
    request_id = message.get("id")
    if not isinstance(method, str):
        return _error(request_id, -32600, "Invalid Request: method is required.")
    is_notification = "id" not in message
    params = message.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": __version__},
                "instructions": (
                    "Read-only local tools: doctor, similarity search, GPU benchmark, workflow validation, "
                    "node catalog. Nothing is written outside a temporary directory and nothing uses the network."
                ),
            },
        }
    if method.startswith("notifications/"):
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {"name": name, **definition, "annotations": {"readOnlyHint": True}}
                    for name, (definition, _) in TOOLS.items()
                ]
            },
        }
    if method == "tools/call":
        if not isinstance(params, dict):
            return _error(request_id, -32602, "Invalid params.")
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str) or name not in TOOLS:
            return _error(request_id, -32602, f"Unknown tool: {name!r}.")
        if not isinstance(arguments, dict):
            return _error(request_id, -32602, "Tool arguments must be an object.")
        _, handler = TOOLS[name]
        try:
            payload = handler(arguments)
        except ToolError as exc:
            return {"jsonrpc": "2.0", "id": request_id, "result": _text(str(exc), is_error=True)}
        except AppError as exc:
            return {"jsonrpc": "2.0", "id": request_id, "result": _text(exc.to_dict(), is_error=True)}
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            return {"jsonrpc": "2.0", "id": request_id, "result": _text(f"Tool failed: {exc}", is_error=True)}
        return {"jsonrpc": "2.0", "id": request_id, "result": _text(payload)}
    if is_notification:
        return None
    return _error(request_id, -32601, f"Method not found: {method}")


def serve(lines: Iterator[str] | None = None) -> int:
    """Run the stdio server until EOF. Only JSON-RPC goes to stdout."""
    source = lines if lines is not None else iter(sys.stdin)
    for raw in source:
        raw = raw.strip()
        if not raw:
            continue
        response: dict[str, Any] | None
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            response = _error(None, -32700, "Parse error")
        else:
            if not isinstance(message, dict):
                response = _error(None, -32600, "Invalid Request: expected an object.")
            else:
                response = handle_message(message)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0
