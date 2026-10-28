"""Chemistry tests: standardisation policy, descriptors, depictions."""

from __future__ import annotations

import pytest
from rdkit import Chem

from hcs_discovery.chemistry.depiction import depiction_svg
from hcs_discovery.chemistry.descriptors import DESCRIPTORS, compute_descriptors, descriptor_columns
from hcs_discovery.chemistry.standardize import (
    MoleculeError,
    StandardizeOptions,
    parse_smiles,
    standardize,
)


def test_canonicalisation_is_deterministic():
    first = standardize("OCC")
    second = standardize("CCO")
    assert first.canonical_smiles == second.canonical_smiles == "CCO"
    assert first.inchikey == second.inchikey


def test_stereochemistry_is_preserved_in_isomeric_smiles():
    result = standardize("C[C@H](N)C(=O)O")
    assert "@" in result.isomeric_smiles
    assert "@" not in result.canonical_smiles


def test_salt_stripping_is_default_and_warned():
    result = standardize("CC(=O)[O-].[Na+]")
    assert result.canonical_smiles == "CC(=O)[O-]"
    assert any("counter-ions" in warning for warning in result.warnings)


def test_salts_can_be_kept():
    result = standardize("CC(=O)[O-].[Na+]", StandardizeOptions(strip_salts=False))
    assert "." in result.canonical_smiles


def test_invalid_smiles_raises_validation_error():
    with pytest.raises(MoleculeError):
        standardize("not-a-molecule")
    with pytest.raises(MoleculeError):
        standardize("   ")


def test_atom_limit_is_enforced():
    with pytest.raises(MoleculeError):
        standardize("C" * 500, StandardizeOptions(max_atoms=50))


def test_ethanol_descriptors_match_reference_values():
    values = compute_descriptors("CCO", ["mw", "logp", "tpsa", "hbd", "hba"])
    assert values["mw"]["value"] == pytest.approx(46.069, abs=0.05)
    assert values["hbd"]["value"] == 1
    assert values["hba"]["value"] == 1
    assert values["tpsa"]["value"] == pytest.approx(20.23, abs=0.2)
    assert values["mw"]["unit"] == "g/mol"
    assert values["logp"]["direction"] == "lower"


def test_all_advertised_descriptors_are_computable():
    for key in DESCRIPTORS:
        values = compute_descriptors("CC(=O)Oc1ccccc1C(=O)O", [key])
        assert values[key]["value"] is not None
        assert values[key]["method"]


def test_unknown_descriptor_is_rejected():
    with pytest.raises(ValueError):
        compute_descriptors("CCO", ["not_a_descriptor"])


def test_descriptor_columns_carry_method_and_unit():
    columns = descriptor_columns(["mw", "qed"])
    assert columns[0].unit == "g/mol"
    assert columns[0].method
    assert columns[1].direction == "higher"


def test_smiles_parser_returns_rdkit_molecule():
    assert isinstance(parse_smiles("c1ccccc1"), Chem.Mol)


def test_depiction_is_svg_and_handles_invalid():
    svg = depiction_svg("CCO", width=200, height=120)
    assert svg.lstrip().startswith("<?xml") or svg.lstrip().startswith("<svg")
    assert "<svg" in svg
    with pytest.raises(ValueError):
        depiction_svg("nope")
