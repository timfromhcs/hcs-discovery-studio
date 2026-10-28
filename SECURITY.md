# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | Yes (preview) |
| < 0.1 | No |

HCS Discovery Studio is a local-first preview. Security fixes are applied to the
latest published release.

## Reporting a vulnerability

Please do **not** open a public issue for a suspected vulnerability.

Use GitHub's private vulnerability reporting on the repository:
`Security` → `Advisories` → `Report a vulnerability`.

Include:

- the affected version or commit,
- the operating system and Python version,
- a minimal reproduction or proof of concept,
- the impact you believe is possible,
- any suggested mitigation.

You can expect an acknowledgement within seven days. This is a volunteer
project; timelines for a fix depend on severity and reproducibility. Please
allow a reasonable disclosure window before publishing details.

## Scope

In scope:

- the Python package, CLI, HTTP API and bundled web application,
- authentication and network-policy enforcement,
- path traversal, archive and upload handling,
- secret leakage in logs, reports, API errors or artifacts,
- cross-site scripting or unsafe HTML rendering in the UI and reports,
- dependency vulnerabilities that affect a shipped code path.

Out of scope:

- findings that require a modified local database, a compromised operating
  system account or physical access,
- missing security headers on a deliberately loopback-only development server
  that are already documented,
- vulnerabilities in planned engines that are not bundled or runnable,
- reports about the absence of features listed as planned,
- social engineering and denial-of-service against your own local machine.

## Security model in brief

- The default bind address is `127.0.0.1`. Binding to any other interface
  requires `HCS_API_TOKEN`; the application refuses to start otherwise.
- In local-only network policy, non-loopback LLM endpoints and remote data
  connectors are blocked in code, not only in the UI.
- Secrets are read from environment variables. The UI and CLI always redact
  secret values; they are never written to the database, run manifests or
  reports.
- Run artifacts are written beneath the configured data directory using
  sanitised filenames and traversal checks.
- Uploads are size-limited and row-limited, and every row outcome is recorded.
- Reports HTML-escape imported names, SMILES and metric values.
- The application does not send telemetry or contact external services during
  the default CPU demo.

The full threat model, including assets, trust boundaries, mitigations and
residual risks, is in `docs/security/THREAT_MODEL.md`.

## Secrets and credentials

- Never commit a `.env` file. Only `.env.example` is tracked.
- Put credentials in your OS environment or a local secret manager.
- Rotate any credential that has been pasted into a chat, issue, log or
  screenshot.
- CI uses short-lived `GITHUB_TOKEN` permissions and does not receive model API
  keys. Optional live-provider checks must be separate, manual workflows with
  explicit secrets and no secret logging.

## Dependency and supply-chain controls

- Python dependencies are locked in `uv.lock`; frontend dependencies are locked
  in `apps/web/package-lock.json`.
- GitHub Actions are pinned to full commit SHAs and run with least-privilege
  permissions.
- CI runs CodeQL, dependency review, a license policy check, secret scanning
  and the full test suite.
- Release artifacts are built from a verified tag in CI and published with
  SHA-256 checksums and a CycloneDX SBOM.

## Safe use

This software produces computational prioritisation signals. It does not prove
binding, safety, efficacy or clinical utility. Do not use its output as the sole
basis for experimental, clinical, regulatory or commercial decisions.
