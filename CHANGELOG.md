# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet.

## [0.1.0] - 2026-10-28

First public preview. This release is an honest vertical slice, not a complete
drug-discovery platform. See `docs/engineering/IMPLEMENTATION_STATUS.md` for the
feature-by-feature status.

### Added

- Project, dataset, compound, workflow and run domain model persisted in SQLite
  through SQLAlchemy 2, with Alembic as the schema authority.
- CSV, SDF and SMILES import with row-level outcomes, duplicate retention,
  configurable standardisation (salt stripping, neutralisation, canonical
  tautomer) and SHA-256 file checksums.
- RDKit-backed descriptor calculation, Morgan/Tanimoto similarity, explicit
  rule filters, Pareto non-dominated sorting and a transparent weighted
  composite score.
- Lease-based local job queue with restart recovery, cancellation, per-node
  timeouts, a content-addressed node cache and at-least-once execution.
- Run manifests containing workflow snapshots, dataset checksums, engine and
  Python versions, hardware description, artifact checksums and limitations.
- Server-Sent Events run log streaming, run retry, artifact download and
  HTML/Markdown/JSON/CSV report export.
- React + TypeScript single-page UI covering workspace, project overview,
  compound library, compound detail, workflow library, visual workflow editor,
  run monitor, results explorer, model registry, data-source status, settings
  and about pages, with light/dark themes and a narrow-screen layout.
- Headless `hcs-discovery` CLI with project, dataset, compound, workflow, run,
  report, model, config, cache and database commands. `--json` works before or
  after the subcommand.
- Versioned `/api/v1` HTTP API with bearer-token enforcement for non-loopback
  binding, loopback-only CORS, request IDs, security headers, payload limits,
  rate limiting and a redacted error envelope.
- Local OpenAI-compatible LLM provider probe with a local-only network policy
  and an explicit opt-in for remote endpoints. No LLM feature is required for
  the CPU demo.
- Vulkan device probe that reports hardware presence only and never implies
  model support.
- Self-contained wheel that bundles the built SPA, so a `pip install` serves the
  UI without a Node toolchain.
- Backend test suite (82 tests), frontend typecheck/build, three Playwright
  end-to-end tests, Ruff and mypy gates, Alembic migration tests and security
  tests for redaction and network policy.
- GitHub Actions CI for Linux and Windows backend gates, frontend build and
  Playwright end-to-end tests, CodeQL analysis, dependency review, a license
  policy check and secret scanning. The pipeline is green on both operating
  systems, and the tag-triggered release workflow published `v0.1.0` as a
  prerelease with a CycloneDX SBOM, `SHA256SUMS.txt` and a verified
  build-provenance attestation.
- Apache-2.0 license, NOTICE, citation metadata, security policy, code of
  conduct, contribution guide and the documentation set required by the
  project brief.

### Fixed

- `uv sync` now works on a fresh checkout before the SPA is built. A Hatch build
  hook creates the missing `apps/web/dist` directory; release builds still
  compile the frontend before packaging.
- Narrow-screen tables no longer clip primary data. Secondary columns are hidden
  deliberately, identifiers ellipsize, card headers wrap their actions, and the
  settings environment table stacks label above value.
- Mypy no longer aborts on RDKit 2026.9.1's invalid bundled type stubs; the CI
  job removes only that stub package before type checking.

### Known limitations

- Docking, molecular dynamics, learned property prediction and structure
  prediction adapters are listed as `planned` and are not runnable.
- Workflows are linear single-input chains. Multi-input merge nodes are
  explicitly rejected by validation.
- The queue and database target a single local machine. There is no
  multi-tenant isolation, PostgreSQL deployment or distributed worker support.
- The LLM provider is a client and a registry entry, not an autonomous agent.
- No predictive-accuracy claim is made. The included validation protocol
  describes what would be required before such a claim could be made.
- There is no hosted service, telemetry, account system or cloud dependency.
