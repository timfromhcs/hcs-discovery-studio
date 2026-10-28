"""Integration tests for DAG branching, fan-out, fan-in table joining, and cycle validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from hcs_discovery.core.config import Settings
from hcs_discovery.core.errors import ValidationError
from hcs_discovery.database.base import get_session_factory
from hcs_discovery.database.models import Run
from hcs_discovery.jobs.worker import Worker
from hcs_discovery.services import create_project, create_run, import_dataset, results_page
from hcs_discovery.workflow.schema import (
    EdgeSpec,
    NodeSpec,
    WorkflowSpec,
    validate_workflow,
)
from hcs_discovery.workflow.table import IDENTITY_COLUMNS


def test_validate_branching_and_join_workflow() -> None:
    # DAG with fan-out from desc into filt and prop, then fan-in into join
    spec = WorkflowSpec(
        name="Branching and Joining Test",
        nodes=[
            NodeSpec(id="desc", type="chem.descriptors", config={"descriptors": ["mw", "logp"]}),
            NodeSpec(id="filt", type="filter.rules", config={"rules": [{"column": "mw", "op": "le", "value": 500}]}),
            NodeSpec(id="prop", type="predict.property", config={"model_id": "esol_solubility"}),
            NodeSpec(id="join", type="table.join", config={"key_column": "id"}),
            NodeSpec(id="sum", type="report.summary", config={}),
        ],
        edges=[
            EdgeSpec(source="desc", target="filt"),
            EdgeSpec(source="desc", target="prop"),
            EdgeSpec(source="filt", target="join"),
            EdgeSpec(source="prop", target="join"),
            EdgeSpec(source="join", target="sum"),
        ],
    )

    validated = validate_workflow(spec, input_columns=list(IDENTITY_COLUMNS))
    order_ids = [n.id for n in validated.order]
    assert order_ids[0] == "desc"
    assert order_ids.index("join") > order_ids.index("filt")
    assert order_ids.index("join") > order_ids.index("prop")
    assert order_ids[-1] == "sum"

    # Columns at join node include columns from both branches
    join_cols = {c.name for c in validated.columns_at["join"]}
    assert "filter_pass" in join_cols
    assert "esol_solubility_pred" in join_cols


def test_cycle_detection_in_workflow() -> None:
    spec = WorkflowSpec(
        name="Cyclic Workflow",
        nodes=[
            NodeSpec(id="a", type="chem.descriptors", config={"descriptors": ["mw"]}),
            NodeSpec(id="b", type="filter.rules", config={"rules": [{"column": "mw", "op": "le", "value": 500}]}),
            NodeSpec(id="c", type="report.summary", config={}),
        ],
        edges=[
            EdgeSpec(source="a", target="b"),
            EdgeSpec(source="b", target="c"),
            EdgeSpec(source="c", target="a"),  # cycle!
        ],
    )

    with pytest.raises(ValidationError, match="Workflow validation failed"):
        validate_workflow(spec, input_columns=list(IDENTITY_COLUMNS))


def test_multiple_inputs_on_non_join_rejected() -> None:
    spec = WorkflowSpec(
        name="Invalid Multi Input",
        nodes=[
            NodeSpec(id="desc1", type="chem.descriptors", config={"descriptors": ["mw"]}),
            NodeSpec(id="desc2", type="chem.descriptors", config={"descriptors": ["logp"]}),
            NodeSpec(id="filt", type="filter.rules", config={"rules": [{"column": "mw", "op": "le", "value": 500}]}),
        ],
        edges=[
            EdgeSpec(source="desc1", target="filt"),
            EdgeSpec(source="desc2", target="filt"),
        ],
    )

    with pytest.raises(ValidationError) as exc_info:
        validate_workflow(spec, input_columns=list(IDENTITY_COLUMNS))

    issues = exc_info.value.details.get("issues", [])
    assert any("only accepts one input" in str(i.get("message", "")) for i in issues)


def test_execute_branching_dag_run(
    session: Session,
    settings: Settings,
    tmp_path: Path,
) -> None:
    factory = get_session_factory(settings)

    # 1. Create project and import small dataset
    project = create_project(session, name="DAG Test Project")
    csv_bytes = b"smiles,name\nCCO,ethanol\nCC(=O)Oc1ccccc1C(=O)O,aspirin\nc1ccccc1,benzene\n"
    dataset = import_dataset(
        session=session,
        settings=settings,
        project_id=project.id,
        filename="dag_mols.csv",
        data=csv_bytes,
    )

    # 2. Define branching workflow:
    # root: desc
    # branch 1: filt
    # branch 2: prop
    # merge: join
    # leaf: sum
    wfl_def = {
        "name": "Branch and Join Run",
        "nodes": [
            {"id": "desc", "type": "chem.descriptors", "config": {"descriptors": ["mw", "logp"]}},
            {"id": "filt", "type": "filter.rules", "config": {"rules": [{"column": "mw", "op": "le", "value": 150}]}},
            {"id": "prop", "type": "predict.property", "config": {"model_id": "esol_solubility"}},
            {"id": "join", "type": "table.join", "config": {"key_column": "id"}},
            {"id": "sum", "type": "report.summary", "config": {}},
        ],
        "edges": [
            {"source": "desc", "target": "filt"},
            {"source": "desc", "target": "prop"},
            {"source": "filt", "target": "join"},
            {"source": "prop", "target": "join"},
            {"source": "join", "target": "sum"},
        ],
    }

    run = create_run(session, project_id=project.id, dataset_id=dataset.id, workflow=wfl_def)
    run_id = run.id

    # 3. Execute via Worker
    worker = Worker(settings=settings, factory=factory)
    executed = worker.run_once()
    assert executed is not None

    # 4. Verify run status and results
    with factory() as check_session:
        completed_run = check_session.get(Run, run_id)
        assert completed_run is not None
        assert completed_run.status == "succeeded"

        # Check results
        results = results_page(check_session, run_id=run_id)
        assert len(results["items"]) == 3

        # Check that joined table rows contain columns from both branches
        row0 = results["items"][0]
        assert row0["rejected"] is False
        assert "esol_solubility_pred" in row0["metrics"]
        assert "mw" in row0["metrics"]
        assert "logp" in row0["metrics"]
