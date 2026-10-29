"""EMBL-EBI ChEMBL web services connector for targets, compounds and bioactivities."""

from __future__ import annotations

import httpx

from ...core.config import Settings
from ...core.errors import ValidationError
from .base import BaseConnector, ConnectorRecord

CHEMBL_BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"
CHEMBL_LICENSE = "Creative Commons Attribution-ShareAlike 3.0 Unported (CC-BY-SA 3.0 - EMBL-EBI ChEMBL)"


class ChEMBLConnector(BaseConnector):
    """Client for EMBL-EBI ChEMBL Web Services."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        mock_transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__(settings=settings, mock_transport=mock_transport, rate_limit_delay=0.25)

    def search_targets(self, query: str, *, limit: int = 20) -> list[ConnectorRecord]:
        """Search biological targets in ChEMBL by target name, gene, or organism."""
        cleaned = query.strip()
        if not cleaned:
            raise ValidationError("Target search query cannot be empty.")

        url = f"{CHEMBL_BASE_URL}/target/search.json"
        res_json = self.get_json(url, params={"q": cleaned, "limit": limit}) or {}
        targets = res_json.get("targets", [])
        records: list[ConnectorRecord] = []
        retrieval_time = self.now_iso()

        for item in targets:
            chembl_id = item.get("target_chembl_id", "")
            record_data = {
                "target_chembl_id": chembl_id,
                "pref_name": item.get("pref_name"),
                "target_type": item.get("target_type"),
                "organism": item.get("organism"),
                "score": item.get("score"),
            }
            records.append(
                ConnectorRecord(
                    source="ChEMBL",
                    external_id=chembl_id,
                    source_url=f"https://www.ebi.ac.uk/chembl/target_report_card/{chembl_id}/",
                    retrieval_time=retrieval_time,
                    license=CHEMBL_LICENSE,
                    data=record_data,
                    content_hash=self.hash_payload(record_data),
                )
            )

        return records

    def search_compounds(self, query: str, *, limit: int = 20) -> list[ConnectorRecord]:
        """Search small molecule compounds in ChEMBL by chemical name or synonym."""
        cleaned = query.strip()
        if not cleaned:
            raise ValidationError("Compound search query cannot be empty.")

        url = f"{CHEMBL_BASE_URL}/molecule/search.json"
        res_json = self.get_json(url, params={"q": cleaned, "limit": limit}) or {}
        molecules = res_json.get("molecules", [])
        records: list[ConnectorRecord] = []
        retrieval_time = self.now_iso()

        for item in molecules:
            chembl_id = item.get("molecule_chembl_id", "")
            structures = item.get("molecule_structures") or {}
            record_data = {
                "molecule_chembl_id": chembl_id,
                "pref_name": item.get("pref_name"),
                "max_phase": item.get("max_phase"),
                "molecule_type": item.get("molecule_type"),
                "canonical_smiles": structures.get("canonical_smiles"),
                "standard_inchi_key": structures.get("standard_inchi_key"),
            }
            records.append(
                ConnectorRecord(
                    source="ChEMBL",
                    external_id=chembl_id,
                    source_url=f"https://www.ebi.ac.uk/chembl/compound_report_card/{chembl_id}/",
                    retrieval_time=retrieval_time,
                    license=CHEMBL_LICENSE,
                    data=record_data,
                    content_hash=self.hash_payload(record_data),
                )
            )

        return records

    def get_target_activities(self, target_chembl_id: str, *, limit: int = 50) -> list[ConnectorRecord]:
        """Retrieve reported experimental bioactivities for a specific ChEMBL target."""
        cleaned_id = target_chembl_id.strip()
        if not cleaned_id:
            raise ValidationError("Target ChEMBL ID cannot be empty.")

        url = f"{CHEMBL_BASE_URL}/activity.json"
        res_json = self.get_json(url, params={"target_chembl_id": cleaned_id, "limit": limit}) or {}
        activities = res_json.get("activities", [])
        records: list[ConnectorRecord] = []
        retrieval_time = self.now_iso()

        for item in activities:
            act_id = str(item.get("activity_id", ""))
            record_data = {
                "activity_id": act_id,
                "target_chembl_id": cleaned_id,
                "molecule_chembl_id": item.get("molecule_chembl_id"),
                "standard_type": item.get("standard_type"),
                "standard_relation": item.get("standard_relation"),
                "standard_value": item.get("standard_value"),
                "standard_units": item.get("standard_units"),
                "assay_type": item.get("assay_type"),
                "pchembl_value": item.get("pchembl_value"),
            }
            records.append(
                ConnectorRecord(
                    source="ChEMBL",
                    external_id=f"ACT:{act_id}",
                    source_url=f"https://www.ebi.ac.uk/chembl/activity_report_card/{act_id}/",
                    retrieval_time=retrieval_time,
                    license=CHEMBL_LICENSE,
                    data=record_data,
                    content_hash=self.hash_payload(record_data),
                )
            )

        return records
