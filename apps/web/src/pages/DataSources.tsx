import { Link } from "react-router-dom";
import { useProjects, useStats } from "../api/queries";
import { Icon } from "../components/Icon";
import {
  Badge,
  Card,
  CardHeader,
  CopyButton,
  InlineNotice,
  KeyValue,
  LinkButton,
  PageHeader,
  Stat,
} from "../components/ui";

interface SourceEntry {
  name: string;
  access: string;
  status: "available" | "planned";
  description: string;
  license: string;
  detail: string;
}

const SOURCES: SourceEntry[] = [
  {
    name: "Local structure files",
    access: "File upload / filesystem",
    status: "available",
    description: "CSV, TSV, SDF and SMILES files are parsed locally, standardised and stored with a SHA-256 checksum.",
    license: "Declared per import",
    detail: "Supported formats: CSV, TSV, SDF, SMI/SMILES. Invalid rows are retained in the dataset journal with an error.",
  },
  {
    name: "Project run artifacts",
    access: "Local data directory",
    status: "available",
    description: "Every completed run writes results.json, results.csv, a Markdown/HTML report and a provenance manifest.",
    license: "Inherited from the dataset",
    detail: "Artifacts are addressed by run id and SHA-256; they are never overwritten by later runs.",
  },
  {
    name: "ChEMBL",
    access: "Remote REST API",
    status: "planned",
    description: "A bioactivity connector would fetch compounds and assay endpoints with a documented release, not a moving target.",
    license: "CC BY-SA 4.0 (data)",
    detail: "Not implemented. No network request is made by this build. Do not assume ChEMBL data is present.",
  },
  {
    name: "PubChem",
    access: "Remote REST API",
    status: "planned",
    description: "A compound lookup connector for names, identifiers and computed properties.",
    license: "Public domain (US government work)",
    detail: "Not implemented. Record identifiers must be imported from a local file in this release.",
  },
  {
    name: "ZINC",
    access: "Bulk download",
    status: "planned",
    description: "A purchasable-compound library importer with explicit snapshot dates and tranche metadata.",
    license: "Per ZINC terms; verify before redistribution",
    detail: "Not implemented. There is no scheduler, downloader or remote catalogue browser.",
  },
];

export function DataSourcesPage() {
  const stats = useStats();
  const projects = useProjects();
  const firstProject = projects.data?.items[0];

  return (
    <div className="page">
      <PageHeader
        eyebrow="Data sources"
        title="Where structures come from"
        description="This release is deliberately local-first. You bring a structure file; the studio records its checksum, license and every transformation. Remote catalogue connectors are listed below as planned, not enabled."
        actions={
          firstProject ? (
            <LinkButton to={`/projects/${firstProject.id}`} variant="primary" icon="upload">
              Import into {firstProject.name}
            </LinkButton>
          ) : (
            <LinkButton to="/" variant="primary" icon="plus">
              Create a project first
            </LinkButton>
          )
        }
        meta={
          <>
            <Badge tone="accent">
              <Icon name="shield" size={13} /> Local-only by default
            </Badge>
            <span className="muted small">{stats.data?.compounds.toLocaleString() ?? "—"} compounds stored</span>
          </>
        }
      />

      <InlineNotice tone="warn" title="No remote connectors are enabled in this build">
        <p>
          The only ingestion path is a local file upload through the UI or <span className="mono">hcs-discovery dataset import</span>.
          Network egress is blocked by the default network policy; the planned cards below do not call any service. See{" "}
          <Link to="/settings">settings</Link> for the active policy.
        </p>
      </InlineNotice>

      <section className="stats-grid" aria-label="Data source totals">
        <Stat label="Compounds" value={stats.data?.compounds.toLocaleString() ?? "—"} icon="molecule" hint="Standardised structures" />
        <Stat label="Projects" value={stats.data?.projects ?? "—"} icon="folder" hint="Each with its own provenance" />
        <Stat label="Runs" value={stats.data?.runs ?? "—"} icon="run" hint="Results kept as artifacts" />
        <Stat label="Remote connectors" value="0" icon="external" hint="Zero enabled by design" />
      </section>

      <Card>
        <CardHeader
          title="Source catalogue"
          subtitle="Availability describes this build, not an aspiration."
          icon="database"
        />
        <div className="catalog-grid">
          {SOURCES.map((source) => (
            <article key={source.name} className="catalog-card source-card">
              <div className="row-between">
                <span className="model-icon">
                  <Icon name={source.status === "available" ? "database" : "external"} size={18} />
                </span>
                <Badge tone={source.status === "available" ? "ok" : "muted"} dot>
                  {source.status}
                </Badge>
              </div>
              <strong>{source.name}</strong>
              <span className="mono tiny muted">{source.access}</span>
              <p className="small muted">{source.description}</p>
              <p className="tiny muted">{source.detail}</p>
              <div className="chip-row">
                <span className="chip">{source.license}</span>
              </div>
            </article>
          ))}
        </div>
      </Card>

      <div className="grid-2">
        <Card>
          <CardHeader title="What an import records" subtitle="Provenance is a first-class column, not a footnote." icon="shield" />
          <ul className="plain-list small">
            <li>Original filename, byte size and SHA-256 of the uploaded file.</li>
            <li>Declared license and optional source URL supplied by you.</li>
            <li>Format, column mapping, standardisation options and a row-level journal.</li>
            <li>Every accepted, duplicate and rejected row, with the parser error when one exists.</li>
            <li>The canonical SMILES used as the compound identity, plus isomeric SMILES and InChIKey.</li>
          </ul>
          <p className="tiny muted">
            Re-uploading the same checksum is detected; existing structures are not silently overwritten.
          </p>
        </Card>

        <Card>
          <CardHeader title="Command-line parity" subtitle="The same import is available without the UI." icon="models" />
          <KeyValue
            items={[
              {
                label: "Import",
                value: <span className="mono small">hcs-discovery dataset import --project prj_… --file library.sdf --license "CC BY 4.0"</span>,
                mono: false,
              },
              { label: "List", value: <span className="mono small">hcs-discovery dataset list --project prj_… --json</span>, mono: false },
              { label: "Errors", value: <span className="mono small">hcs-discovery dataset errors dts_… --json</span>, mono: false },
              { label: "API", value: <span className="mono small">POST /api/v1/projects/{"{id}"}/datasets</span>, mono: false },
            ]}
          />
          <div className="row-actions">
            <CopyButton
              value={'hcs-discovery dataset import --project prj_… --file library.sdf --license "CC BY 4.0"'}
              label="Copy import command"
            />
          </div>
          <InlineNotice tone="info" title="License hygiene">
            Record the license you actually have. The studio stores your declaration and displays it with the compound;
            it cannot verify redistribution rights for you.
          </InlineNotice>
        </Card>
      </div>
    </div>
  );
}
