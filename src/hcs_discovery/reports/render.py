"""Report generation from persisted run data (Markdown, HTML, JSON, CSV)."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import PRODUCT_NAME, __version__
from ..core.config import Settings
from ..core.errors import NotFoundError
from ..core.paths import safe_join
from ..core.timeutil import iso
from ..database.models import Artifact, Compound, Project, Run, RunNode, RunResult

CAVEAT = (
    "Computational scores and descriptors are prioritisation signals, not measurements. "
    "They do not prove binding, safety, efficacy or clinical utility, and require experimental validation."
)


def load_report_data(session: Session, run_id: str) -> dict[str, Any]:
    run = session.get(Run, run_id)
    if run is None:
        raise NotFoundError(f"Run '{run_id}' does not exist.")
    project = session.get(Project, run.project_id)
    nodes = session.execute(select(RunNode).where(RunNode.run_id == run.id).order_by(RunNode.id)).scalars().all()
    artifacts = session.execute(select(Artifact).where(Artifact.run_id == run.id).order_by(Artifact.id)).scalars().all()
    results = session.execute(
        select(RunResult, Compound)
        .join(Compound, Compound.id == RunResult.compound_id, isouter=True)
        .where(RunResult.run_id == run.id)
        .order_by(RunResult.rank.is_(None), RunResult.rank, RunResult.id)
    ).all()

    metric_names: list[str] = []
    for result, _compound in results:
        for key in result.metrics:
            if key not in metric_names:
                metric_names.append(key)

    rows = [
        {
            "rank": result.rank,
            "compound_id": result.compound_id,
            "name": compound.name if compound else None,
            "smiles": compound.isomeric_smiles if compound else None,
            "composite_score": result.composite_score,
            "pareto_front": result.pareto_front,
            "rejected": result.rejected,
            "reasons": result.reasons,
            "metrics": result.metrics,
        }
        for result, compound in results
    ]

    return {
        "product": {"name": PRODUCT_NAME, "version": __version__},
        "run": {
            "id": run.id,
            "status": run.status,
            "workflow_name": run.workflow_name,
            "workflow_hash": run.workflow_hash,
            "created_at": iso(run.created_at),
            "started_at": iso(run.started_at),
            "finished_at": iso(run.finished_at),
            "seed": run.seed,
            "error": run.error,
        },
        "project": {"id": project.id, "name": project.name} if project else None,
        "nodes": [
            {
                "node_id": node.node_id,
                "type": node.node_type,
                "status": node.status,
                "cached": node.cached,
                "cache_key": node.cache_key,
                "duration_ms": node.summary.get("duration_ms") if node.summary else None,
            }
            for node in nodes
        ],
        "artifacts": [
            {
                "rel_path": artifact.rel_path,
                "media_type": artifact.media_type,
                "size_bytes": artifact.size_bytes,
                "sha256": artifact.sha256,
            }
            for artifact in artifacts
        ],
        "manifest": run.manifest,
        "columns": run.manifest.get("columns", []) if isinstance(run.manifest, dict) else [],
        "results": rows,
        "metric_names": metric_names,
        "caveat": CAVEAT,
    }


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4g}"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def render_markdown(data: dict[str, Any]) -> str:
    run = data["run"]
    project = data["project"] or {"name": "unknown"}
    lines = [
        f"# {run['workflow_name']} - run report",
        "",
        f"**Product:** {data['product']['name']} {data['product']['version']}  ",
        f"**Project:** {project['name']}  ",
        f"**Run:** `{run['id']}` ({run['status']})  ",
        f"**Started:** {run['started_at']}  **Finished:** {run['finished_at']}  ",
        f"**Workflow hash:** `{run['workflow_hash'][:16]}`",
        "",
        "## Pipeline",
        "",
        "| Node | Type | Status | Cached | Duration (ms) |",
        "|---|---|---|---|---|",
    ]
    for node in data["nodes"]:
        lines.append(
            f"| {node['node_id']} | {node['type']} | {node['status']} | "
            f"{'yes' if node['cached'] else 'no'} | {_fmt(node['duration_ms'])} |"
        )

    total_results = len(data["results"])
    lines.extend(
        [
            "",
            "## Results",
            "",
            f"{total_results} record(s). Rejected rows are retained with reasons.",
            "",
        ]
    )
    if total_results > 200:
        lines.extend(
            [
                f"> **Table Truncation Notice:** Displaying first 200 of {total_results} records "
                "for document rendering performance. Complete data is preserved in CSV, JSON and artifact exports.",
                "",
            ]
        )
    header = [
        "Rank",
        "Name",
        "SMILES",
        "Score",
        "Pareto",
        "Rejected",
        "Reasons",
        *data["metric_names"],
    ]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")
    for row in data["results"][:200]:
        cells = [
            _fmt(row["rank"]),
            _fmt(row["name"]),
            _fmt(row["smiles"]),
            _fmt(row["composite_score"]),
            _fmt(row["pareto_front"]),
            _fmt(row["rejected"]),
            _fmt("; ".join(row["reasons"])),
            *[_fmt(row["metrics"].get(name)) for name in data["metric_names"]],
        ]
        lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |")

    manifest = data.get("manifest") or {}
    lines.extend(["", "## Provenance", ""])
    if manifest:
        lines.extend(
            [
                f"- Inputs hash: `{manifest.get('inputs_hash')}`",
                f"- Dataset: `{(manifest.get('dataset') or {}).get('id')}` "
                f"(sha256 `{(manifest.get('dataset') or {}).get('sha256')}`)",
                f"- Environment: {manifest.get('environment', {})}",
                f"- Hardware: {manifest.get('hardware', {})}",
            ]
        )
    lines.extend(
        [
            "",
            "### Artifacts",
            "",
            "| Path | Media type | Bytes | SHA-256 |",
            "|---|---|---|---|",
            *[
                f"| {artifact['rel_path']} | {artifact['media_type']} | {artifact['size_bytes']} "
                f"| {artifact['sha256'][:16]}... |"
                for artifact in data["artifacts"]
            ],
            "",
            "## Limitations",
            "",
            *[f"- {item}" for item in manifest.get("limitations", [])],
            "",
            f"> {data['caveat']}",
            "",
            "*Made with love by hcsmedia. Report generated from run artifacts; values are reproducible "
            "within the recorded software versions.*",
            "",
        ]
    )
    return "\n".join(lines)


def render_html(data: dict[str, Any]) -> str:
    run = data["run"]
    project = data["project"] or {"name": "unknown"}
    manifest = data.get("manifest") or {}
    status_class = {"succeeded": "ok", "failed": "bad", "cancelled": "warn"}.get(run["status"], "warn")

    def esc(value: Any) -> str:
        return html.escape(_fmt(value))

    def pill(status: str) -> str:
        return {"succeeded": "ok", "failed": "bad", "cancelled": "warn"}.get(status, "warn")

    node_rows = "".join(
        "<tr>"
        f"<td>{esc(node['node_id'])}</td><td>{esc(node['type'])}</td>"
        f"<td><span class='pill {pill(node['status'])}'>"
        f"{esc(node['status'])}</span></td>"
        f"<td>{'yes' if node['cached'] else 'no'}</td><td>{esc(node['duration_ms'])}</td>"
        "</tr>"
        for node in data["nodes"]
    )
    header_cells = "".join(
        f"<th>{esc(label)}</th>"
        for label in [
            "Rank",
            "Name",
            "SMILES",
            "Score",
            "Pareto",
            "Rejected",
            "Reasons",
            *data["metric_names"],
        ]
    )
    total_html_results = len(data["results"])
    truncation_html = ""
    if total_html_results > 500:
        truncation_html = (
            "<div class='caveat' style='margin-bottom:12px; border-left-color:var(--accent-2); "
            "background:#0c1522; color:#c0d4f5;'>"
            f"<strong>Table Truncation Notice:</strong> Displaying first 500 of {total_html_results} "
            "records for browser performance. Complete results are preserved in CSV, JSON and artifact exports.</div>"
        )
    result_rows = []
    for row in data["results"][:500]:
        cells = [
            esc(row["rank"]),
            esc(row["name"]),
            esc(row["smiles"]),
            esc(row["composite_score"]),
            esc(row["pareto_front"]),
            esc(row["rejected"]),
            esc("; ".join(row["reasons"])),
            *[esc(row["metrics"].get(name)) for name in data["metric_names"]],
        ]
        result_rows.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
    artifact_rows = "".join(
        f"<tr><td><code>{esc(a['rel_path'])}</code></td><td>{esc(a['media_type'])}</td>"
        f"<td>{esc(a['size_bytes'])}</td><td><code>{esc(a['sha256'][:24])}…</code></td></tr>"
        for a in data["artifacts"]
    )
    limitations = "".join(f"<li>{esc(item)}</li>" for item in manifest.get("limitations", []))

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(run["workflow_name"])} — {esc(data["product"]["name"])} report</title>
<style>
  :root {{ color-scheme: dark; --bg:#080b10; --surface:#111823; --line:#1f2b3a; --text:#e8eef7;
          --muted:#93a4ba; --accent:#5ee0c0; --accent-2:#7aa2ff; --bad:#ff8a8a; --warn:#ffcc7a; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text);
          font:15px/1.55 ui-sans-serif,system-ui,"Segoe UI",sans-serif; }}
  .page {{ max-width:1100px; margin:0 auto; padding:48px 28px 80px; }}
  header {{ display:flex; gap:24px; align-items:flex-start; justify-content:space-between;
            border-bottom:1px solid var(--line); padding-bottom:24px; margin-bottom:32px; }}
  .brand {{ display:flex; align-items:center; gap:12px; font-weight:650; letter-spacing:.02em; }}
  .mark {{ width:34px; height:34px; }}
  h1 {{ font-size:clamp(22px,3vw,32px); margin:6px 0 4px; letter-spacing:-.02em; }}
  .sub {{ color:var(--muted); font-size:13px; }}
  h2 {{ font-size:14px; text-transform:uppercase; letter-spacing:.12em; color:var(--accent-2);
        margin:36px 0 12px; }}
  table {{ width:100%; border-collapse:collapse; font-size:12.5px; background:var(--surface);
           border:1px solid var(--line); border-radius:10px; overflow:hidden; }}
  th {{ text-align:left; font-weight:600; color:var(--muted); background:#0e1520; padding:9px 10px;
        border-bottom:1px solid var(--line); white-space:nowrap; }}
  td {{ padding:8px 10px; border-bottom:1px solid #172231; vertical-align:top;
        font-variant-numeric:tabular-nums; }}
  tr:last-child td {{ border-bottom:none; }}
  code, .mono {{ font-family:ui-monospace,"Cascadia Code",Consolas,monospace; font-size:12px; }}
  .pill {{ display:inline-block; padding:1px 8px; border-radius:999px; font-size:11px;
           border:1px solid currentColor; }}
  .pill.ok {{ color:var(--accent); }} .pill.bad {{ color:var(--bad); }} .pill.warn {{ color:var(--warn); }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px; }}
  .card {{ background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:14px 16px; }}
  .card dt {{ color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.08em; }}
  .card dd {{ margin:4px 0 0; font-size:13px; overflow-wrap:anywhere; }}
  .caveat {{ border-left:3px solid var(--warn); background:#171207; color:#f0dcb6;
             padding:12px 16px; border-radius:0 8px 8px 0; font-size:13px; }}
  footer {{ margin-top:48px; border-top:1px solid var(--line); padding-top:18px; color:var(--muted);
            font-size:12px; display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; }}
</style>
</head>
<body>
<div class="page">
  <header>
    <div>
      <div class="brand">
        <svg class="mark" viewBox="0 0 48 48" fill="none" aria-hidden="true">
          <circle cx="10" cy="12" r="5" stroke="#5ee0c0" stroke-width="2.2"/>
          <circle cx="38" cy="14" r="5" stroke="#7aa2ff" stroke-width="2.2"/>
          <circle cx="24" cy="37" r="5" stroke="#5ee0c0" stroke-width="2.2"/>
          <path d="M15 13.5 33 15M13 16.5 21.5 32.5M35.5 18 26 33" stroke="#93a4ba" stroke-width="1.6"/>
        </svg>
        <span>HCS Discovery Studio</span>
      </div>
      <h1>{esc(run["workflow_name"])}</h1>
      <div class="sub">Run report · project {esc(project["name"])} · {esc(run["status"])}</div>
    </div>
    <div class="sub mono">v{esc(data["product"]["version"])}</div>
  </header>

  <dl class="grid">
    <div class="card"><dt>Run</dt><dd class="mono">{esc(run["id"])}</dd></div>
    <div class="card"><dt>Status</dt><dd><span class="pill {status_class}">{esc(run["status"])}</span></dd></div>
    <div class="card"><dt>Records</dt><dd>{len(data["results"])}</dd></div>
    <div class="card"><dt>Workflow hash</dt><dd class="mono">{esc(run["workflow_hash"][:16])}…</dd></div>
    <div class="card"><dt>Started</dt><dd>{esc(run["started_at"])}</dd></div>
    <div class="card"><dt>Finished</dt><dd>{esc(run["finished_at"])}</dd></div>
  </dl>

  <h2>Pipeline</h2>
  <table><thead><tr><th>Node</th><th>Type</th><th>Status</th><th>Cached</th><th>Duration (ms)</th></tr></thead>
  <tbody>{node_rows}</tbody></table>

  <h2>Results</h2>
  {truncation_html}<table><thead><tr>{header_cells}</tr></thead><tbody>{"".join(result_rows)}</tbody></table>

  <h2>Artifacts</h2>
  <table><thead><tr><th>Path</th><th>Media type</th><th>Bytes</th><th>SHA-256</th></tr></thead>
  <tbody>{artifact_rows}</tbody></table>

  <h2>Limitations</h2>
  <ul>{limitations}</ul>
  <p class="caveat">{esc(data["caveat"])}</p>

  <footer>
    <span>Made with ❤ by hcsmedia</span>
    <span class="mono">manifest {esc((data["manifest"] or {}).get("inputs_hash", "")[:24])}</span>
  </footer>
</div>
</body>
</html>
"""


def render_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def results_csv_path(settings: Settings, run_id: str) -> Path:
    return safe_join(settings.runs_dir, run_id, "results.csv")


def export_report(
    session: Session,
    settings: Settings,
    run_id: str,
    fmt: str,
    output: Path,
) -> Path:
    fmt = fmt.lower()
    data = load_report_data(session, run_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "markdown" or fmt == "md":
        output.write_text(render_markdown(data), encoding="utf-8")
    elif fmt == "html":
        output.write_text(render_html(data), encoding="utf-8")
    elif fmt == "json":
        output.write_text(render_json(data), encoding="utf-8")
    elif fmt == "csv":
        source = results_csv_path(settings, run_id)
        if not source.exists():
            raise NotFoundError("This run has no results.csv artifact.")
        output.write_bytes(source.read_bytes())
    elif fmt == "sdf":
        source = safe_join(settings.runs_dir, run_id, "results.sdf")
        if source.exists():
            output.write_bytes(source.read_bytes())
        else:
            from rdkit import Chem

            writer = Chem.SDWriter(str(output))
            try:
                for row in data["results"]:
                    smiles = row.get("smiles")
                    mol = Chem.MolFromSmiles(smiles) if smiles else None
                    if mol is None:
                        mol = Chem.MolFromSmiles("")
                    if mol is not None:
                        mol.SetProp("_Name", str(row.get("compound_id") or row.get("name") or ""))
                        if row.get("rank") is not None:
                            mol.SetProp("RANK", str(row["rank"]))
                        if row.get("composite_score") is not None:
                            mol.SetProp("COMPOSITE_SCORE", str(row["composite_score"]))
                        if row.get("pareto_front") is not None:
                            mol.SetProp("PARETO_FRONT", str(row["pareto_front"]))
                        for k, v in row.get("metrics", {}).items():
                            if v is not None:
                                mol.SetProp(str(k).upper(), str(v))
                        writer.write(mol)
            finally:
                writer.close()
    else:
        raise ValueError(f"Unsupported report format '{fmt}'")
    return output
