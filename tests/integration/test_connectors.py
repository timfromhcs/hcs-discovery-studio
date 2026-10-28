"""Integration tests for external data connectors with mock transports and policy gating."""

from __future__ import annotations

import httpx
import pytest
from starlette.testclient import TestClient

from hcs_discovery.core.config import Settings
from hcs_discovery.plugins.connectors.chembl import ChEMBLConnector
from hcs_discovery.plugins.connectors.policy import NetworkPolicyViolationError
from hcs_discovery.plugins.connectors.pubchem import PubChemConnector

MOCK_PUBCHEM_ASPIRIN_RESPONSE = {
    "PropertyTable": {
        "Properties": [
            {
                "CID": 2244,
                "CanonicalSMILES": "CC(=O)OC1=CC=CC=C1C(=O)O",
                "IsomericSMILES": "CC(=O)OC1=CC=CC=C1C(=O)O",
                "InChIKey": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
                "MolecularFormula": "C9H8O4",
                "MolecularWeight": 180.16,
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


def test_pubchem_search_with_mock_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "pubchem.ncbi.nlm.nih.gov" in request.url.host
        assert "aspirin" in str(request.url).lower()
        return httpx.Response(200, json=MOCK_PUBCHEM_ASPIRIN_RESPONSE)

    transport = httpx.MockTransport(handler)
    connector = PubChemConnector(mock_transport=transport)
    records = connector.search_compound_by_name("aspirin")

    assert len(records) == 1
    rec = records[0]
    assert rec.source == "PubChem"
    assert rec.external_id == "CID:2244"
    assert rec.data["canonical_smiles"] == "CC(=O)OC1=CC=CC=C1C(=O)O"
    assert rec.data["molecular_weight"] == 180.16
    assert "CC0" in rec.license
    assert rec.content_hash is not None


def test_chembl_search_targets_with_mock_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "www.ebi.ac.uk" in request.url.host
        if "/target/search.json" in str(request.url):
            return httpx.Response(200, json=MOCK_CHEMBL_EGFR_RESPONSE)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    connector = ChEMBLConnector(mock_transport=transport)
    records = connector.search_targets("EGFR")

    assert len(records) == 1
    rec = records[0]
    assert rec.source == "ChEMBL"
    assert rec.external_id == "CHEMBL203"
    assert rec.data["pref_name"] == "Epidermal growth factor receptor erbB1"
    assert rec.data["organism"] == "Homo sapiens"
    assert "CC-BY-SA" in rec.license


def test_chembl_search_compounds_and_activities_mock() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "/molecule/search.json" in url_str:
            return httpx.Response(200, json=MOCK_CHEMBL_ASPIRIN_RESPONSE)
        if "/activity.json" in url_str:
            return httpx.Response(200, json=MOCK_CHEMBL_ACTIVITIES_RESPONSE)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    connector = ChEMBLConnector(mock_transport=transport)

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
