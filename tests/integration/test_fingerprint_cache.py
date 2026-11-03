"""Dataset fingerprint cache: reuse, invalidation and corruption handling."""

from __future__ import annotations

import numpy as np
from sqlalchemy import select

from hcs_discovery.database.models import Compound, DatasetFingerprints
from hcs_discovery.services import fingerprint_cache_stats, load_dataset_fingerprints
from tests.integration.test_api import _create_project, _import


def test_cache_reuses_then_rebuilds_when_the_dataset_changes(client):
    project = _create_project(client)
    dataset = _import(client, project["id"])
    factory = client.app.state.session_factory

    with factory() as session:
        first = load_dataset_fingerprints(session, dataset["id"])
        assert first.cached is False
        assert first.count == dataset["imported_count"]
        assert first.packed.shape == (dataset["imported_count"], 64)

        second = load_dataset_fingerprints(session, dataset["id"])
        assert second.cached is True
        assert np.array_equal(first.packed, second.packed)
        assert second.checksum == first.checksum
        assert fingerprint_cache_stats(session) == {"entries": 1, "compounds": dataset["imported_count"]}

        compound = session.execute(select(Compound).order_by(Compound.id)).scalars().first()
        assert compound is not None
        # Guarantee a change: the first compound may already be ethanol ("CCO").
        compound.isomeric_smiles = "C" if compound.isomeric_smiles != "C" else "CC"
        session.commit()
        third = load_dataset_fingerprints(session, dataset["id"])
        assert third.cached is False
        assert third.compounds_checksum != second.compounds_checksum


def test_corrupted_blob_is_rebuilt_instead_of_scored(client):
    project = _create_project(client)
    dataset = _import(client, project["id"])
    factory = client.app.state.session_factory

    with factory() as session:
        load_dataset_fingerprints(session, dataset["id"])
        row = session.execute(select(DatasetFingerprints)).scalar_one()
        row.packed = b"broken"
        session.commit()

        rebuilt = load_dataset_fingerprints(session, dataset["id"])
        assert rebuilt.cached is False
        assert rebuilt.count == dataset["imported_count"]
        assert rebuilt.packed.shape == (dataset["imported_count"], 64)

        again = load_dataset_fingerprints(session, dataset["id"])
        assert again.cached is True


def test_unknown_dataset_is_a_not_found(client):
    import pytest

    from hcs_discovery.core.errors import NotFoundError

    factory = client.app.state.session_factory
    with factory() as session, pytest.raises(NotFoundError):
        load_dataset_fingerprints(session, "dts_missing")
