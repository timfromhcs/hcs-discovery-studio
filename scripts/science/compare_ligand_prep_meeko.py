"""Compare HCS ligand PDBQT preparation against Meeko on the repository fixtures.

Meeko (LGPL-2.1) is not a project dependency. Run this in a separate environment
that has both this project and Meeko installed, for example::

    uv venv .meeko-venv
    uv pip install --python .meeko-venv/Scripts/python.exe -e . meeko==0.8.0 scipy gemmi
    .meeko-venv/Scripts/python.exe scripts/science/compare_ligand_prep_meeko.py

For each fixture ligand it compares the torsion count (TORSDOF), the number of
PDBQT atoms after non-polar hydrogen merging, the size of the ROOT rigid group and
the multiset of (AutoDock type, Gasteiger charge rounded to 0.001). Geometry is not
compared: both tools embed independently. The report is written as JSON and
Markdown under docs/validation.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = (
    ROOT / "tests" / "fixtures" / "e2e_library.csv",
    ROOT / "tests" / "fixtures" / "esol_solubility_challenge.json",
)


def _ligands() -> list[tuple[str, str]]:
    ligands: list[tuple[str, str]] = []
    with FIXTURES[0].open(encoding="utf-8") as handle:
        ligands.extend((row["name"], row["smiles"]) for row in csv.DictReader(handle))
    records = json.loads(FIXTURES[1].read_text(encoding="utf-8"))["records"]
    ligands.extend((str(r.get("name") or r.get("id")), r["smiles"]) for r in records)
    return ligands


def _summary(pdbqt: str) -> dict[str, object]:
    atoms: list[tuple[str, float]] = []
    root_atoms = 0
    in_root = False
    torsdof = None
    for line in pdbqt.splitlines():
        if line.startswith("ROOT"):
            in_root = True
        elif line.startswith("ENDROOT"):
            in_root = False
        elif line.startswith(("ATOM", "HETATM")):
            atoms.append((line[77:79].strip(), round(float(line[70:76]), 3)))
            root_atoms += in_root
        elif line.startswith("TORSDOF"):
            torsdof = int(line.split()[1])
    return {
        "torsdof": torsdof,
        "atoms": len(atoms),
        "root_atoms": root_atoms,
        "types_charges": sorted(Counter(atoms).items()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", type=Path, default=ROOT / "docs" / "validation")
    args = parser.parse_args()

    import meeko
    from meeko import MoleculePreparation, PDBQTWriterLegacy
    from rdkit import Chem, rdBase
    from rdkit.Chem import AllChem

    from hcs_discovery.plugins.science.docking.prep import PREPARATION_METHOD, LigandPreparationError, prepare_ligand

    rows = []
    for name, smiles in _ligands():
        row: dict[str, object] = {"name": name, "smiles": smiles}
        try:
            prepared = prepare_ligand(smiles, seed=7)
            ours = _summary(prepared.pdbqt)
        except LigandPreparationError as exc:
            row.update(status="hcs_refused", detail=exc.message)
            rows.append(row)
            continue
        mol = Chem.MolFromSmiles(smiles)
        frags = Chem.GetMolFrags(mol, asMols=True)
        mol = Chem.AddHs(max(frags, key=lambda m: m.GetNumHeavyAtoms()))
        AllChem.EmbedMolecule(mol, randomSeed=7)
        text, ok, error = PDBQTWriterLegacy.write_string(MoleculePreparation().prepare(mol)[0])
        if not ok:
            row.update(status="meeko_failed", detail=error)
            rows.append(row)
            continue
        theirs = _summary(text)
        mismatches = [key for key in ("torsdof", "atoms", "root_atoms", "types_charges") if ours[key] != theirs[key]]
        rigid_macrocycle = any(w.startswith("Macrocycle kept rigid") for w in prepared.warnings)
        if not mismatches:
            status = "match"
        elif rigid_macrocycle:
            # Meeko samples rings of 7+ atoms by opening them with G/CG pseudo-atoms;
            # this preparation keeps them rigid and says so in its warnings.
            status = "known_deviation_rigid_macrocycle"
        else:
            status = "mismatch"
        row.update(
            status=status,
            mismatches=mismatches,
            hcs={k: ours[k] for k in ("torsdof", "atoms", "root_atoms")},
            meeko={k: theirs[k] for k in ("torsdof", "atoms", "root_atoms")},
        )
        rows.append(row)

    counts = Counter(str(row["status"]) for row in rows)
    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "hcs_method": PREPARATION_METHOD,
        "reference": {"tool": "Meeko", "version": meeko.__version__, "license": "LGPL-2.1"},
        "environment": {"python": platform.python_version(), "rdkit": rdBase.rdkitVersion},
        "counts": dict(sorted(counts.items())),
        "ligands": rows,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "ligand-prep-meeko.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Ligand preparation vs. Meeko",
        "",
        "Generated by `scripts/science/compare_ligand_prep_meeko.py`. Compares the HCS PDBQT",
        f"preparation (`{PREPARATION_METHOD}`) with Meeko {meeko.__version__} on the repository",
        "fixture ligands: TORSDOF, PDBQT atom count, ROOT group size and the multiset of",
        "AutoDock types with Gasteiger charges (0.001). Geometry is not compared.",
        "",
        f"- Python {platform.python_version()}, RDKit {rdBase.rdkitVersion}",
        f"- Ligands: {len(rows)}; " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())),
        "",
        "`known_deviation_rigid_macrocycle`: rings of 7 or more atoms are kept rigid here,",
        "whereas Meeko opens them with two pseudo-atoms (hence two extra PDBQT atoms) so",
        "Vina can sample ring conformations. The ligand carries a preparation warning.",
        "",
        "This is a format and convention check against an established tool. It is not a",
        "docking accuracy or pose-recovery benchmark.",
        "",
        "| Ligand | Status | HCS TORSDOF / atoms / root | Meeko TORSDOF / atoms / root | Differs in |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        hcs = row.get("hcs") or {}
        ref = row.get("meeko") or {}
        fmt = lambda d: f"{d.get('torsdof', '–')} / {d.get('atoms', '–')} / {d.get('root_atoms', '–')}"  # noqa: E731
        differs = ", ".join(row.get("mismatches", [])) or row.get("detail", "")
        lines.append(f"| {row['name']} | {row['status']} | {fmt(hcs)} | {fmt(ref)} | {differs} |")
    (args.out_dir / "ligand-prep-meeko.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report["counts"]))
    return 0 if counts.get("mismatch", 0) == 0 and counts.get("meeko_failed", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
