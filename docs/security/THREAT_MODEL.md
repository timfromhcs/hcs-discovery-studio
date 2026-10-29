# Threat model

Scope: the local-first HCS Discovery Studio application, CLI, API, worker and
bundled SPA in version 0.1.0. The model assumes a single trusted operator on a
personal workstation or a small shared server.

## Assets

| Asset | Why it matters |
|---|---|
| Imported structures, names and source IDs | May be confidential research data |
| Run results and artifacts | Scientific record; tampering changes conclusions |
| Database and manifests | Provenance and audit trail |
| API token and provider keys | Access to the local API or an external provider |
| Local filesystem | Runs, cache, uploads and the SQLite file |
| CI/release credentials | Supply-chain integrity |
| Reputation of published results | False claims cause real harm |

## Actors

- The local operator (trusted).
- A collaborator with access to the same machine or a shared data directory
  (semi-trusted).
- A malicious file supplied by a third party (untrusted input).
- A malicious or compromised dependency (supply chain).
- A remote LLM provider, if explicitly enabled (external).
- An unauthenticated network client, if the operator binds beyond loopback
  (untrusted).

## Trust boundaries

```text
[untrusted file] --upload--> [API parser] --validated rows--> [SQLite]
[browser] --HTTP/SSE--> [local API] --services--> [DB + filesystem]
[worker] --in-process node--> [RDKit / future adapters]
[app] --optional probe--> [LLM endpoint]
[GitHub Actions] --build--> [release artifact]
```

There is no sandbox between the application and a node handler. A third-party
node runs with the user's privileges. This is a deliberate 0.1.0 limitation.

## Threats and mitigations

### 1. Unauthorized network access

**Threat:** The API is bound to `0.0.0.0` and exposes research data.

**Mitigations:**

- Default host is `127.0.0.1`.
- `create_app` refuses to start on a non-loopback host without
  `HCS_API_TOKEN`.
- Bearer tokens are compared with `secrets.compare_digest`.
- CORS is enabled only for loopback development origins.
- Rate limiting applies to expensive POSTs on non-loopback binds.
- Security headers include CSP, `X-Frame-Options: DENY`, `nosniff` and
  `Referrer-Policy: no-referrer`.

**Residual:** No TLS, no user accounts, no per-project authorization, no token
rotation or expiry. A shared token grants full access. Use a reverse proxy with
TLS and network controls.

### 2. Secret disclosure

**Threat:** A provider key or API token appears in logs, errors, reports or the
UI.

**Mitigations:**

- Secrets are read from environment variables, not the database.
- `Settings.public_dict()` reports only `configured`/`missing`.
- `redact_text` removes common token/key/private-key shapes and registered
  secrets.
- Run event messages are redacted before storage.
- API errors use a stable envelope without tracebacks.
- Reports contain no configuration secrets.
- CI does not receive model keys.

**Residual:** Redaction is pattern-based and cannot catch every secret format.
Never log a secret deliberately. A secret pasted into an issue or screenshot is
outside the application's control.

### 3. Path traversal and unsafe filenames

**Threat:** A crafted upload name or artifact name writes outside the data
directory, or a workflow config (for example a docking `receptor_path` or an
agent `plan_id`) makes the server read an arbitrary host file.

**Mitigations:**

- `safe_filename` strips path separators, control characters and reserved
  Windows names.
- `safe_join` resolves symlinks with `realpath` and rejects absolute paths,
  escapes and sibling directories that share the base prefix.
- `dock.vina` reads receptors only under `<data_dir>/receptors` unless the
  local operator sets `HCS_ALLOW_EXTERNAL_RECEPTOR_PATHS=true`.
- Agent plan ids must match `^plan_[0-9a-f]{12}$` before any path is built.
- `relative_artifact_path` verifies the artifact is under the run directory.
- The SPA file handler resolves and checks the candidate is under `WEB_DIST`.

**Residual:** Symlinks created by the local user could redirect writes. The
application does not follow untrusted symlinks intentionally, but filesystem
ACLs are the operator's responsibility.

### 4. Malicious or malformed input

**Threat:** A huge or malformed CSV/SDF causes a crash, memory exhaustion or
code execution.

**Mitigations:**

- Upload size limit (`HCS_MAX_UPLOAD_MB`) and row limit
  (`HCS_MAX_IMPORT_ROWS`).
- CSV/SDF/SMILES parsers with per-row error capture.
- RDKit parsing, not `eval`.
- No archive extraction.
- Pydantic validation with bounded fields.

**Residual:** A single extremely large molecule or pathological SMILES can still
consume CPU. There is no per-row timeout. Run imports on a machine with
appropriate limits.

### 5. Cross-site scripting and report injection

**Threat:** A compound name or SMILES contains HTML/JS and executes in the UI or
an exported report.

**Mitigations:**

- React escapes text by default; the UI does not use `dangerouslySetInnerHTML`.
- Report Markdown and HTML escape imported values.
- CSP restricts scripts to `self` and blocks framing.
- Uploaded files are never served as HTML from the SPA mount.

**Residual:** A user who opens a downloaded report outside the app trusts that
file's contents. Markdown tables escape `|` but not every renderer's extensions.

### 6. Server-side request forgery via providers

**Threat:** A configured provider URL points at an internal service.

**Mitigations:**

- Default network policy blocks non-loopback endpoints.
- Remote use requires two explicit settings.
- The probe only calls `GET /models` on the configured base URL.
- No user-controlled URL is fetched by the API.

**Residual:** In remote mode, an operator can point the client at any host. This
is an explicit trust decision, not a sandbox.

### 7. Prompt injection (future LLM features)

**Threat:** A model output instructs the system to run a tool or exfiltrate data.

**Current state:** There is no LLM chat feature and no LLM workflow node. The
provider is a probe and a client only.

**Required before enabling LLM tools:**

- Treat model output as untrusted text.
- Require explicit human approval for tool calls.
- Allowlist tools and arguments.
- Never pass secrets to a model.
- Log the exact prompt and tool decision, redacted.

### 8. Artifact and database tampering

**Threat:** A local actor modifies results or manifests and the report looks
authoritative.

**Mitigations:**

- Artifacts are hashed with SHA-256 at write time and recorded in the database
  and manifest.
- The manifest includes the workflow hash, dataset checksum and input hash.
- Reports list artifact checksums.

**Residual:** There is no signature or append-only ledger. A local actor with
write access can modify both the file and the database. Hashes detect accidental
corruption, not a determined insider. Share the manifest and checksums through a
separate channel if integrity matters.

### 9. Denial of service

**Threat:** A user or process submits many runs or huge imports.

**Mitigations:**

- Row and upload limits.
- One worker by default.
- Rate limiting on non-loopback expensive POSTs.
- Per-node timeout.
- Cancellation.

**Residual:** No global queue quota, disk quota or per-user limit. A local user
can fill the disk.

### 10. Supply chain

**Threat:** A compromised dependency or GitHub Action modifies code or steals
secrets.

**Mitigations:**

- Lockfiles for Python and npm.
- GitHub Actions pinned to commit SHAs.
- Least-privilege workflow permissions.
- CodeQL, dependency review, secret scanning and license policy checks.
- Release builds from a verified tag after tests.
- SBOM and checksums for release artifacts.

**Residual:** No reproducible-build attestation for every artifact, no hardware
signing, and dependency review depends on advisory coverage. Review dependency
updates before merging.

### 11. Data exfiltration through telemetry

**Threat:** The app phones home.

**Mitigations:**

- No telemetry, analytics, crash reporting or auto-update.
- No network call in the CPU demo.
- The only outbound client is the optional LLM provider, gated by policy.

**Residual:** A future plugin could add a network client. Review plugins.

### 12. CI credential misuse

**Threat:** A pull request from a fork runs with repository write permissions.

**Mitigations:**

- Default `contents: read`.
- Release jobs run only on tags and depend on test jobs.
- No secrets are available to pull-request jobs.
- Actions are pinned.

**Residual:** A compromised maintainer account can change workflows. Enable
branch protection, required reviews and 2FA.

## Assumptions

- The operating system account and filesystem permissions are trustworthy.
- The user does not run untrusted third-party node code.
- The browser and OS are patched.
- The user reviews imported data licenses before use.
- The user does not expose the loopback server through an unauthenticated proxy.

## Out of scope

- Multi-tenant isolation and hostile co-tenants.
- Regulatory compliance certification (HIPAA, GxP, 21 CFR Part 11).
- Clinical decision support.
- Protection against a local administrator or root.
- Malicious model weights (none are bundled).
- Container escape (no container is shipped).

## Review triggers

Revisit this model when adding: authentication, multi-user projects, a hosted
deployment, LLM tools, model weights, archive import, plugin discovery, or any
new outbound network client.
