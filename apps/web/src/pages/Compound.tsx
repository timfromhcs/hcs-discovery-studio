import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useCompound } from "../api/queries";
import { Icon } from "../components/Icon";
import {
  Badge,
  Card,
  CardHeader,
  CopyButton,
  EmptyState,
  ErrorState,
  InlineNotice,
  LinkButton,
  PageHeader,
  RunStatusBadge,
  Skeleton,
} from "../components/ui";
import { formatDate, formatMetric, formatNumber } from "../lib/format";
import { useTheme } from "../lib/theme";

export function CompoundPage() {
  const { compoundId = "" } = useParams();
  const compound = useCompound(compoundId);
  const { theme } = useTheme();
  const [imageFailed, setImageFailed] = useState(false);

  if (compound.isLoading) {
    return (
      <div className="page">
        <Skeleton className="skeleton-hero" />
        <div className="detail-grid">
          <Skeleton className="skeleton-card tall-skeleton" />
          <Skeleton className="skeleton-block" />
        </div>
      </div>
    );
  }

  if (compound.error || !compound.data) {
    return (
      <div className="page">
        <ErrorState error={compound.error ?? new Error("Compound not found.")} onRetry={() => void compound.refetch()} />
        <LinkButton to="/" icon="arrowLeft">
          Back to workspace
        </LinkButton>
      </div>
    );
  }

  const data = compound.data;
  const descriptors = Object.entries(data.descriptors);
  const imageUrl = api.compounds.depictionUrl(data.id, theme);

  return (
    <div className="page">
      <PageHeader
        eyebrow={
          <>
            <Link to={`/projects/${data.project_id}`}>Project</Link>
            <Icon name="chevronRight" size={12} />
            <Link to={`/projects/${data.project_id}/library`}>Library</Link>
            <Icon name="chevronRight" size={12} />
            <span className="mono">{data.id}</span>
          </>
        }
        title={data.name || "Unnamed compound"}
        description={data.source.dataset_name ? `Imported from ${data.source.dataset_name}` : "Imported structure"}
        actions={
          <>
            <LinkButton to={`/projects/${data.project_id}/library`} variant="secondary" icon="arrowLeft">
              Library
            </LinkButton>
            {data.runs[0] ? (
              <LinkButton to={`/runs/${data.runs[0].run_id}/results`} variant="secondary" icon="results">
                Latest results
              </LinkButton>
            ) : null}
          </>
        }
        meta={
          <>
            <span className="mono small">{data.canonical_smiles}</span>
            {data.formula ? <Badge tone="neutral">{data.formula}</Badge> : null}
            {data.formal_charge !== 0 ? <Badge tone="warn">charge {data.formal_charge}</Badge> : null}
          </>
        }
      />

      {data.warnings.length ? (
        <InlineNotice tone="warn" title={`${data.warnings.length} structure warning${data.warnings.length === 1 ? "" : "s"}`}>
          <ul className="plain-list">
            {data.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </InlineNotice>
      ) : null}

      <div className="detail-grid">
        <Card className="depiction-card">
          <CardHeader title="2D structure" subtitle="Rendered locally by RDKit from the canonical isomeric SMILES." icon="molecule" />
          <div className={`depiction-frame theme-${theme}`}>
            {imageFailed ? (
              <EmptyState
                compact
                icon="alert"
                title="Depiction unavailable"
                description="The parser could not render this structure. Identifiers and source values are still shown."
              />
            ) : (
              <img
                src={imageUrl}
                alt={`2D chemical structure of ${data.name ?? data.id}`}
                onError={() => setImageFailed(true)}
              />
            )}
          </div>
          <div className="depiction-caption">
            <span className="muted small">RDKit depiction · {theme} theme</span>
            <a className="text-link small" href={imageUrl} target="_blank" rel="noreferrer">
              Open SVG <Icon name="external" size={12} />
            </a>
          </div>
        </Card>

        <Card>
          <CardHeader title="Identifiers" subtitle="Original input is preserved next to the normalised structure." icon="target" />
          <div className="identifier-list">
            <Identifier label="Input SMILES" value={data.input_smiles} />
            <Identifier label="Canonical isomeric SMILES" value={data.isomeric_smiles} />
            <Identifier label="Canonical SMILES" value={data.canonical_smiles} />
            <Identifier label="InChI" value={data.inchi} />
            <Identifier label="InChIKey" value={data.inchikey} />
            <Identifier label="Molecular formula" value={data.formula} />
            <Identifier label="Formal charge" value={String(data.formal_charge)} />
            <Identifier label="Compound ID" value={data.id} />
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader
          title="Descriptors"
          subtitle="Computed on request with the pinned RDKit version recorded by the application. Units and method travel with each value."
          icon="flask"
          actions={
            <button
              className="text-link small"
              onClick={() => {
                const rows = [["descriptor", "label", "value", "unit", "direction", "method"]];
                for (const [key, detail] of descriptors) {
                  rows.push([key, detail.label, String(detail.value ?? ""), detail.unit ?? "", detail.direction ?? "", detail.method]);
                }
                const text = rows.map((row) => row.map((cell) => `"${cell.replaceAll('"', '""')}"`).join(",")).join("\n");
                const blob = new Blob([text], { type: "text/csv" });
                const url = URL.createObjectURL(blob);
                const anchor = document.createElement("a");
                anchor.href = url;
                anchor.download = `${data.id}-descriptors.csv`;
                anchor.click();
                URL.revokeObjectURL(url);
              }}
            >
              Export descriptors
            </button>
          }
        />
        <div className="table-wrap">
          <table className="data-table descriptor-table">
            <thead>
              <tr>
                <th>Descriptor</th>
                <th className="num">Value</th>
                <th>Unit</th>
                <th>Direction</th>
                <th>Method</th>
                <th>Interpretation</th>
              </tr>
            </thead>
            <tbody>
              {descriptors.map(([key, detail]) => (
                <tr key={key}>
                  <td>
                    <strong>{detail.label}</strong>
                    <div className="tiny muted mono">{key}</div>
                  </td>
                  <td className="num tabular value-cell">{formatNumber(detail.value)}</td>
                  <td className="small">{detail.unit || "—"}</td>
                  <td className="small">
                    {detail.direction ? (
                      <span className={`direction direction-${detail.direction}`}>{detail.direction}</span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="mono tiny">{detail.method}</td>
                  <td className="small muted">{detail.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="table-note">
          Descriptors are deterministic property calculations. They are not a prediction of activity, safety or
          developability.
        </p>
      </Card>

      <div className="detail-grid">
        <Card>
          <CardHeader title="Source & provenance" icon="shield" />
          <dl className="key-value">
            <div>
              <dt>Dataset</dt>
              <dd>
                {data.source.dataset_id ? (
                  <span>{data.source.dataset_name}</span>
                ) : (
                  "Imported without a dataset"
                )}
              </dd>
            </div>
            <div>
              <dt>Source format</dt>
              <dd>{data.source.source_format ?? "—"}</dd>
            </div>
            <div>
              <dt>Source row</dt>
              <dd className="mono">{data.source.source_row_index ?? "—"}</dd>
            </div>
            <div>
              <dt>Source ID</dt>
              <dd className="mono">{data.source.source_id ?? "—"}</dd>
            </div>
            <div>
              <dt>License</dt>
              <dd>{data.source.license}</dd>
            </div>
            <div>
              <dt>Source URL</dt>
              <dd className="mono break-all">{data.source.source_url ?? "—"}</dd>
            </div>
            <div>
              <dt>Dataset SHA-256</dt>
              <dd className="mono tiny break-all">{data.source.dataset_sha256 ?? "—"}</dd>
            </div>
            <div>
              <dt>Imported</dt>
              <dd>{formatDate(data.created_at)}</dd>
            </div>
          </dl>
        </Card>

        <Card>
          <CardHeader title="Run appearances" subtitle="How this compound fared in persisted runs." icon="run" />
          {data.runs.length ? (
            <div className="table-wrap">
              <table className="data-table compact-table">
                <thead>
                  <tr>
                    <th>Run</th>
                    <th className="num">Rank</th>
                    <th className="num">Score</th>
                    <th>Status</th>
                    <th>Reasons</th>
                  </tr>
                </thead>
                <tbody>
                  {data.runs.map((appearance) => (
                    <tr key={appearance.run_id}>
                      <td>
                        <Link to={`/runs/${appearance.run_id}`}>{appearance.workflow_name}</Link>
                        <div className="tiny muted mono">{appearance.run_id}</div>
                      </td>
                      <td className="num tabular">{appearance.rank ?? "—"}</td>
                      <td className="num tabular">{formatMetric(appearance.composite_score)}</td>
                      <td>
                        <RunStatusBadge status={appearance.status} />
                      </td>
                      <td className="small">
                        {appearance.rejected ? (
                          <span className="error-text">Filtered: {appearance.reasons.join("; ") || "no reason recorded"}</span>
                        ) : (
                          <span className="success-text">Passed filters</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              compact
              icon="run"
              title="No run results yet"
              description="Run a workflow on a dataset containing this compound to record ranking and filter outcomes."
            />
          )}
        </Card>
      </div>

      <InlineNotice tone="info" title="No 3D conformer or experimental measurements">
        This version stores 2D identifiers and computed descriptors only. It does not generate 3D poses, dock
        structures or attach assay measurements. A structure viewer is not shown because no valid 3D structure is
        available for this record.
      </InlineNotice>
    </div>
  );
}

function Identifier({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="identifier">
      <span className="identifier-label">{label}</span>
      <div className="identifier-row">
        <code className="identifier-value break-all">{value || "—"}</code>
        {value ? <CopyButton value={value} label={`Copy ${label}`} compact /> : null}
      </div>
    </div>
  );
}
