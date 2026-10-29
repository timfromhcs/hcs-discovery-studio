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


@pytest.mark.parametrize(
    "smiles",
    ["C(C)(C)(C)(C)C", "c1cccc1", "C1CC", "[Xx]", "N(=O)=O=O"],
)
def test_invalid_valences_and_unclosed_rings_are_row_errors(smiles):
    with pytest.raises(MoleculeError):
        standardize(smiles)


def test_explicit_and_implicit_hydrogens_give_the_same_identity():
    assert standardize("[H]OC([H])([H])C([H])([H])[H]").isomeric_smiles == standardize("CCO").isomeric_smiles


def test_stereoisomers_are_distinct_but_share_the_flat_canonical_smiles():
    r = standardize("C[C@H](N)C(=O)O")
    s = standardize("C[C@@H](N)C(=O)O")
    assert r.isomeric_smiles != s.isomeric_smiles
    assert r.inchikey != s.inchikey
    assert r.canonical_smiles == s.canonical_smiles


def test_charged_species_are_kept_unless_neutralisation_is_requested():
    kept = standardize("C[NH3+]")
    assert kept.formal_charge == 1
    assert not kept.warnings
    neutral = standardize("C[NH3+]", StandardizeOptions(neutralize=True))
    assert neutral.formal_charge == 0
    assert neutral.warnings == ["Formal charges neutralised where chemically valid."]


def test_optional_steps_only_report_changes_they_made():
    unchanged = standardize("CCO", StandardizeOptions(neutralize=True, canonical_tautomer=True))
    assert unchanged.warnings == []
    tautomer = standardize("Oc1ccccn1", StandardizeOptions(canonical_tautomer=True))
    assert tautomer.warnings == ["Canonical tautomer applied."]
    assert tautomer.isomeric_smiles == "O=c1cccc[nH]1"


def test_multi_component_records_report_the_kept_fragment():
    result = standardize("CC(=O)[O-].[Na+].O")
    assert result.isomeric_smiles == "CC(=O)[O-]"
    assert "3 components -> 1" in result.warnings[0]


@pytest.mark.parametrize(
    ("smiles", "formula"), [("[Se]1C=CC=C1", "C4H4Se"), ("B(O)(O)c1ccccc1", "C6H7BO2"), ("[Si](C)(C)(C)C", "C4H12Si")]
)
def test_uncommon_elements_standardise_with_identifiers(smiles, formula):
    result = standardize(smiles)
    assert result.formula == formula
    assert result.inchikey and len(result.inchikey) == 27


def test_unexpected_errors_are_not_converted_into_warnings(monkeypatch):
    import hcs_discovery.chemistry.standardize as module

    class Broken:
        def choose(self, mol):
            raise AttributeError("defect, not chemistry")

    monkeypatch.setattr(module.rdMolStandardize, "LargestFragmentChooser", Broken)
    with pytest.raises(AttributeError):
        standardize("CCO.O")


def test_rdkit_chemistry_failures_become_recorded_warnings(monkeypatch):
    import hcs_discovery.chemistry.standardize as module

    class Failing:
        def uncharge(self, mol):
            raise ValueError("cannot uncharge\nsecond line")

    monkeypatch.setattr(module.rdMolStandardize, "Uncharger", Failing)
    result = standardize("C[NH3+]", StandardizeOptions(neutralize=True))
    assert result.warnings == ["Neutralisation skipped: ValueError: cannot uncharge"]
    assert result.formal_charge == 1
