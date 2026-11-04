"""MCP server: JSON-RPC framing, tool contracts and a real stdio session."""

from __future__ import annotations

import json
import subprocess
import sys

from hcs_discovery.mcp_server import handle_message, serve


def call(message: dict) -> dict:
    response = handle_message(message)
    assert response is not None, "notifications must not produce a response"
    return response


def test_initialize_announces_tools_and_protocol():
    response = call({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    result = response["result"]
    assert result["protocolVersion"]
    assert result["capabilities"]["tools"]["listChanged"] is False
    assert result["serverInfo"]["name"] == "hcs-discovery"


def test_notifications_do_not_get_a_response():
    assert handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_tools_list_exposes_read_only_tools():
    response = call({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tools = {tool["name"]: tool for tool in response["result"]["tools"]}
    assert set(tools) == {
        "hcs_doctor",
        "hcs_similarity_search",
        "hcs_gpu_bench",
        "hcs_workflow_validate",
        "hcs_models_list",
    }
    assert all(tool["annotations"]["readOnlyHint"] is True for tool in tools.values())
    assert tools["hcs_similarity_search"]["inputSchema"]["required"] == ["query"]


def test_similarity_tool_returns_the_cli_schema(settings):
    response = call(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "hcs_similarity_search",
                "arguments": {
                    "query": "c1ccccc1",
                    "smiles": ["c1ccccc1", "CCO", "not-a-smiles"],
                    "engine": "cpu",
                    "k": 2,
                },
            },
        }
    )
    payload = json.loads(response["result"]["content"][0]["text"])
    assert response["result"]["isError"] is False
    assert payload["schema"] == "hcs.similarity-search.v1"
    assert payload["n_library"] == 3
    assert payload["hits"][0]["similarity"] == 1.0
    assert len(payload["hits"]) == 2


def test_similarity_tool_rejects_both_sources(settings):
    response = call(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "hcs_similarity_search",
                "arguments": {"query": "CCO", "smiles": ["CCO"], "file": "library.smi"},
            },
        }
    )
    assert response["result"]["isError"] is True
    assert "either" in response["result"]["content"][0]["text"]


def test_unknown_tool_is_a_jsonrpc_error():
    response = call(
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "hcs_shell", "arguments": {}}}
    )
    assert response["error"]["code"] == -32602


def test_unknown_method_and_bad_version():
    assert call({"jsonrpc": "2.0", "id": 6, "method": "nope"})["error"]["code"] == -32601
    assert call({"jsonrpc": "1.0", "id": 7, "method": "ping"})["error"]["code"] == -32600


def test_workflow_validate_tool_reports_the_order(triage_definition):
    response = call(
        {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {"name": "hcs_workflow_validate", "arguments": {"workflow": triage_definition}},
        }
    )
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["valid"] is True
    assert payload["order"] == ["descriptors", "filters", "ranking", "summary"]


def test_doctor_and_models_tools(settings):
    doctor = call(
        {"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "hcs_doctor", "arguments": {}}}
    )
    payload = json.loads(doctor["result"]["content"][0]["text"])
    assert payload["status"] in {"ok", "degraded", "error"}
    assert payload["checks"]

    models = call(
        {"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": {"name": "hcs_models_list", "arguments": {}}}
    )
    catalog = json.loads(models["result"]["content"][0]["text"])
    assert "chem.similarity" in catalog["types"]


def test_stdio_session_is_protocol_only(settings):
    """A real subprocess: stdout must contain JSON-RPC lines and nothing else."""
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "hcs_models_list", "arguments": {}}},
    ]
    process = subprocess.run(
        [sys.executable, "-m", "hcs_discovery.cli.main", "mcp", "serve"],
        input="\n".join(json.dumps(request) for request in requests) + "\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert process.returncode == 0, process.stderr[-2000:]
    lines = [line for line in process.stdout.splitlines() if line.strip()]
    assert len(lines) == 3
    for line in lines:
        message = json.loads(line)
        assert message["jsonrpc"] == "2.0"
        assert "result" in message


def test_parse_errors_and_invalid_requests(capsys):
    serve(iter(['{"jsonrpc": "2.0", "id": 1,\n', "[1, 2, 3]\n"]))
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert len(lines) == 2
    assert json.loads(lines[0])["error"]["code"] == -32700  # truncated JSON: parse error
    assert json.loads(lines[1])["error"]["code"] == -32600  # array instead of object
    assert handle_message({"jsonrpc": "2.0", "id": 2})["error"]["code"] == -32600
    assert handle_message({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": []})["error"]["code"] == -32602


# ------------------------------------------------------------------- 2026-07-28
MODERN_META = {"io.modelcontextprotocol/protocolVersion": "2026-07-28"}


def _modern(method: str, request_id: int, params: dict | None = None) -> dict:
    merged = {"_meta": MODERN_META, **(params or {})}
    return call({"jsonrpc": "2.0", "id": request_id, "method": method, "params": merged})


def test_server_discover_reports_the_modern_versions_and_identity():
    response = call({"jsonrpc": "2.0", "id": 20, "method": "server/discover", "params": {"_meta": MODERN_META}})
    result = response["result"]
    assert result["resultType"] == "complete"
    assert result["supportedVersions"][0] == "2026-07-28"
    assert "2024-11-05" in result["supportedVersions"]
    assert result["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "hcs-discovery"
    assert result["capabilities"]["tools"] == {}
    assert result["ttlMs"] > 0 and result["cacheScope"] == "public"


def test_modern_tools_list_is_cacheable_and_deterministic():
    first = _modern("tools/list", 21)["result"]
    second = _modern("tools/list", 22)["result"]
    assert first["resultType"] == "complete"
    assert first["ttlMs"] == 60_000 and first["cacheScope"] == "public"
    names = [tool["name"] for tool in first["tools"]]
    assert names == sorted(names)
    assert names == [tool["name"] for tool in second["tools"]]
    assert all(tool["annotations"]["openWorldHint"] is False for tool in first["tools"])


def test_modern_tool_call_carries_structured_content(settings):
    response = _modern(
        "tools/call",
        23,
        {"name": "hcs_similarity_search", "arguments": {"query": "CCO", "smiles": ["CCO", "CCC"], "engine": "cpu"}},
    )
    result = response["result"]
    assert result["resultType"] == "complete"
    assert result["structuredContent"]["schema"] == "hcs.similarity-search.v1"
    assert result["isError"] is False


def test_unsupported_version_is_a_modern_error_with_the_supported_list():
    response = call(
        {
            "jsonrpc": "2.0",
            "id": 24,
            "method": "tools/list",
            "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "1900-01-01"}},
        }
    )
    assert response["error"]["code"] == -32022
    assert "2026-07-28" in response["error"]["data"]["supported"]
    assert response["error"]["data"]["requested"] == "1900-01-01"


def test_legacy_initialize_still_negotiates_an_old_revision():
    response = call({"jsonrpc": "2.0", "id": 25, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}})
    assert response["result"]["protocolVersion"] == "2024-11-05"
    assert "resultType" not in response["result"]
    legacy_list = call({"jsonrpc": "2.0", "id": 26, "method": "tools/list"})["result"]
    assert "ttlMs" not in legacy_list and "resultType" not in legacy_list
