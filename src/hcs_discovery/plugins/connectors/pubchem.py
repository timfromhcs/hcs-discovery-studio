"""PubChem PUG REST connector with provenance retention and rate limiting."""

from __future__ import annotations

import urllib.parse

import httpx

from ...core.config import Settings
from ...core.errors import ValidationError
from .base import BaseConnector, ConnectorRecord

PUBCHEM_BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PUBCHEM_LICENSE = "Public Domain (CC0 - US National Library of Medicine / NIH PubChem)"


class PubChemConnector(BaseConnector):
    """Client for NCBI PubChem PUG REST API."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        mock_transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__(settings=settings, mock_transport=mock_transport, rate_limit_delay=0.25)

    def search_compound_by_name(self, name: str) -> list[ConnectorRecord]:
        """Search PubChem compound properties by chemical or generic name."""
        cleaned = name.strip()
        if not cleaned:
            raise ValidationError("Search query cannot be empty.")

        encoded_name = urllib.parse.quote(cleaned)
        url = (
            f"{PUBCHEM_BASE_URL}/compound/name/{encoded_name}/property/"
            "CanonicalSMILES,IsomericSMILES,InChIKey,MolecularFormula,MolecularWeight,IUPACName/JSON"
        )

        res_json = self.get_json(url, allow_not_found=True)
        if res_json is None:
            return []
        props = res_json.get("PropertyTable", {}).get("Properties", [])
        records: list[ConnectorRecord] = []
        retrieval_time = self.now_iso()

        for item in props:
            cid = str(item.get("CID", ""))
            record_data = {
                "cid": item.get("CID"),
                "canonical_smiles": item.get("CanonicalSMILES"),
                "isomeric_smiles": item.get("IsomericSMILES"),
                "inchikey": item.get("InChIKey"),
                "formula": item.get("MolecularFormula"),
                "molecular_weight": item.get("MolecularWeight"),
                "iupac_name": item.get("IUPACName"),
            }
            records.append(
                ConnectorRecord(
                    source="PubChem",
                    external_id=f"CID:{cid}",
                    source_url=f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
                    retrieval_time=retrieval_time,
                    license=PUBCHEM_LICENSE,
                    data=record_data,
                    content_hash=self.hash_payload(record_data),
                )
            )

        return records

    def search_compound_by_cid(self, cid: int) -> ConnectorRecord | None:
        """Fetch compound details by PubChem CID."""
        url = (
            f"{PUBCHEM_BASE_URL}/compound/cid/{cid}/property/"
            "CanonicalSMILES,IsomericSMILES,InChIKey,MolecularFormula,MolecularWeight,IUPACName/JSON"
        )
        res_json = self.get_json(url, allow_not_found=True)
        if res_json is None:
            return None
        props = res_json.get("PropertyTable", {}).get("Properties", [])
        if not props:
            return None

        item = props[0]
        record_data = {
            "cid": item.get("CID"),
            "canonical_smiles": item.get("CanonicalSMILES"),
            "isomeric_smiles": item.get("IsomericSMILES"),
            "inchikey": item.get("InChIKey"),
            "formula": item.get("MolecularFormula"),
            "molecular_weight": item.get("MolecularWeight"),
            "iupac_name": item.get("IUPACName"),
        }
        return ConnectorRecord(
            source="PubChem",
            external_id=f"CID:{cid}",
            source_url=f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
            retrieval_time=self.now_iso(),
            license=PUBCHEM_LICENSE,
            data=record_data,
            content_hash=self.hash_payload(record_data),
        )
