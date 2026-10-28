import { Link } from "react-router-dom";
import { useAbout, useDiagnostics, useModels, useWorkflowCatalog } from "../api/queries";
import { Logo } from "../components/Icon";
import {
  Badge,
  Card,
  CardHeader,
  CopyButton,
  ErrorState,
  InlineNotice,
  KeyValue,
  LinkButton,
  PageHeader,
  Skeleton,
  Stat,
} from "../components/ui";
import { CREDIT } from "../lib/constants";

const LIMITS: Array<{ title: string; body: string }> = [
  {
    title: "Descriptors are calculated, not measured",
    body: "Molecular weight, cLogP, TPSA, HBD/HBA, rotatable bonds, ring counts, Fsp3, QED and molar refractivity come from RDKit on a 2D graph. They are useful for triage and are not experimental observations.",
  },
  {
    title: "Rankings are prioritisation signals",
    body: "Composite scores and Pareto fronts order compounds according to the objectives and weights you chose. A high rank is not evidence of binding, selectivity, safety, efficacy, bioavailability or clinical utility.",
  },
  {
    title: "No docking, ADMET or structure prediction",
    body: "This release has no docking engine, no ADMET model, no protein structure prediction, no generative design and no 3D conformer generation. Model-registry entries for these are marked planned and cannot be queued.",
  },
  {
    title: "Rules are explicitly yours",
    body: "The rule-filter node applies the thresholds you configure and records every pass/fail reason. It does not encode Lipinski, Veber or any other rule set unless you enter those values yourself.",
  },
  {
    title: "Similarity is a fingerprint heuristic",
    body: "Morgan/Tanimoto similarity compares 2D circular fingerprints against a query you supply. It is sensitive to fingerprint radius, bit length and the chosen similarity column; it is not a scaffold-aware or 3D measure.",
  },
  {
    title: "No assay or clinical data model",
    body: "Datasets are structure-centric in this release. There is no assay import, dose-response curve fitting, ADME dataset, or clinical outcome table. Do not treat the workspace as an electronic lab notebook.",
  },
  {
    title: "Local-first, not a validated product",
    body: "The software is a research workbench. It is not medical software, not a regulatory submission package and not a substitute for expert review. Validate every pipeline against your own reference data before relying on it.",
  },
];

const CONTROLS: Array<{ title: string; body: string }> = [
  {
    title: "No silent network access",
    body: "The default network policy is local. Diagnostics probe only when requested; remote LLM access is a separate opt-in and requires the remote policy.",
  },
  {
    title: "Secrets stay in the environment",
    body: "API tokens and provider keys are read from HCS_* variables. The settings API reports only “configured” or “missing”, and logs redact known secret values.",
  },
  {
    title: "Authentication off loopback",
    body: "Binding to a non-loopback interface requires HCS_API_TOKEN; requests must present a matching bearer token. Do not expose the service to the public internet.",
  },
  {
    title: "Provenance is immutable",
    body: "Each run snapshots the workflow definition, content hash, seed, dataset checksum, engine versions and implementation hashes. Artifacts are addressed by SHA-256.",
  },
];

export function AboutPage() {
  const about = useAbout();
  const diagnostics = useDiagnostics();
  const models = useModels(false);
  const catalog = useWorkflowCatalog();
  const runnable = models.data?.items.filter((model) => model.status === "available" || model.status === "available_with_limits").length;

  const citation = `@software{hcs_discovery_studio,
  title  = {HCS Discovery Studio},
  author = {hcsmedia},
  year   = {2026},
  url    = {https://github.com/timfromhcs/hcs-discovery-studio},
  note   = {Local-first, reproducible drug-discovery research workbench}
}`;

  return (
    <div className="page">
      <PageHeader
        eyebrow="About & help"
        title="What this is, and what it is not"
        description="A local-first research workbench for structure triage. The goal is transparent, reproducible prioritisation — not a claim to discover drugs automatically."
        actions={
          <LinkButton to="/settings" variant="secondary" icon="settings">
            Diagnostics
          </LinkButton>
        }
        meta={
          about.data ? (
            <>
              <Badge tone="accent" dot>
                v{about.data.version}
              </Badge>
              <span className="muted small">{about.data.license}</span>
              <span className="muted small">{about.data.local_first ? "Local-first" : "Remote"}</span>
            </>
          ) : null
        }
      />

      <Card className="about-hero">
        <div className="about-brand">
          <Logo size={52} />
          <div>
            <h2>{about.data?.product ?? "HCS Discovery Studio"}</h2>
            <p className="muted">{about.data?.tagline ?? "Open science. Reproducible discovery."}</p>
            <p className="small muted">{about.data?.credit ?? CREDIT}</p>
          </div>
        </div>
        {about.isLoading ? (
          <Skeleton className="skeleton-row" />
        ) : about.error ? (
          <ErrorState error={about.error} onRetry={() => void about.refetch()} />
        ) : (
          <KeyValue
            items={[
              { label: "Version", value: about.data?.version ?? "—", mono: true },
              { label: "Project license", value: about.data?.license ?? "—" },
              { label: "Network policy", value: about.data?.network_policy ?? "—" },
              { label: "Python", value: diagnostics.data?.environment.python ?? "—", mono: true },
              { label: "Backend", value: diagnostics.data?.environment.backend ?? "FastAPI", mono: true },
              { label: "Platform", value: diagnostics.data?.environment.platform ?? "—" },
            ]}
          />
        )}
      </Card>

      <section className="stats-grid" aria-label="Release facts">
        <Stat label="Workflow nodes" value={catalog.data?.items.length ?? "—"} icon="workflow" hint="Generated from the live registry" />
        <Stat label="Runnable engines" value={runnable ?? "—"} icon="models" hint="Passed local runtime checks" />
        <Stat label="Remote connectors" value="0" icon="external" hint="By design in this release" />
        <Stat label="Data stays" value={about.data?.local_first === false ? "Remote" : "Local"} icon="shield" hint="SQLite, uploads and artifacts" />
      </section>

      <InlineNotice tone="danger" title="Scientific scope — read before making decisions">
        Values, flags and rankings produced here are hypotheses to test, not evidence of activity. Nothing in this
        application has been validated for a specific target, indication or regulatory use. Do not use it to make
        clinical, safety or dosing decisions.
      </InlineNotice>

      <Card>
        <CardHeader title="Limitations register" subtitle="Known boundaries of this release, stated plainly." icon="info" />
        <div className="limitations-list">
          {LIMITS.map((limit) => (
            <article key={limit.title}>
              <h3>{limit.title}</h3>
              <p className="small muted">{limit.body}</p>
            </article>
          ))}
        </div>
      </Card>

      <div className="grid-2">
        <Card>
          <CardHeader title="Reproducibility contract" subtitle="What “reproducible” means in practice." icon="refresh" />
          <ul className="plain-list small">
            <li>Workflow definitions are validated before queueing and snapshotted into the run.</li>
            <li>Node cache keys include node type, version, config, input hash, engine versions and implementation hash.</li>
            <li>Seeds are explicit; there is no hidden randomness in the shipped nodes.</li>
            <li>Every artifact is content-addressed and listed in the run manifest with its SHA-256.</li>
            <li>The results report can be exported as JSON, CSV, Markdown or HTML without the UI.</li>
          </ul>
          <div className="row-actions">
            <CopyButton value="hcs-discovery run artifacts RUN_ID --json" label="Copy artifacts command" />
            <CopyButton value="hcs-discovery report export RUN_ID --format csv --output results.csv" label="Copy export command" />
          </div>
        </Card>

        <Card>
          <CardHeader title="Security and privacy" subtitle="Defaults are conservative; verify them for your deployment." icon="shield" />
          <div className="limitations-list compact">
            {CONTROLS.map((control) => (
              <article key={control.title}>
                <h3>{control.title}</h3>
                <p className="small muted">{control.body}</p>
              </article>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid-2">
        <Card>
          <CardHeader title="Get help" subtitle="The CLI and the HTTP API expose the same operations." icon="info" />
          <KeyValue
            items={[
              { label: "API schema", value: <a className="text-link" href="/api/v1/openapi.json">/api/v1/openapi.json</a> },
              { label: "Health", value: <a className="text-link" href="/api/v1/health">/api/v1/health</a> },
              { label: "CLI", value: <span className="mono small">hcs-discovery --help</span> },
              { label: "Doctor", value: <span className="mono small">hcs-discovery doctor --check-vulkan</span> },
              { label: "Data sources", value: <Link className="text-link" to="/sources">Supported ingestion</Link> },
            ]}
          />
          <p className="tiny muted">
            When reporting a problem, include the version, platform, the failing command or request, and the run id if
            one exists. Redact tokens, keys, absolute paths and proprietary structures you cannot share.
          </p>
        </Card>

        <Card>
          <CardHeader title="Citation" subtitle="Cite the software version you actually used." icon="library" />
          <pre className="citation-block">{citation}</pre>
          <div className="row-actions">
            <CopyButton value={citation} label="Copy BibTeX" />
            <CopyButton value="hcs-discovery version" label="Copy version command" />
          </div>
          <p className="tiny muted">
            Third-party libraries, datasets and model weights keep their own licenses. Check the NOTICE file and each
            model card before redistribution.
          </p>
        </Card>
      </div>
    </div>
  );
}
