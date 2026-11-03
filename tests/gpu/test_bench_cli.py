from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from hcs_discovery.cli.main import app
from hcs_discovery.gpu import bench
from hcs_discovery.gpu.device import select_adapter

runner = CliRunner()


def test_bench_skipped_without_gpu_exits_zero(monkeypatch):
    monkeypatch.setattr(
        bench, "probe_gpu", lambda: {"status": "unavailable", "detail": "none", "adapter": None, "backend": None}
    )
    result = runner.invoke(app, ["gpu", "bench", "--n", "64"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["status"] == "skipped"


def test_probe_command_emits_json():
    result = runner.invoke(app, ["gpu", "probe"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["status"] in {"available", "unavailable", "software_only"}


@pytest.mark.gpu
def test_bench_parity_on_hardware(tmp_path):
    if select_adapter() is None:
        pytest.skip("no hardware GPU adapter")
    out = tmp_path / "b.json"
    result = runner.invoke(app, ["gpu", "bench", "--n", "2000", "--repeats", "2", "--out", str(out)])
    assert result.exit_code == 0, result.stdout
    data = json.loads(out.read_text())
    assert data["schema"] == "hcs.gpu-bench.v1" and data["parity"]["exact_counts"] is True
    assert data["status"] == "passed"


def test_system_gpu_route(client):
    r = client.get("/api/v1/gpu")
    assert r.status_code == 200 and "status" in r.json()
