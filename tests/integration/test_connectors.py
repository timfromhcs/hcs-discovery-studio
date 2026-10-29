"""Integration tests for external data connectors with mock transports and policy gating."""

from __future__ import annotations

import httpx
import pytest
from starlette.testclient import TestClient

from hcs_discovery.core.config import Settings
from hcs_discovery.core.errors import ValidationError
from hcs_discovery.plugins.connectors import base as connector_base
from hcs_discovery.plugins.connectors.base import MAX_PAYLOAD_BYTES, structure_check
from hcs_discovery.plugins.connectors.chembl import ChEMBLConnector
from hcs_discovery.plugins.connectors.policy import NetworkPolicyViolationError, check_network_allowed
from hcs_discovery.plugins.connectors.pubchem import PubChemConnector


@pytest.fixture()
def remote(tmp_path) -> Settings:
    """Remote network policy; requests still only reach the mock transport."""
    return Settings(data_dir=tmp_path / "data", network_policy="remote")


MOCK_PUBCHEM_ASPIRIN_RESPONSE = {
    "PropertyTable": {
        "Properties": [
            {
                "CID": 2244,
                "SMILES": "CC(=O)OC1=CC=CC=C1C(=O)O",
                "ConnectivitySMILES": "CC(=O)OC1=CC=CC=C1C(=O)O",
                "InChIKey": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
                "MolecularFormula": "C9H8O4",
                "MolecularWeight": "180.16",
                "IUPACName": "2-acetyloxybenzoic acid",
            }
        ]
    }
}

MOCK_CHEMBL_EGFR_RESPONSE = {
    "targets": [
        {
            "target_chembl_id": "CHEMBL203",
            "pref_name": "Epidermal growth factor receptor erbB1",
            "target_type": "SINGLE PROTEIN",
            "organism": "Homo sapiens",
            "score": 100,
        }
    ]
}

MOCK_CHEMBL_ASPIRIN_RESPONSE = {
    "molecules": [
        {
            "molecule_chembl_id": "CHEMBL25",
            "pref_name": "ASPIRIN",
            "max_phase": 4,
            "molecule_type": "Small molecule",
            "molecule_structures": {
                "canonical_smiles": "CC(=O)Oc1ccccc1C(=O)O",
                "standard_inchi_key": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
            },
        }
    ]
}

MOCK_CHEMBL_ACTIVITIES_RESPONSE = {
    "activities": [
        {
            "activity_id": 123456,
            "molecule_chembl_id": "CHEMBL25",
            "standard_type": "IC50",
            "standard_relation": "=",
            "standard_value": "15.5",
            "standard_units": "nM",
            "assay_type": "B",
            "pchembl_value": "7.81",
        }
    ]
}


def test_network_policy_blocks_connectors_by_default(settings: Settings) -> None:
    # Default policy is local
    assert settings.network_policy == "local"

    pubchem = PubChemConnector(settings=settings)
    with pytest.raises(NetworkPolicyViolationError, match="blocked by policy"):
        pubchem.search_compound_by_name("aspirin")

    chembl = ChEMBLConnector(settings=settings)
    with pytest.raises(NetworkPolicyViolationError, match="blocked by policy"):
        chembl.search_targets("EGFR")


def test_pubchem_search_with_mock_transport(remote: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "pubchem.ncbi.nlm.nih.gov" in request.url.host
        assert "aspirin" in str(request.url).lower()
        return httpx.Response(200, json=MOCK_PUBCHEM_ASPIRIN_RESPONSE)

    transport = httpx.MockTransport(handler)
    connector = PubChemConnector(settings=remote, mock_transport=transport)
    records = connector.search_compound_by_name("aspirin")

    assert len(records) == 1
    rec = records[0]
    assert rec.source == "PubChem"
    assert rec.external_id == "CID:2244"
    assert rec.data["canonical_smiles"] == "CC(=O)OC1=CC=CC=C1C(=O)O"
    assert rec.data["molecular_weight"] == 180.16
    assert "CC0" in rec.license
    assert rec.content_hash is not None


def test_chembl_search_targets_with_mock_transport(remote: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "www.ebi.ac.uk" in request.url.host
        if "/target/search.json" in str(request.url):
            return httpx.Response(200, json=MOCK_CHEMBL_EGFR_RESPONSE)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    connector = ChEMBLConnector(settings=remote, mock_transport=transport)
    records = connector.search_targets("EGFR")

    assert len(records) == 1
    rec = records[0]
    assert rec.source == "ChEMBL"
    assert rec.external_id == "CHEMBL203"
    assert rec.data["pref_name"] == "Epidermal growth factor receptor erbB1"
    assert rec.data["organism"] == "Homo sapiens"
    assert "CC-BY-SA" in rec.license


def test_chembl_search_compounds_and_activities_mock(remote: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "/molecule/search.json" in url_str:
            return httpx.Response(200, json=MOCK_CHEMBL_ASPIRIN_RESPONSE)
        if "/activity.json" in url_str:
            return httpx.Response(200, json=MOCK_CHEMBL_ACTIVITIES_RESPONSE)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    connector = ChEMBLConnector(settings=remote, mock_transport=transport)

    compounds = connector.search_compounds("aspirin")
    assert len(compounds) == 1
    assert compounds[0].external_id == "CHEMBL25"
    assert compounds[0].data["canonical_smiles"] == "CC(=O)Oc1ccccc1C(=O)O"

    activities = connector.get_target_activities("CHEMBL203")
    assert len(activities) == 1
    assert activities[0].data["standard_type"] == "IC50"
    assert activities[0].data["standard_value"] == "15.5"


def test_connector_status_api(client: TestClient) -> None:
    response = client.get("/api/v1/connectors/status")
    assert response.status_code == 200
    data = response.json()
    assert data["network_policy"] == "local"
    assert data["remote_enabled"] is False
    assert len(data["connectors"]) == 2
    # Status is blocked_by_policy when policy is local
    assert all(c["status"] == "blocked_by_policy" for c in data["connectors"])


def test_connector_api_endpoints_blocked_by_local_policy(client: TestClient) -> None:
    # PubChem search should be blocked
    resp_pubchem = client.get("/api/v1/connectors/pubchem/search?query=aspirin")
    assert resp_pubchem.status_code == 422
    assert resp_pubchem.json()["error"]["code"] == "network_policy_violation"

    # ChEMBL search should be blocked
    resp_chembl = client.get("/api/v1/connectors/chembl/targets?query=EGFR")
    assert resp_chembl.status_code == 422
    assert resp_chembl.json()["error"]["code"] == "network_policy_violation"


def test_cli_fetch_blocked_by_local_policy() -> None:
    from typer.testing import CliRunner

    from hcs_discovery.cli.main import app

    runner = CliRunner()
    result = runner.invoke(app, ["fetch", "pubchem", "aspirin"])
    assert result.exit_code != 0
    assert "blocked by policy" in (result.stdout + result.stderr).lower()


def test_connector_rejects_redirects_instead_of_following_them(remote: Settings) -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(302, headers={"location": "https://evil.example/steal"})

    connector = PubChemConnector(settings=remote, mock_transport=httpx.MockTransport(handler))
    with pytest.raises(ValidationError, match="redirect blocked") as excinfo:
        connector.search_compound_by_name("aspirin")
    assert excinfo.value.details["status"] == 302
    assert len(requested) == 1


def test_connector_reports_malformed_json_instead_of_raising_raw_error(remote: Settings) -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, content=b"{not-json", headers={"content-type": "application/json"})
    )
    connector = ChEMBLConnector(settings=remote, mock_transport=transport)
    with pytest.raises(ValidationError, match="malformed JSON"):
        connector.search_targets("EGFR")


def test_connector_404_is_explicit_unless_caller_opts_into_absence(remote: Settings) -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(404, text="not found"))
    connector = ChEMBLConnector(settings=remote, mock_transport=transport)
    with pytest.raises(ValidationError, match="not found") as excinfo:
        connector.search_targets("EGFR")
    assert excinfo.value.details["status"] == 404

    pubchem = PubChemConnector(settings=remote, mock_transport=_not_found_transport())
    assert pubchem.search_compound_by_name("aspirin") == []
    assert pubchem.search_compound_by_cid(999999) is None


def _not_found_transport() -> httpx.MockTransport:
    return httpx.MockTransport(lambda _request: httpx.Response(404, text="not found"))


def test_allowlist_host_normalisation_rejects_lookalikes(settings: Settings) -> None:
    remote = settings.model_copy(update={"network_policy": "remote"})
    check_network_allowed("PubChem.NCBI.NLM.NIH.gov.", settings=remote)
    check_network_allowed("www.ebi.ac.uk:443", settings=remote)

    with pytest.raises(NetworkPolicyViolationError):
        check_network_allowed("pubchem.ncbi.nlm.nih.gov.evil.example", settings=remote)
    with pytest.raises(NetworkPolicyViolationError):
        check_network_allowed("pubch\u0435m.ncbi.nlm.nih.gov", settings=remote)
    with pytest.raises(NetworkPolicyViolationError):
        check_network_allowed("", settings=remote)


def _json(payload: dict, **headers: str) -> httpx.Response:
    return httpx.Response(200, json=payload, headers=headers)


def test_pubchem_record_maps_current_property_names_and_checks_structure(remote: Settings) -> None:
    connector = PubChemConnector(
        settings=remote, mock_transport=httpx.MockTransport(lambda _r: _json(MOCK_PUBCHEM_ASPIRIN_RESPONSE))
    )
    data = connector.search_compound_by_cid(2244).data  # type: ignore[union-attr]
    assert data["isomeric_smiles"] == "CC(=O)OC1=CC=CC=C1C(=O)O"
    assert data["canonical_smiles"] == "CC(=O)OC1=CC=CC=C1C(=O)O"
    assert data["molecular_weight"] == 180.16
    assert data["structure_check"] == "consistent"


def test_pubchem_requests_the_current_smiles_properties(remote: Settings) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return _json(MOCK_PUBCHEM_ASPIRIN_RESPONSE)

    PubChemConnector(settings=remote, mock_transport=httpx.MockTransport(handler)).search_compound_by_name("aspirin")
    assert "/property/SMILES,ConnectivitySMILES,InChIKey," in seen[0]


def test_pubchem_legacy_property_names_are_still_read(remote: Settings) -> None:
    legacy = {
        "PropertyTable": {
            "Properties": [
                {
                    "CID": 702,
                    "CanonicalSMILES": "CCO",
                    "IsomericSMILES": "CCO",
                    "InChIKey": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
                    "MolecularWeight": 46.07,
                }
            ]
        }
    }
    connector = PubChemConnector(settings=remote, mock_transport=httpx.MockTransport(lambda _r: _json(legacy)))
    data = connector.search_compound_by_cid(702).data  # type: ignore[union-attr]
    assert (data["isomeric_smiles"], data["structure_check"]) == ("CCO", "consistent")


def test_structure_check_reports_inconsistent_provider_records() -> None:
    assert structure_check("CCO", "LFQSCWFLJHTTHZ-UHFFFAOYSA-N") == "consistent"
    assert structure_check("CCN", "LFQSCWFLJHTTHZ-UHFFFAOYSA-N") == "inchikey_mismatch"
    assert structure_check("C1CC", "LFQSCWFLJHTTHZ-UHFFFAOYSA-N") == "unparseable_smiles"
    assert structure_check(None, "LFQSCWFLJHTTHZ-UHFFFAOYSA-N") == "missing_smiles"
    assert structure_check("CCO", None) == "no_inchikey_reported"


def test_policy_is_enforced_even_with_a_mock_transport(settings: Settings) -> None:
    calls: list[httpx.Request] = []
    transport = httpx.MockTransport(lambda request: calls.append(request) or _json({}))
    with pytest.raises(NetworkPolicyViolationError):
        PubChemConnector(settings=settings, mock_transport=transport).search_compound_by_name("aspirin")
    assert calls == []


def test_connector_refuses_plain_http(remote: Settings) -> None:
    connector = ChEMBLConnector(settings=remote, mock_transport=httpx.MockTransport(lambda _r: _json({})))
    with pytest.raises(ValidationError, match="HTTPS"):
        connector.get_json("http://www.ebi.ac.uk/chembl/api/data/target.json")


def test_connector_rejects_non_json_content_type(remote: Settings) -> None:
    transport = httpx.MockTransport(
        lambda _r: httpx.Response(200, content=b"<html>maintenance</html>", headers={"content-type": "text/html"})
    )
    with pytest.raises(ValidationError, match="expected JSON"):
        ChEMBLConnector(settings=remote, mock_transport=transport).search_targets("EGFR")


def test_connector_enforces_payload_ceiling_while_streaming(remote: Settings) -> None:
    big = b'{"targets": [' + b'"x",' * (MAX_PAYLOAD_BYTES // 4) + b'"x"]}'
    transport = httpx.MockTransport(
        lambda _r: httpx.Response(200, content=iter([big]), headers={"content-type": "application/json"})
    )
    with pytest.raises(ValidationError, match="exceeds ceiling"):
        ChEMBLConnector(settings=remote, mock_transport=transport).search_targets("EGFR")

    declared = httpx.MockTransport(
        lambda _r: httpx.Response(
            200,
            content=b"{}",
            headers={"content-type": "application/json", "content-length": str(MAX_PAYLOAD_BYTES + 1)},
        )
    )
    with pytest.raises(ValidationError, match="exceeds ceiling"):
        ChEMBLConnector(settings=remote, mock_transport=declared).search_targets("EGFR")


def test_connector_retries_rate_limits_honouring_capped_retry_after(remote: Settings, monkeypatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(connector_base.time, "sleep", sleeps.append)
    responses = iter(
        [
            httpx.Response(429, headers={"retry-after": "3"}),
            httpx.Response(503, headers={"retry-after": "3600"}),
            _json(MOCK_CHEMBL_EGFR_RESPONSE),
        ]
    )
    transport = httpx.MockTransport(lambda _r: next(responses))
    records = ChEMBLConnector(settings=remote, mock_transport=transport).search_targets("EGFR")
    assert len(records) == 1
    assert sleeps == [3.0, connector_base.MAX_RETRY_AFTER_SECONDS]


def test_connector_reports_persistent_server_errors(remote: Settings, monkeypatch) -> None:
    monkeypatch.setattr(connector_base.time, "sleep", lambda _s: None)
    calls: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(502, text="bad gateway")

    with pytest.raises(ValidationError, match="status 502") as excinfo:
        ChEMBLConnector(settings=remote, mock_transport=httpx.MockTransport(handler)).search_targets("EGFR")
    assert excinfo.value.details["status"] == 502
    assert len(calls) == 3


def test_connector_reports_timeouts_after_retrying(remote: Settings, monkeypatch) -> None:
    monkeypatch.setattr(connector_base.time, "sleep", lambda _s: None)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(ValidationError, match="Network error"):
        ChEMBLConnector(settings=remote, mock_transport=httpx.MockTransport(handler)).search_targets("EGFR")


@pytest.mark.network
def test_live_pubchem_returns_a_consistent_structure(tmp_path) -> None:
    """Opt-in (``-m network``): guards against provider schema changes like PubChem's 2025 SMILES rename."""
    live = Settings(data_dir=tmp_path / "data", network_policy="remote")
    record = PubChemConnector(settings=live).search_compound_by_cid(2244)
    assert record is not None
    assert record.data["isomeric_smiles"]
    assert record.data["structure_check"] == "consistent"
