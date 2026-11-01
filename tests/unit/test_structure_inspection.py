"""Inspection of PDB coordinate files.

The fixture is hand-written test data (see the REMARK record in the file). It is
not a real structure and must never be used for science.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hcs_discovery.core.errors import ValidationError
from hcs_discovery.structures.pdb import (
    ION_RESIDUES,
    MAX_STRUCTURE_BYTES,
    WATER_RESIDUES,
    StructureFormatError,
    detect_format,
    inspect_pdb,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "structures" / "tiny_two_chain.pdb"


def test_inspection_reports_chains_residues_and_hetero_groups():
    inspection = inspect_pdb(FIXTURE)
    assert inspection.format == "pdb"
    assert inspection.atom_count == 9
    assert inspection.pdb_id == "1TST"
    assert inspection.title is not None and inspection.title.startswith("SYNTHETIC TWO-CHAIN")
    chains = {chain.chain_id: chain for chain in inspection.chains}
    assert set(chains) == {"A", "B"}
    assert chains["A"].residue_count == 3  # residues 1, 2 and 5
    assert chains["A"].atom_count == 5
    assert chains["B"].residue_count == 1


def test_missing_residues_are_reported_as_a_gap_not_imputed():
    inspection = inspect_pdb(FIXTURE)
    chain_a = next(chain for chain in inspection.chains if chain.chain_id == "A")
    assert chain_a.missing_residue_count == 2
    assert [gap.as_dict() for gap in chain_a.gaps] == [
        {"after_residue": 2, "missing_from": 3, "missing_to": 4, "count": 2}
    ]
    assert any("gaps" in warning for warning in inspection.warnings)


def test_ligands_waters_and_ions_are_separated():
    inspection = inspect_pdb(FIXTURE)
    assert inspection.ligands == ("LIG",)
    assert inspection.waters == 1
    assert inspection.ions == ("ZN",)
    assert "HOH" in WATER_RESIDUES and "ZN" in ION_RESIDUES


def test_alternate_locations_are_reported():
    inspection = inspect_pdb(FIXTURE)
    assert inspection.alternate_locations == ("A", "B")
    assert any("Alternate locations" in warning for warning in inspection.warnings)


def test_inspection_is_serialisable_and_keeps_units_out_of_it():
    payload = inspect_pdb(FIXTURE).as_dict()
    assert payload["filename"].endswith(".pdb")
    assert payload["size_bytes"] > 0
    assert payload["chains"][0]["chain_id"] == "A"
    assert payload["ligands"] == ["LIG"]


def test_mmcif_is_refused_instead_of_half_parsed():
    with pytest.raises(StructureFormatError) as excinfo:
        detect_format("1abc.cif")
    assert excinfo.value.code == "unsupported_format"
    assert "not supported" in excinfo.value.message


def test_unknown_extension_is_refused_with_the_supported_list():
    with pytest.raises(StructureFormatError) as excinfo:
        detect_format("structure.xyz")
    assert excinfo.value.details["supported"] == ["pdb", "ent"]


def test_empty_file_is_rejected(tmp_path: Path):
    empty = tmp_path / "empty.pdb"
    empty.write_bytes(b"")
    with pytest.raises(ValidationError) as excinfo:
        inspect_pdb(empty)
    assert "empty" in excinfo.value.message


def test_file_without_coordinates_is_rejected(tmp_path: Path):
    header_only = tmp_path / "header.pdb"
    header_only.write_text("HEADER    NOTHING HERE\nEND\n", encoding="utf-8")
    with pytest.raises(ValidationError) as excinfo:
        inspect_pdb(header_only)
    assert excinfo.value.code == "validation_error"
    assert "no ATOM or HETATM" in excinfo.value.message


def test_oversized_file_is_rejected_before_parsing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    big = tmp_path / "big.pdb"
    big.write_bytes(b"ATOM  " + b"x" * 2048)
    monkeypatch.setattr("hcs_discovery.structures.pdb.MAX_STRUCTURE_BYTES", 1024)
    with pytest.raises(ValidationError) as excinfo:
        inspect_pdb(big)
    assert "too large" in excinfo.value.message
    assert MAX_STRUCTURE_BYTES >= 1024


def test_no_models_record_still_counts_as_one(tmp_path: Path):
    path = tmp_path / "single.pdb"
    path.write_text(
        "ATOM      1 N    ALA A   1       1.000   2.000   3.000  1.00 20.00           N\nEND\n",
        encoding="utf-8",
    )
    inspection = inspect_pdb(path)
    assert inspection.model_count == 1
    assert inspection.atom_count == 1
    assert inspection.warnings == ()
