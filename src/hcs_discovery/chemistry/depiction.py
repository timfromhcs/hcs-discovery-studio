"""2D molecular depictions rendered locally with RDKit (no network, no JS library)."""

from __future__ import annotations

from rdkit import Chem
from rdkit.Chem.Draw import rdMolDraw2D


def depiction_svg(smiles: str, *, width: int = 360, height: int = 240, theme: str = "dark") -> str:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError("Invalid SMILES")
    drawer = rdMolDraw2D.MolDraw2DSVG(width, height)
    options = drawer.drawOptions()
    options.clearBackground = False
    options.bondLineWidth = 2.0
    options.minFontSize = 12
    options.maxFontSize = 20
    if theme == "dark":
        options.setBackgroundColour((0.07, 0.09, 0.12, 1.0))
        options.setSymbolColour((0.90, 0.93, 0.97, 1.0))
        options.setAnnotationColour((0.75, 0.81, 0.90, 1.0))
    else:
        options.setBackgroundColour((1.0, 1.0, 1.0, 1.0))
        options.setSymbolColour((0.10, 0.12, 0.16, 1.0))
    drawer.DrawMolecule(mol)
    drawer.FinishDrawing()
    svg = drawer.GetDrawingText().replace("svg:", "")
    return svg
