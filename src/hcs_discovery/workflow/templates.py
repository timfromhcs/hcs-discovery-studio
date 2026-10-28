"""Built-in workflow templates shown in the UI and used by the demo."""

from __future__ import annotations

from typing import Any

from ..chemistry.descriptors import DEFAULT_DESCRIPTORS


def triage_template() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "id": "triage-basic",
        "name": "Basic triage",
        "description": (
            "Deterministic, offline triage: compute RDKit descriptors, flag rows against editable "
            "drug-likeness-style thresholds, rank survivors by a transparent composite score and "
            "write a summary report. Thresholds are project criteria, not laws."
        ),
        "nodes": [
            {
                "id": "descriptors",
                "type": "chem.descriptors",
                "title": "RDKit descriptors",
                "config": {"descriptors": list(DEFAULT_DESCRIPTORS)},
            },
            {
                "id": "filters",
                "type": "filter.rules",
                "title": "Triage thresholds",
                "config": {
                    "mode": "flag",
                    "rules": [
                        {
                            "column": "mw",
                            "op": "between",
                            "value": 150,
                            "value2": 600,
                            "label": "MW 150-600 g/mol",
                        },
                        {
                            "column": "logp",
                            "op": "between",
                            "value": -1.0,
                            "value2": 5.5,
                            "label": "cLogP -1..5.5",
                        },
                        {"column": "tpsa", "op": "le", "value": 160, "label": "TPSA <= 160 A^2"},
                        {"column": "hbd", "op": "le", "value": 5, "label": "HBD <= 5"},
                        {"column": "hba", "op": "le", "value": 10, "label": "HBA <= 10"},
                        {
                            "column": "rotb",
                            "op": "le",
                            "value": 10,
                            "label": "Rotatable bonds <= 10",
                        },
                    ],
                },
            },
            {
                "id": "ranking",
                "type": "rank.pareto",
                "title": "Pareto + composite ranking",
                "config": {
                    "objectives": [
                        {"column": "qed", "direction": "higher", "weight": 1.5},
                        {"column": "tpsa", "direction": "lower", "weight": 1.0},
                        {"column": "logp", "direction": "lower", "weight": 1.0},
                        {"column": "mw", "direction": "lower", "weight": 0.5},
                    ]
                },
            },
            {
                "id": "summary",
                "type": "report.summary",
                "title": "Summary report",
                "config": {"title": "Basic triage summary", "top_n": 10},
            },
        ],
        "edges": [
            {"source": "descriptors", "target": "filters"},
            {"source": "filters", "target": "ranking"},
            {"source": "ranking", "target": "summary"},
        ],
    }


def similarity_template() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "id": "similarity-triage",
        "name": "Similarity triage",
        "description": "Rank library members by Morgan/Tanimoto similarity to a query structure.",
        "nodes": [
            {
                "id": "similarity",
                "type": "chem.similarity",
                "title": "Similarity to query",
                "config": {"query_smiles": "CC(=O)Oc1ccccc1C(=O)O", "radius": 2, "bits": 2048},
            },
            {
                "id": "ranking",
                "type": "rank.pareto",
                "title": "Similarity ranking",
                "config": {"objectives": [{"column": "similarity_query", "direction": "higher", "weight": 1.0}]},
            },
        ],
        "edges": [{"source": "similarity", "target": "ranking"}],
    }


def minimal_template() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "id": "descriptors-only",
        "name": "Descriptors only",
        "description": "Compute RDKit descriptors and export the table. Useful as a starting point.",
        "nodes": [
            {
                "id": "descriptors",
                "type": "chem.descriptors",
                "title": "RDKit descriptors",
                "config": {"descriptors": list(DEFAULT_DESCRIPTORS)},
            }
        ],
        "edges": [],
    }


def templates() -> list[dict[str, Any]]:
    return [triage_template(), similarity_template(), minimal_template()]
