"""Report rendering and security-focused tests."""

from __future__ import annotations

import json

import pytest

from hcs_discovery.core.errors import PolicyError
from hcs_discovery.plugins.llm.openai_compat import OpenAICompatibleProvider
from hcs_discovery.reports.render import load_report_data, render_html, render_json, render_markdown
from hcs_discovery.services import create_run
from hcs_discovery.workflow.executor import RunExecutor


@pytest.fixture()
def finished_run(settings, session, project, dataset, triage_definition):
    run = create_run(session, project_id=project.id, workflow=triage_definition, dataset_id=dataset.id)
    executor = RunExecutor(
        run_id=run.id,
        session_factory=__import__("hcs_discovery.database.base", fromlist=["get_session_factory"]).get_session_factory(
            settings
        ),
        settings=settings,
        worker_id="report-test",
    )
    assert executor.execute() == "succeeded"
    session.expire_all()
    return session.get(type(run), run.id)


def test_reports_include_provenance_and_caveat(session, finished_run):
    data = load_report_data(session, finished_run.id)
    markdown = render_markdown(data)
    assert "## Provenance" in markdown
    assert finished_run.workflow_hash[:16] in markdown
    assert "not measurements" in markdown
    assert "results.csv" in markdown

    html = render_html(data)
    assert "<!doctype html>" in html
    assert "SHA-256" in html

    payload = json.loads(render_json(data))
    assert payload["run"]["id"] == finished_run.id
    assert payload["product"]["version"]


def test_html_report_escapes_untrusted_metadata(session, finished_run):
    finished_run.workflow_name = "<script>alert('x')</script>"
    session.commit()
    html = render_html(load_report_data(session, finished_run.id))
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_local_policy_blocks_remote_llm(settings):
    remote = settings.model_copy(update={"llm_base_url": "https://api.example.com/v1", "network_policy": "local"})
    provider = OpenAICompatibleProvider(remote)
    with pytest.raises(PolicyError):
        provider.chat([{"role": "user", "content": "hi"}])
    health = provider.probe()
    assert health.status == "blocked_by_policy"


def test_remote_llm_requires_explicit_opt_in(settings):
    remote = settings.model_copy(
        update={
            "llm_base_url": "https://api.example.com/v1",
            "network_policy": "remote",
            "remote_llm_enabled": False,
        }
    )
    with pytest.raises(PolicyError):
        OpenAICompatibleProvider(remote).chat([{"role": "user", "content": "hi"}])


def test_provider_metadata_never_exposes_key(settings):
    configured = settings.model_copy(
        update={"llm_base_url": "http://127.0.0.1:1234/v1", "llm_api_key": "secret-value-123"}
    )
    metadata = OpenAICompatibleProvider(configured).metadata()
    assert metadata["api_key"] == "configured"
    assert "secret-value-123" not in json.dumps(metadata)


def test_provider_probe_reports_unreachable_without_crashing(settings):
    configured = settings.model_copy(update={"llm_base_url": "http://127.0.0.1:9/v1"})
    health = OpenAICompatibleProvider(configured).probe()
    assert health.status == "unreachable"


def test_vulkan_probe_is_truthful_about_model_support():
    from hcs_discovery.plugins.science.vulkan import probe_vulkan

    result = probe_vulkan()
    assert "model_support" in result
    if result["available"]:
        assert result["devices"]
    assert result["model_support"] == "unknown"
