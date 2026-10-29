"""Model/engine registry built from real local probes.

Nothing here is reported as runnable unless it can actually execute on this host.
Planned engines are listed as ``planned`` and are never offered as workflow nodes.
"""

from __future__ import annotations

import rdkit
from sqlalchemy.orm import Session

from ..core.config import Settings
from ..core.errors import NotFoundError
from ..plugins.llm.openai_compat import build_provider
from ..plugins.science.docking.vina import (
    ADAPTER_ID as VINA_ID,
)
from ..plugins.science.docking.vina import (
    SCIENTIFIC_CAVEAT as VINA_CAVEAT,
)
from ..plugins.science.docking.vina import (
    probe_vina,
)
from ..plugins.science.properties.adapter import (
    ADAPTER_ID as PROP_PRED_ID,
)
from ..plugins.science.properties.adapter import (
    probe_property_predictor,
)
from ..schemas.models import AdapterCard, LicenseInfo, ResourceProfile

RDKIT_BSL = LicenseInfo(code="BSD-3-Clause", weights="n/a", data="n/a")


def _rdkit_card() -> AdapterCard:
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors

        mol = Chem.MolFromSmiles("CCO")
        ok = mol is not None and Descriptors.MolWt(mol) > 0
        status = "available" if ok else "unavailable"
        notes = [
            "Deterministic chemistry baseline: parsing, standardisation, descriptors, fingerprints, depictions.",
            "Vulkan is not used; descriptors are CPU computations.",
        ]
        if not ok:
            notes.append("RDKit failed a self-test on this host.")
    except Exception as exc:
        status = "unavailable"
        notes = [f"Import failed: {type(exc).__name__}"]
    return AdapterCard(
        id="science:rdkit",
        display_name="RDKit",
        category="chemistry",
        version=rdkit.__version__,
        license=RDKIT_BSL,
        capabilities=[
            "parse_smiles",
            "standardize",
            "descriptors",
            "fingerprints",
            "similarity",
            "depiction",
        ],
        device_providers=["cpu"],
        network_required=False,
        resource_profile=ResourceProfile(ram_mb_min=256),
        status=status,  # type: ignore[arg-type]
        citation_url="https://www.rdkit.org/docs/Citing.html",
        documentation_url="https://www.rdkit.org/docs/",
        notes=notes,
    )


def _llm_card(settings: Settings, *, probe: bool) -> AdapterCard:
    provider = build_provider(settings)
    meta = provider.metadata()
    health = provider.probe() if probe and provider.configured else None
    status = "not_configured"
    notes = [
        "Local OpenAI-compatible endpoints only by default (llama.cpp, LM Studio, ...).",
        "The LLM drafts research text; it never executes tools without explicit approval.",
    ]
    if provider.configured:
        status = "available_with_limits"
        notes.insert(0, f"Endpoint: {provider.base_url}")
        if health is not None:
            notes.insert(0, f"Probe: {health.status} — {health.detail}")
            if health.status == "unreachable":
                status = "unavailable"
    return AdapterCard(
        id=meta["id"],
        display_name=meta["display_name"],
        category="llm",
        version="openai-compatible/1",
        license=LicenseInfo(code="client-code Apache-2.0", weights="provider-specific", data="provider-specific"),
        capabilities=["chat", "requirements_drafting"],
        device_providers=["cpu", "vulkan-via-provider"],
        network_required=meta["network_required"],
        resource_profile=ResourceProfile(),
        status=status,  # type: ignore[arg-type]
        documentation_url="https://platform.openai.com/docs/api-reference",
        notes=notes,
        implemented=True,
    )


def _vina_card(settings: Settings, *, probe: bool) -> AdapterCard:
    probe_res = probe_vina(settings)
    status = probe_res["status"]
    notes = [
        "CPU molecular docking baseline: search space definition, ligand preparation, empirical scoring.",
        probe_res["detail"],
        VINA_CAVEAT,
    ]
    if status == "not_configured":
        notes.append(probe_res.get("remediation", ""))

    return AdapterCard(
        id=VINA_ID,
        display_name="AutoDock Vina",
        category="docking",
        version=probe_res.get("version") or "unknown",
        license=LicenseInfo(code="Apache-2.0", weights="n/a", data="n/a"),
        capabilities=["docking", "pose_search", "binding_affinity"],
        device_providers=["cpu"],
        network_required=False,
        resource_profile=ResourceProfile(ram_mb_min=512),
        status=status,
        citation_url="https://doi.org/10.1021/acs.jcim.1c00203",
        documentation_url="https://autodock-vina.readthedocs.io/",
        notes=notes,
        implemented=True,
    )


def _property_predictor_card() -> AdapterCard:
    probe_res = probe_property_predictor()
    notes = [
        (
            "Literature-derived molecular property models: ESOL aqueous solubility and CNS MPO "
            "BBB scoring, with uncertainty and applicability-domain flags."
        ),
        probe_res["detail"],
        (
            "Measured ESOL accuracy on an independent challenge set is modest "
            "(RMSE 0.97, R^2 0.07 log10 units); see docs/validation/esol-solubility.md."
        ),
    ]
    return AdapterCard(
        id=PROP_PRED_ID,
        display_name="Property Predictor",
        category="property",
        version="1.1.0",
        license=LicenseInfo(
            code="Apache-2.0",
            weights="open-literature",
            data="Delaney-2004/Wager-2010",
        ),
        capabilities=[
            "property_prediction",
            "solubility",
            "cns_bbb",
            "uncertainty_estimation",
            "applicability_domain",
        ],
        device_providers=["cpu"],
        network_required=False,
        resource_profile=ResourceProfile(ram_mb_min=256),
        status="available",
        citation_url="https://doi.org/10.1021/ci034243x",
        documentation_url="https://doi.org/10.1021/ci034243x",
        notes=notes,
        implemented=True,
    )


def _planned_cards() -> list[AdapterCard]:
    planned = [
        (
            "science:openmm",
            "OpenMM",
            "simulation",
            "MIT / LGPL dependencies",
            "Molecular dynamics. Planned; no simulation engine is bundled yet.",
            "https://github.com/openmm/openmm",
            ["molecular_dynamics"],
        ),
        (
            "science:chemprop",
            "Chemprop",
            "property",
            "MIT",
            "Message-passing property prediction. Planned; requires validated model weights per endpoint.",
            "https://github.com/chemprop/chemprop",
            ["property_prediction", "admet"],
        ),
        (
            "science:boltz2",
            "Boltz-2",
            "structure",
            "MIT (repository; audit weights separately)",
            "Structure/affinity research model. Planned; large weights and GPU-class hardware required.",
            "https://github.com/jwohlwend/boltz",
            ["structure_prediction", "affinity_research"],
        ),
        (
            "science:chai1",
            "Chai-1",
            "structure",
            "Apache-2.0 (repository; audit weights separately)",
            "Co-folding research model. Planned; hardware requirements are high.",
            "https://github.com/chaidiscovery/chai-lab",
            ["structure_prediction"],
        ),
    ]
    cards = []
    for id_, name, category, license_note, note, url, capabilities in planned:
        cards.append(
            AdapterCard(
                id=id_,
                display_name=name,
                category=category,  # type: ignore[arg-type]
                version="unknown",
                license=LicenseInfo(code=license_note),
                capabilities=capabilities,
                device_providers=["cpu"],
                network_required=False,
                resource_profile=ResourceProfile(),
                status="planned",
                citation_url=url,
                documentation_url=url,
                notes=[note],
                implemented=False,
            )
        )
    return cards


def list_models(session: Session, settings: Settings, *, probe: bool = False) -> list[dict]:
    del session  # kept for signature symmetry with other services
    cards = [
        _rdkit_card(),
        _vina_card(settings, probe=probe),
        _property_predictor_card(),
        _llm_card(settings, probe=probe),
        *_planned_cards(),
    ]
    return [card.as_dict() for card in cards]


def get_model(session: Session, settings: Settings, adapter_id: str, *, probe: bool = False) -> dict:
    for card in list_models(session, settings, probe=probe):
        if card["id"] == adapter_id:
            return card
    raise NotFoundError(f"Adapter '{adapter_id}' is not registered.")
