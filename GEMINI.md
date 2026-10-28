# GEMINI.md — HCS Discovery Studio

> **Master build directive for an autonomous coding agent**  
> Product: **HCS Discovery Studio**  
> Tagline: *Open science. Reproducible discovery. Made with love by hcsmedia.*  
> Proposed repository slug: `hcs-discovery-studio`  
> Intended license: Apache-2.0 for original project code, subject to a complete third-party license audit.  
> Status goal: first genuinely stable `v1.0.0` release, with all claims backed by executed tests and build evidence.

---

## 0. Mission, operating contract, and definition of success

You are the autonomous software engineering agent responsible for designing, implementing, testing, hardening, documenting, and releasing HCS Discovery Studio. Do not stop at a visual prototype. Build a functional, local-first, open-source scientific software platform for AI-assisted drug-discovery research that offers a polished graphical UI, a headless command-line interface, a versioned API, workflow automation, inspectable execution, and plug-in support for an evolving ecosystem of AI models and scientific engines.

The target experience is that a researcher can explore targets and compounds, assemble and run a reproducible computational workflow, watch every stage live, inspect evidence and uncertainty, export results, and run the same workflow from a terminal or another application without opening the UI.

### 0.1 Primary goals

1. **Local-first:** a useful installation must run locally without a paid cloud service, without Docker being mandatory, and without requiring a remote LLM. Core chemistry and deterministic test workflows must work offline after installation.
2. **CPU-first, Vulkan-aware:** CPU is the dependable baseline. Vulkan acceleration is an optional capability that must be detected and demonstrated for each supported runtime/model. Never imply that every scientific model runs on Vulkan. Do not require CUDA.
3. **Model-agnostic:** provide adapter contracts for local and hosted language models, scientific ML models, and traditional scientific executables. Separate LLM orchestration from scientific computation.
4. **Headless and observable:** every UI action that initiates a workflow must have an equivalent documented CLI/API action. Long jobs must expose status, progress, logs, artifacts, cancellation, failure reasons, and provenance while running.
5. **Reproducible:** capture inputs, normalized structures, workflow definition, configuration, model/provider versions, dependency versions, seeds where applicable, hardware/backend information, timestamps, and output hashes.
6. **Scientific humility:** predictions are hypotheses and ranking signals, not proof of binding, safety, efficacy, clinical utility, or therapeutic success. Display validation status and uncertainty honestly.
7. **Beautiful and accessible UX:** create a cohesive professional scientific product, not a generic admin dashboard. Responsive, keyboard accessible, readable, fast, clear, and visually informative.
8. **Security by default:** treat molecules, structure files, datasets, model output, plug-ins, remote providers, and uploaded workflow definitions as untrusted input. Secrets never belong in source, logs, screenshots, issue reports, model prompts, or Git history.
9. **Open-source quality:** include tests, CI, dependency/ license provenance, contribution guidance, responsible-use guidance, reproducible setup, a visually strong README, and a tagged, buildable stable release.
10. **No fabricated completion:** claim that a feature, test, model adapter, Vulkan backend, cloud build, or release is working only when it has been executed and verified. Clearly separate implemented, tested, experimental, unavailable, and planned features.

### 0.2 Non-negotiable engineering rules

- Inspect the actual workspace and installed tools before modifying anything. Do not overwrite unrelated repositories or files. If this directive is being used as the bootstrap prompt, create a clean project directory called `hcs-discovery-studio` in the designated workspace.
- Establish a written implementation plan and living checklist in `docs/engineering/IMPLEMENTATION_STATUS.md`. Update it after each phase and test loop.
- Work in small, reviewable steps. After each meaningful change: run targeted tests, inspect the diff, fix regressions, then run the broader suite appropriate to the phase.
- Keep a concise test/decision log in `docs/engineering/AGENT_LOG.md` with commands, actual exit codes, failures, fixes, and unresolved blockers. Do not include secrets, personal data, or sensitive scientific input data in logs.
- Do not hide failing tests, make tests pass by weakening assertions without justification, skip real code paths, substitute mocks for all integration tests, or convert errors into fake success responses.
- Tests may use mocks for external services, but each adapter must have a contract test and a clearly labelled optional live smoke test where credentials or large model downloads are required.
- Never use `git push --force`, disable repository protections, commit credentials, or bypass required checks. Do not make a release if core acceptance criteria are failing.
- Do not create cloud infrastructure that can incur charges without explicit user authorization. CI builds and a container image are in scope; a production deployment to a paid provider requires a specified provider and explicit approval.
- If required account access, credentials, hardware, external service availability, or a model download is genuinely unavailable, continue with all work that can be completed safely, document the blocker, and never claim the missing check passed.
- Keep the project genuinely open source. Do not copy proprietary source code, scrape restricted data, or relicense a dependency/model/dataset under HCS terms. Record licenses independently for source, weights, and datasets.

### 0.3 Definition of success

HCS Discovery Studio is ready for `v1.0.0` only if all release gates in Section 16 are satisfied, the local installation path works on a clean environment, the core flows work end-to-end, CI runs from the pushed repository, the release artifacts build successfully, and the documentation matches the product that actually exists. “No known bugs” is not a provable claim; instead provide a transparent limitations register and evidence that the defined tests and checks pass.

---

## 1. Product identity and positioning

**Product name:** HCS Discovery Studio  
**Short description:** A local-first, open-source AI drug-discovery research workbench with pluggable models, reproducible workflows, scientific provenance, live execution, and a complete CLI/API.  
**Credits:** “Made with ❤️ by hcsmedia” — place in the application footer, About screen, README, and release notes. Use the supplied HCS brand assets if they exist and are authorized. If they do not exist, create original SVG branding; never borrow third-party logos without permission.

**Positioning statement:** Bring the best independent open scientific tools into one coherent, inspectable workflow, and make the whole workflow usable through both a friendly UI and automation interfaces.

Do not market the product as a replacement for wet-lab validation, a regulator-approved medical system, a clinical decision system, or a platform proven to discover better drugs than commercial tools. The differentiator to prove first is **better openness, reproducibility, access, operability, and extensibility**. Scientific performance superiority can be claimed only after fair, documented benchmarking.

### 1.1 Product principles

- **One project, one provenance graph:** targets, structures, compounds, assays, predictions, runs, reports, and exported files should be linked, not scattered across folders.
- **Every prediction is explainable enough to audit:** show the method, version, input identifiers, score direction, units, uncertainty if available, and relevant caveats.
- **Make compute costs visible:** estimate before running where possible; show expected memory/VRAM class, backend, queue position, runtime history, and cancellation state.
- **Progressive fidelity:** do cheap checks first, reserve expensive calculations for the most promising and valid candidates, and preserve the reason each item advanced or was filtered out.
- **Researcher remains in control:** no autonomous wet-lab activity, no hidden external uploads, no silent billing, and no destructive actions without clear consent.
- **Portable results:** exports must not depend on a proprietary account or a live server.
- **Explicit capability, not marketing:** each engine/model advertises verified capabilities and limitations through metadata and a local “Doctor” report.

---

## 2. Research baseline and tools to evaluate

This section sets the research starting point, not a claim that every tool is already integrated. Before selecting exact dependency versions, verify each project's current status, license, install requirements, model-weight license, supported runtimes, and citation instructions from its authoritative repository/documentation. Record the findings in `docs/research/COMPONENT_AND_LICENSE_AUDIT.md` with the date checked.

### 2.1 Scientific ecosystem: candidates for adapters

| Component / ecosystem | Likely role | Source | Important caveat |
|---|---|---|---|
| RDKit | Molecular parsing, canonicalization, descriptors, fingerprints, substructure/similarity search, depictions | https://github.com/rdkit/rdkit | BSD-3-Clause code license; verify licenses for any additional data or contributed modules. Core cheminformatics baseline. |
| AutoDock Vina | Classical molecular docking and pose search | https://github.com/ccsb-scripps/AutoDock-Vina and https://autodock-vina.readthedocs.io/ | CPU multithreading is useful for local workflows. Docking scores are not experimental binding affinities. |
| GNINA | Docking with CNN-assisted rescoring/refinement | https://github.com/gnina/gnina | Verify build, model-weight, and hardware requirements per release. CNN rescoring/refinement can be much slower than classical scoring. |
| OpenMM | Molecular mechanics and molecular-dynamics simulations | https://github.com/openmm/openmm and https://openmm.org/ | CPU/reference platform is a practical baseline; CUDA/OpenCL platforms and other acceleration paths have separate constraints and license considerations. Do not claim Vulkan support unless an actual supported backend is proven. |
| Boltz-1 / Boltz-2 | Biomolecular structure and interaction prediction; Boltz-2 includes binding-affinity prediction research | https://github.com/jwohlwend/boltz and https://www.boltz.com/boltz2 | Repository and model are reported under MIT; audit the current release, all weights, dependencies, and minimum hardware before integration. Large models may not be practical on a small local machine. |
| Chai-1 | Biomolecular structure prediction / co-folding | https://github.com/chaidiscovery/chai-lab | Repository states Apache-2.0 for code and weights; re-check the exact release and dependencies. Hardware/runtime requirements can be high. |
| DiffDock | ML-based ligand docking / pose prediction | https://github.com/gcorso/DiffDock | Experimental/model-specific integration; verify license, model files, installation status, and benchmark limitations for the selected version. |
| Chemprop | Molecular property prediction using message-passing neural networks | https://github.com/chemprop/chemprop | MIT license stated by project; model behavior depends on training data, task definition, and evaluation split. |
| DeepChem | Broader machine-learning toolkit for chemistry and biology | https://github.com/deepchem/deepchem | Use only modules that are maintained, licensed, documented, and appropriate for this platform; do not add the entire stack without need. |
| OpenADMET | Open science work on ADMET data and predictive modelling | https://github.com/OpenADMET | Treat this as an ecosystem/source to evaluate. Audit the exact model or dataset repository and license before bundling it. |
| Open Targets Platform | Target–disease evidence, target prioritization, and evidence integration | https://platform-docs.opentargets.org/ | Useful target-research integration; respect data/source licenses, API terms, rate limits, and versioned releases. |
| ChEMBL | Curated bioactivity and medicinal-chemistry data | https://chembl.gitbook.io/chembl-interface-documentation/web-services | Preserve source record IDs, assay metadata, units, confidence fields, and data release version. Avoid mixing incompatible assay contexts. |
| PubChem PUG REST | Compound records, identifiers, properties, and structure queries | https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest | Respect API guidance, rate limiting, attribution, and source identity. It is an external data source, not a guarantee of scientific correctness. |
| Protein Data Bank (PDB) | Experimental macromolecular structures and metadata | https://www.rcsb.org/ and https://www.rcsb.org/docs/programmatic-access/web-apis-overview | Keep accession, assembly, chain, organism, method, resolution/quality metadata, and citation. Handle mmCIF as well as PDB where practical. |
| UniProt | Protein sequence, annotation, and accession resolution | https://www.uniprot.org/help/api | Keep accession and release/source provenance. Avoid assuming that a sequence/annotation is complete or experimentally confirmed. |
| Benchling | Commercial reference point for unified scientific records, workflows, collaboration, and lab integrations | https://www.benchling.com/features and https://www.benchling.com/platform | Not an open-source dependency. Learn from its unified data model, metadata, permissions, and workflow UX; do not copy proprietary UI/code. |
| KNIME | Workflow-canvas reference for visual scientific/data pipelines | https://www.knime.com/ | Review current license and extension terms before any integration. Inspiration only unless a concrete adapter is justified. |

### 2.2 What “SOTA” means here

There is no single application that owns every state-of-the-art stage of drug discovery. The state of the art is a shifting combination of curated evidence, cheminformatics, structure modelling, docking, property/ADMET prediction, simulation, data management, and experimental validation. Many components have different hardware requirements, data provenance, licenses, and accuracy limits.

Do not simply add as many models as possible. Build a capability registry with explicit statuses:

- `available`: executable and passed local health/contract checks.
- `available_with_limits`: usable with documented limitations.
- `needs_install`: implementation exists but its optional dependency is absent.
- `needs_credentials`: remote provider needs a configured key.
- `needs_hardware`: current host does not meet documented requirements.
- `experimental`: interface exists but it has not passed the required scientific or operational validation.
- `disabled_by_policy`: blocked by configured responsible-use policy.
- `unavailable`: unsupported, broken, or license-incompatible; explain why.

The UI must never show an unavailable model as runnable. Build a “What works on this machine?” page from actual health checks, not hardcoded claims.

### 2.3 Proposed differentiators that are realistic to build

1. **Unified, versioned workflow graph:** DAG-based workflows with explicit inputs, outputs, dependencies, retries, cache policy, and resource budgets.
2. **Progressive-fidelity screening:** RDKit validation and cheap descriptors/fingerprints first; then configurable property/ADMET predictors; then docking/rescoring; then high-cost structure-model or simulation steps only when feasible.
3. **Multi-objective ranking:** show Pareto fronts and independent metrics instead of hiding all science in one opaque “drug score.” Make weights visible when the user chooses a composite score.
4. **Uncertainty and applicability-domain awareness:** display confidence/uncertainty only when the selected method supports it; otherwise say “not estimated.” Flag out-of-domain compounds where the method can assess this.
5. **Reproducibility and cache reuse:** content hashes for inputs/configuration/model artifacts, safe cache keys, immutable run manifests, and diffing between runs.
6. **Resource-adaptive execution:** concurrency limits, cancellation, checkpointing where supported, resource estimates, CPU thread controls, optional Vulkan providers, and graceful fallback only when correctness is preserved and the fallback is visible.
7. **First-class terminal mode:** every run can be launched, queried, streamed, cancelled, and exported from CLI/API.
8. **Evidence cards:** every important result carries source records, model and version, scores/units, data-quality notes, uncertainty, and links to run artifacts.
9. **Offline operation:** after data/model assets are downloaded, the core app should not silently contact remote services. Network egress must be explicit and visible.
10. **Open interfaces:** stable plugin contracts, versioned JSON schemas, OpenAPI, exportable workflow definitions, and test fixtures for third-party adapter authors.

These are product/engineering advantages to test. Do not claim better scientific accuracy than established tools until the benchmark protocol in Section 13 proves it.

---

## 3. Recommended architecture

Use a maintainable monorepo with a clean boundary between UI, API, orchestration, scientific engines, and model providers. Prefer the simplest design that can be tested end-to-end. Avoid microservices for their own sake.

### 3.1 Proposed stack

**Frontend**
- React + TypeScript + Vite.
- A consistent component system based on accessible primitives; Tailwind CSS is acceptable if design tokens are centralised.
- TanStack Query or equivalent for server state; keep complex scientific run state out of scattered component-local state.
- React Flow or a comparable mature graph editor for workflow DAGs if the package's license and maintenance status pass the audit.
- ECharts, Plotly, or another maintained charting library for scientific graphs; verify license and accessibility requirements.
- RDKit-generated 2D depictions via backend SVG/image generation or a well-maintained browser-compatible RDKit build. For macromolecular 3D, evaluate Mol* or another properly licensed viewer. Never render untrusted structure content as unsanitized HTML.
- Playwright for browser E2E tests.

**Backend**
- Python 3.12+ unless the dependency audit demonstrates a better-supported version for the selected scientific stack. Verify version compatibility rather than pinning Python to an arbitrary newest release.
- `uv` for reproducible dependency/environment management; commit the lockfile.
- FastAPI + Pydantic for typed/versioned HTTP APIs and generated OpenAPI.
- SQLAlchemy 2 + Alembic for relational persistence and migrations.
- SQLite as the local default; PostgreSQL for multi-user/cloud deployment. Keep the repository/data layer portable and test both database backends.
- A worker process and a documented queue abstraction for long-running jobs. Start with a robust local, persistent SQLite queue if it meets concurrency requirements; use a separately validated PostgreSQL-backed queue or other properly supported queue in deployment. Keep jobs idempotent and lease-based; do not assume exactly-once execution.
- Structured JSON logging, correlation IDs, explicit error models, health/readiness endpoints, and metrics hooks.

**Packaging and tooling**
- `pyproject.toml`, `uv.lock`, `package.json`, lockfile for the selected JS package manager, `.editorconfig`, formatter/linter config, `pre-commit` if useful, and a single documented command for the common test suite.
- Native local setup must be supported on Windows 11 x64 and Linux x64. Docker/Compose may be offered as an optional reproducible deployment path but must not be the only way to run the application.
- Do not commit weights, datasets, local DBs, caches, virtual environments, or large binaries to Git. Follow GitHub's repository size/file limits; use release artifacts or approved external model/data storage where needed.

### 3.2 Repository layout

Implement a layout close to the following; adjust only when there is a documented reason:

```text
hcs-discovery-studio/
├─ GEMINI.md
├─ README.md
├─ LICENSE
├─ NOTICE
├─ CITATION.cff
├─ pyproject.toml
├─ uv.lock
├─ package.json                 # if using a root task runner
├─ pnpm-lock.yaml               # or the selected package manager's lockfile
├─ .gitignore
├─ .gitattributes
├─ .editorconfig
├─ .env.example                 # placeholders only; never real secrets
├─ apps/
│  └─ web/                      # React + TypeScript UI
├─ packages/
│  └─ shared-schemas/           # versioned JSON/API schemas, where appropriate
├─ src/
│  └─ hcs_discovery/
│     ├─ api/                   # FastAPI routes and API dependencies
│     ├─ cli/                   # headless command interface
│     ├─ core/                  # domain objects, validation, errors
│     ├─ database/              # models, repositories, migrations
│     ├─ workflow/              # DAG schema, validation, executor, cache, events
│     ├─ jobs/                  # queue, worker, retries, cancellation, leases
│     ├─ plugins/               # registry and adapter contracts
│     │  ├─ llm/                # language-model providers
│     │  └─ science/            # chemistry / structural / ADMET / simulation
│     ├─ chemistry/             # canonicalization, descriptors, formats
│     ├─ datasets/              # import, provenance, source connectors
│     ├─ security/              # policy, secret references, safe paths
│     ├─ reports/               # report generation and export
│     └─ telemetry/             # local health metrics; privacy-first
├─ tests/
│  ├─ unit/
│  ├─ contract/
│  ├─ integration/
│  ├─ e2e/
│  ├─ scientific/
│  ├─ security/
│  ├─ fixtures/
│  └─ performance/
├─ examples/
│  ├─ workflows/
│  ├─ datasets/                 # only tiny, redistributable examples
│  └─ api/
├─ docs/
│  ├─ user-guide/
│  ├─ developer-guide/
│  ├─ architecture/
│  ├─ research/
│  ├─ security/
│  ├─ scientific-validation/
│  └─ engineering/
├─ scripts/
│  ├─ dev/                      # safe cross-platform scripts
│  ├─ ci/
│  └─ release/
├─ deploy/
│  └─ containers/               # optional, not required for local use
├─ .github/
│  ├─ workflows/
│  ├─ ISSUE_TEMPLATE/
│  ├─ PULL_REQUEST_TEMPLATE.md
│  ├─ dependabot.yml
│  └─ CODEOWNERS                 # only if owners are genuinely known
└─ assets/
   ├─ brand/
   └─ screenshots/              # real, generated application screenshots
```

Keep optional scientific dependencies in named extras/groups so a user can install the core application without downloading every large ML stack. Use lazy loading for adapters and produce actionable error messages when a dependency is missing.

### 3.3 Domain architecture and data model

At minimum, define and migrate the following entities. Use typed schemas, unique IDs, foreign keys, timestamps, and explicit provenance fields. Avoid storing important structured data only in an unvalidated JSON blob.

- **Project:** name, purpose, user-facing notes, created/updated dates, workspace policy, and default resource limits.
- **Target:** stable identifier(s), gene/protein accession, organism, sequence checksum if available, evidence references, selected structure references, and provenance.
- **Structure:** source/accession, modelled/experimental status, chain and biological assembly, file checksum, format, quality metadata, source license/terms, and local asset path.
- **Compound:** canonical isomeric SMILES (where RDKit can parse it), InChI/InChIKey when supported, source IDs, stereochemistry and salt/tautomer handling metadata, molecular descriptors, validation warnings, and structure file references.
- **Dataset:** source, retrieval date, release/version, license, schema, checksum, record counts, missingness profile, transformations, and citation.
- **Assay/measurement:** original value, unit, relation operator (`=`, `<`, `>`), assay type, organism, target, conditions when known, source record, confidence/curation metadata, and normalized value only when the conversion is valid.
- **Model/Engine:** adapter ID, version, package/runtime/model-weight identifiers and hashes where possible, license metadata, required dependencies, supported device providers, resource estimates, capability flags, and validation status.
- **Workflow definition:** versioned DAG, typed input/output schemas, node configuration, validation warnings, resource budget, safety classification, and workflow content hash.
- **Run:** workflow snapshot, queue/run status, timestamps, cancellation reason, per-node status, host and runtime info, config/seed data, input/output hashes, and linked artifacts.
- **Prediction:** value(s), units, score direction, uncertainty/calibration where supported, method/engine/model version, applicability-domain notes where supported, warnings, and provenance links.
- **Artifact:** safe relative path or object-store key, media type, size, checksum, producing node, and retention policy.
- **Audit event:** actor/source, action, object reference, timestamp, outcome, and redacted metadata. Do not log secrets or raw user prompts by default.

Do not mix incompatible bioactivity values into one column with an unqualified number. Preserve raw values and units, normalize only using explicit, unit-safe conversion rules, and preserve censored values such as `> 10 µM` rather than silently converting them to exact observations.

### 3.4 Workflow engine

Implement DAG execution with:

- Schema validation before queueing.
- Cycle detection, dependency validation, missing-input checks, and plugin capability checks.
- Stable node IDs and typed outputs.
- Per-node status: `pending`, `queued`, `running`, `succeeded`, `failed`, `cancelled`, `skipped`, `retrying`, `blocked`.
- Progress events with timestamps, safe log lines, current stage, and best-effort progress fraction; do not manufacture percentages if an engine provides no meaningful progress signal.
- Cancellation tokens; timeout handling; retry policy for transient infrastructure failures only; explicit opt-out for unsafe-to-repeat nodes.
- Content-addressed cache keys based on normalized inputs, node config, engine/model version, dependency/runtime version, and seed where relevant. Never reuse output across incompatible scientific versions.
- Artifact validation, checksums, and safe output directory boundaries.
- Checkpoint/resume where the engine supports it. Otherwise label a restarted node as a fresh execution.
- A run manifest that can be exported with the workflow and outputs.
- No arbitrary shell in workflow definitions. Scientific executables must be invoked through registered adapters with argument arrays (not interpolated shell strings), timeouts, a controlled environment, and validated paths.

Build a small deterministic example workflow with tiny inputs so a clean machine can validate the whole pipeline without downloading large foundation models.

---

## 4. CPU + Vulkan runtime strategy

### 4.1 Correct claims about hardware

**Primary target-machine profile to verify when available:** Windows 11 Pro x64, AMD Ryzen 7 7735HS, AMD Radeon 680M (RDNA2 iGPU), Vulkan-capable graphics stack, shared-memory graphics allocation (the current configuration may reserve approximately 8 GB UMA), and no NVIDIA CUDA device. Detect actual runtime values instead of hard-coding them; the profile is a test target, not a guarantee that any specific model fits in memory. Include a CPU-only test path so the application still works if Vulkan drivers are missing or disabled.

The platform must not treat Vulkan as a universal GPU API for science. Vulkan can be useful for specific inference runtimes, but many scientific packages use CPU, CUDA, OpenCL, or their own supported platforms. A package's use of GPU in general does not imply it supports Vulkan. For example, the Vulkan backend documentation for PyTorch mobile describes limitations and experimental status; OpenMM has its own platform model. Validate exact support rather than guessing.

### 4.2 Required behavior

1. **CPU baseline:** the platform itself, orchestration, RDKit-based deterministic chemistry, basic descriptors/fingerprints, data import/export, test fixtures, API, CLI, and UI must work on CPU.
2. **Vulkan probing:** detect Vulkan-capable runtimes and device/driver information via supported tools/libraries. Do not assume that the presence of a Vulkan device proves a model supports it.
3. **Per-model capability declaration:** each model adapter reports `cpu`, `vulkan`, `cuda`, `rocm`, `opencl`, or other capabilities only after checks required by that adapter pass. Keep `supported` distinct from `detected` and `actually tested`.
4. **Backend selection:** expose `auto`, `cpu`, and an explicit backend selection when valid. `auto` selects only verified compatible providers. If Vulkan fails, a fallback to CPU is allowed only when the user has accepted fallback and the result semantics remain equivalent; log and display the selected backend. Never silently change model, quantization, precision, or algorithm.
5. **Memory and concurrency:** configure thread count, memory/VRAM limits where supported, batch sizes, and worker concurrency. Detect out-of-memory conditions and stop/recover safely rather than repeatedly crashing the full application.
6. **Benchmark:** provide a reproducible `doctor`/benchmark command comparing the same supported inference task on available backends, with warm-up, repetitions, output-consistency tolerance, device/runtime version, and median/percentile latency. Do not compare different models and label the result a backend speedup.
7. **No CUDA dependency:** base install, core tests, and supported CPU workflows must not import CUDA packages. CUDA-only models remain optional and must be shown as unavailable or remote-only on a host without CUDA.
8. **Truthful unsupported path:** if a research model cannot run locally on the current hardware, keep its adapter as optional/experimental or allow a configured remote provider with explicit data-sharing consent. Do not pretend a fake prediction is real.

### 4.3 LLM provider interoperability

Implement an LLM gateway with a provider registry and capability metadata. Prioritize:

- Local OpenAI-compatible endpoints (e.g. llama.cpp server, LM Studio, and other compatible inference servers).
- A generic custom OpenAI-compatible endpoint, allowing users to supply URL, model ID, and secret reference.
- Native adapters for important provider APIs only when the current official SDK/docs and licensing permit it.
- A plugin interface for other providers; avoid hard-coding assumptions about model names or response formats.
- Optional Hugging Face/local-model integrations when their runtime requirements are satisfied.

The LLM is used for research assistance, workflow drafting, literature/metadata summarization, and controlled tool selection. The LLM is **not** a substitute for validated scientific methods. For model output intended for execution, validate it against a strict schema and policy, show the proposed workflow, and require user approval before any consequential or external action.

Store provider secrets using environment variables, OS credential storage, or a supported secret manager. A UI may store a secret reference or whether a provider is configured, but must not expose the secret again in plaintext. Never include API keys in browser local storage, persistent app DB, telemetry, logs, prompts sent to a different provider, exception tracebacks, README, demo data, screenshots, or issue templates.

### 4.4 Scientific adapter contracts

Every scientific adapter must declare:

```json
{
  "id": "vendor-or-project:model-name",
  "display_name": "Human-readable name",
  "category": "chemistry|target_evidence|structure|docking|property|admet|simulation|reporting",
  "version": "explicit-version-or-unknown",
  "license": {
    "code": "SPDX-or-reviewed-expression",
    "weights": "SPDX-or-reviewed-expression-or-unknown",
    "data": "SPDX-or-reviewed-expression-or-unknown"
  },
  "capabilities": ["..."],
  "device_providers": ["cpu"],
  "network_required": false,
  "resource_profile": {"ram_mb_min": null, "vram_mb_min": null},
  "status": "needs_install",
  "citation_url": "https://...",
  "documentation_url": "https://..."
}
```

This is a conceptual schema: implement and version a proper Pydantic/JSON Schema definition, validate it, and add contract tests. Unknown license or hardware details must be marked unknown rather than guessed. Model weights and datasets need license review separate from code.

Adapter interfaces should include `probe()`, `validate_inputs()`, `estimate_resources()`, `run()`, `validate_outputs()`, `cancel()` where supported, and `version_info()`. All expensive execution should run out of the web request process. Use safe subprocess management where engines are external executables.

---

## 5. Workflow capabilities and scientific correctness

The full drug-discovery process is too broad for a first release to claim completeness. Implement a useful, tested vertical slice first, then add adapters and workflows as optional capabilities. Each workflow page must state which stages are implemented, which are optional, and which are not yet supported.

### 5.1 Recommended workflow stages

**A. Research target / evidence exploration**
- Search local projects and, when requested, connect to documented sources such as Open Targets, UniProt, PDB, ChEMBL, and PubChem.
- Preserve exact source identifiers, retrieval timestamps, source release/version if available, URLs, and evidence metadata.
- Rate-limit external calls, implement timeouts/retries for transient errors, use cached responses with visible timestamps, and offer an offline-only mode.
- Distinguish direct evidence, inferred evidence, model prediction, and user annotation.

**B. Import and curate molecular libraries**
- Support SMILES/SDF/MOL/MOL2 where the selected parser supports them, and CSV with a user-mapped structure column.
- Preserve original row ID and source. Report malformed rows instead of dropping them silently.
- Canonicalize with explicit salt, tautomer, charge, stereochemistry, and duplicate policies. Keep original string plus normalized representation and transformations.
- Compute validation stats, duplicates, missingness, parse failures, invalid valence, unsupported elements, and excessive structures.
- Ensure large uploads have size/record limits and stream parsing where appropriate.

**C. Low-cost triage**
- RDKit descriptors/fingerprints and configurable, documented physicochemical filters.
- Never label a heuristic threshold as a universal medicinal-chemistry law. Make criteria visible, editable, and exportable.
- Optional substructure/similarity searches with clear fingerprint and similarity metric metadata.

**D. Property and ADMET prediction**
- Adapter-based property prediction, such as Chemprop and independently licensed validated models.
- Show endpoint name, units, training-data provenance if known, evaluation metrics if published/reproduced, applicability-domain note if supported, and uncertainty where supported.
- Never merge outputs from different units/endpoints without validated mapping.
- Separate predicted toxicity flags from real experimental toxicology.

**E. Structure preparation and docking**
- Validate protein/ligand inputs, atom counts, chain/residue selection, protonation assumptions, cofactors/metals, box dimensions, missing atoms, and charge preparation.
- Provide AutoDock Vina as an optional CPU baseline once integration and packaging tests pass; GNINA and DiffDock are separate adapters with their own requirements.
- Record all parameters, receptor and ligand hashes, engine version, scoring function, search-space configuration, and warnings.
- Score/pose errors must fail visibly. Never replace a failed result with zero or a made-up score.
- Explain that scores from different engines/functions are not directly interchangeable unless a validated normalization protocol exists.

**F. Structure and interaction prediction**
- Optional Boltz and Chai integrations after license, hardware, and reproducibility checks.
- Keep prediction confidence fields separate from empirical assay evidence. Preserve input sequence and molecular component provenance.
- Large weights are downloaded explicitly by the user or an approved script into a cache, not committed to Git. Verify checksums where provided and record accepted license/terms.

**G. Molecular dynamics / simulation**
- Optional OpenMM integration, with CPU baseline where feasible and platform-specific performance profiles.
- Simulations require explicit system preparation choices, force-field and solvent/ion assumptions, time steps, seeds, equilibration/protocol, and termination criteria.
- Avoid presenting a brief simulation as a validated binding-affinity measurement. Validate input structures and energy/trajectory sanity checks.

**H. Multi-objective prioritization**
- Support Pareto front plots, diversity selection, transparent composite weights, filter reasons, and side-by-side model disagreements.
- Do not make a single “best molecule” badge without showing criteria and caveats.
- Preserve candidates rejected at each stage and the explicit reason.

**I. Reporting / export**
- Export CSV/Parquet where appropriate, SDF, JSON workflow/run manifests, HTML and Markdown reports, plots, and provenance summaries.
- All report content should be reproducible from run artifacts; include software/model versions and a timestamp.
- Do not embed private API keys, user secrets, absolute sensitive filesystem paths, or large hidden payloads into reports.

### 5.2 Safe initial vertical slice

Release 0.x development must first make this slice robust before attempting broad model integration:

1. Create/open a project.
2. Import a small CSV/SMILES dataset and/or use a tiny redistributable example.
3. Validate/canonicalize supported molecules with RDKit.
4. Compute deterministic descriptors and fingerprints.
5. Filter and rank using clearly described, user-configurable criteria.
6. Save a versioned workflow and its run.
7. Watch progress and logs live in UI and CLI.
8. Open compound details including a valid 2D depiction and provenance.
9. Export a report and all result rows, including rejected rows with reasons.
10. Re-run from the same manifest and verify stable deterministic outputs within defined tolerances.

Then integrate one real docking adapter and one real model-provider adapter with separately marked optional prerequisites. The app must never simulate the completion of a missing engine.

### 5.3 Reproducibility rules

- Fix and record random seeds when supported. Document any known nondeterminism in GPU/reduction algorithms.
- Record software version, resolved dependency lock, data release/record IDs, model weights hash, device/backend, precision/quantization, configuration, and hardware/driver details when relevant.
- Use frozen or checksum-identified datasets for scientific benchmark tests. Network-fetched “latest” data must not silently change golden outputs.
- Separate unit tests from scientific benchmarks. A unit test proves software behavior; it does not prove predictive validity.
- Use group/scaffold/time-aware dataset splitting where appropriate to prevent leakage. Never report a random split as proof of out-of-distribution generalization.
- Store measurement units, assay context, censoring, and source IDs. Do not treat data missingness as zero or use a predicted value as ground truth.
- Version transformations. If canonicalization changes stereo, salts, tautomers, or charges, preserve enough source information to explain it.

---

## 6. User interface and UX specification

The application should feel like a polished scientific desktop workspace in the browser: high information density, but calm, consistent and understandable. Do not implement an uninspired generic dashboard with a sidebar, a few cards, and nonfunctional charts.

### 6.1 Visual direction

- HCS identity: original, minimal molecular-node/graph motif; “Made with ❤️ by hcsmedia” in footer/About.
- Dark mode and light mode, with dark as the initial research-workspace option if it passes contrast tests. Include a real theme toggle and persist the preference locally.
- Use design tokens for backgrounds, surfaces, borders, focus rings, scientific chart palettes, spacing, type scale, radii, elevation, and motion.
- Avoid neon gradients everywhere, glass effects that reduce readability, oversized decorative empty space, and gratuitous animation. A restrained polished aesthetic is more useful for long scientific sessions.
- Maintain high contrast and never rely on color alone for status. Add icons/text/shape patterns and textual labels.
- Use a deliberate type hierarchy, legible monospaced treatment for identifiers/SMILES/logs, and tabular numerals for metrics.
- Use small, purposeful animations for job-state changes, workflow transitions, chart hover and loading skeletons. Respect `prefers-reduced-motion`.
- All interactive states must be designed: initial, loading, empty, validation error, API error, offline mode, no provider configured, dependency missing, job running, cancellation requested, cancelled, success, partial success, and retry.

### 6.2 Core navigation and screens

1. **Home / Workspace:** recent projects, recently run workflows, resource status, provider status, quick actions, and a meaningful empty state that guides a first run.
2. **Project overview:** project metadata, targets, datasets, compound collections, runs, artifacts, activity timeline, and source/provenance links.
3. **Target Explorer:** target search and aliases, gene/protein details, organism, evidence sources, structure availability, and transparent target–disease evidence summary.
4. **Compound Library:** table with search, filter, sort, saved views, column chooser, bulk actions, import errors, pagination/virtualization, and export. Large datasets must not render every row into the DOM at once.
5. **Compound detail:** 2D structure, identifiers, descriptors, stereochemistry, source records, predictions, assay measurements, docking poses if available, history, and warnings. Do not invent missing properties.
6. **Workflow Builder:** node palette, typed connections, validation panel, parameter editing, per-node resource estimates, workflow version, save/duplicate/import/export, and a readable run preview. Keyboard alternatives are required to canvas drag-and-drop.
7. **Run Monitor:** live DAG states, queue position, progress events, CPU/RAM and GPU/provider telemetry when available, elapsed time, logs, node input/output summaries, retry/cancel controls, and artifact browser. Never display fake telemetry.
8. **Results & Prioritization:** sortable predictions, filter reasons, uncertainty/evidence, multi-objective scatter/Pareto charts, diversity, score explanations, and comparison across runs/models.
9. **Molecule / Structure Viewer:** safe 2D depiction plus 3D structure viewer when a valid structure is available. Handle loading failures, unsupported atom types, and large structures. Provide an accessible textual alternative with identifiers and key metadata.
10. **AI Research Assistant:** provider selection, current model/capabilities, privacy and network status, structured research help, citations/evidence references, proposed actions, and a preview/approval step before execution. It must say when it does not know or cannot access a source.
11. **Model & Provider Registry:** provider connectivity status, local/remote badge, supported capabilities, backend/device, license summary, requirements, resource estimate, installation guide, and test button.
12. **Data Sources:** configurable connectors, local cache state, last refresh time, rate-limit/error states, license/attribution notes, and clear opt-in for network access.
13. **Reports & Exports:** templates, selected outputs, reproducibility manifest, warnings, data license/citation inclusion, generated report history.
14. **Settings:** workspace path, CPU/thread limits, memory budget, backend selection, cache, file size limits, local-only policy, network consent, secrets/provider configuration, logs, retention, and diagnostics.
15. **Help / About:** version, install health, enabled features, known limitations, citations, license, acknowledgements, and hcsmedia credit.

### 6.3 UI behavior requirements

- Every visible control must be functional. If a feature is not implemented, do not render a button pretending it works; label it clearly as unavailable/experimental or omit it.
- Use confirm dialogs for destructive operations (delete project/dataset, clear cache, cancel important work). Give the user a clear impact summary.
- Make table state URL-shareable where practical, excluding sensitive/private query parameters.
- Use proper loading skeletons, not endless spinners. Every loading state should have a timeout/error path where sensible.
- Add undo for low-risk reversible actions where feasible. Do not advertise undo if no undo record exists.
- Support keyboard navigation, visible focus, correct accessible names, focus restoration after dialogs, and screen-reader-friendly status updates.
- Target WCAG 2.2 AA where applicable; test contrast, keyboard-only workflows, focus order, zoom/resizing, and reduced motion.
- Responsive layout should remain usable on ordinary laptop widths. For large scientific canvases on small screens, provide a list/inspector alternative rather than hiding controls.
- Surface units, score direction, method and version wherever results appear. A column labelled “Affinity” must say what the value actually represents, its unit, and method.
- Tooltips should explain jargon concisely; do not make critical information available only through hover.
- Handle very long SMILES, model names, identifiers, and log lines without breaking layout. Provide copy/download actions with obvious feedback.
- Do not store sensitive scientific files in analytics or third-party frontend telemetry. Default to no third-party usage analytics.

### 6.4 Accessibility and visual QA

Test at common desktop widths and one narrow/mobile width. Capture actual screenshots of implemented pages using Playwright only after the app is running. Inspect screenshots for clipping, overflow, inconsistent spacing, low contrast, misleading labels, broken visualizations, and empty states. Real screenshots can be included in the README; never fabricate UI screenshots or badges.

---

## 7. Headless CLI, API, and external automation

The CLI is a first-class product, not an internal script. Choose a stable executable name, proposed `hcs-discovery`, and implement helpful `--help` output for all subcommands. Every command should return meaningful exit codes and structured machine-readable output where requested.

### 7.1 Proposed CLI surface

Implement a coherent set of commands, adjusting exact syntax as needed but preserving the following capabilities:

```text
hcs-discovery doctor [--json] [--check-vulkan] [--check-providers]
hcs-discovery serve [--host 127.0.0.1] [--port 8787]
hcs-discovery worker [--concurrency N]
hcs-discovery project list
hcs-discovery project create --name "Example Project"
hcs-discovery dataset import <file> --project <project-id> --format auto
hcs-discovery compounds validate <file> [--format auto] [--output <path>]
hcs-discovery models list [--json]
hcs-discovery models inspect <adapter-id>
hcs-discovery workflow list
hcs-discovery workflow validate <workflow.yaml>
hcs-discovery workflow run <workflow.yaml> --project <project-id> [--json]
hcs-discovery run status <run-id> [--json]
hcs-discovery run logs <run-id> [--follow]
hcs-discovery run cancel <run-id>
hcs-discovery run artifacts <run-id> [--output <directory>]
hcs-discovery report export <run-id> --format html|markdown|json|csv --output <path>
hcs-discovery config show [--redact-secrets]
hcs-discovery cache status|clear [--dry-run]
```

Requirements:
- `--json` output is stable, versioned, and written to stdout; human logs go to stderr in JSON mode.
- `run status`, `run logs --follow`, cancellation, and export must work without an interactive terminal.
- Exit codes distinguish validation failure, missing dependency/provider, job failure, cancellation, and unexpected error.
- Do not leak tracebacks or paths that contain secrets by default. Add a debug mode for sanitized detail.
- Long tasks should print run ID immediately, then allow polling/follow mode. Support Ctrl+C without corrupting job state.
- Avoid launching a browser unless the user explicitly requests it.
- `doctor` output must not reveal secret values. It may say “configured” / “missing” and test connectivity only when the user opts in.
- The CLI must share the same service/application layer as the UI; do not implement a separate scientific pipeline that produces different results.

### 7.2 API contract

- Version all public routes under `/api/v1`.
- Provide OpenAPI JSON and API docs when enabled. Document local default binding and safe deployment settings.
- Use typed request/response schemas, size/range constraints, pagination, request IDs, consistent error structures, and explicit validation errors.
- At minimum support projects, targets, compounds, datasets, model registry, workflow validation/creation, run submission/status/events/cancel, artifacts, reports, health/readiness, and diagnostics.
- Use Server-Sent Events or WebSockets for run event streaming; select the simpler robust solution and keep reconnect/resume behavior documented. Polling remains a fallback.
- Restrict CORS to configured origins. Bind local development to loopback by default, not `0.0.0.0`, unless an explicit setting says otherwise.
- Add authentication and authorization for remote/multi-user deployment before exposing it publicly. Do not rely on “it is only an internal tool.”
- Rate-limit expensive API routes and file uploads in remote mode.
- Treat workflow imports as untrusted. Validate schema, paths, adapter IDs, resource limits, and policy before queuing.

### 7.3 Example automation

Include a working, tested script example that submits a workflow, waits for completion, exports outputs, and returns nonzero on failure. Also include a CI example running the deterministic fixture workflow without remote model keys. Document how to connect a local OpenAI-compatible LLM server without making network use mandatory.

---

## 8. Data sources, file safety, and provenance

### 8.1 Data connector design

Use a generic connector interface with `search`, `fetch`, `normalize`, `source_metadata`, `license_metadata`, `health_check`, and rate-limit/retry behavior where supported. Separate connector-specific responses from the canonical internal schema. Store source IDs and raw response checksums when licensing permits. Make connector refresh explicit rather than silently overwriting imported data.

Start with only a small number of reliable connectors and implement their failure paths completely. Candidate integrations include ChEMBL, PubChem, PDB, UniProt, and Open Targets. Each connector must have:
- Documented request/response schemas and a version/source link.
- Timeout and network failure handling.
- Retry with exponential backoff and jitter only for retryable failures.
- Rate limiting and cache policy.
- Pagination/large-result protection.
- Provenance, license and attribution metadata.
- Tests against saved, redistributable fixtures; live smoke tests are optional and explicitly marked.
- An offline mode that refuses hidden network calls.

### 8.2 File and archive safety

- Enforce upload and expanded archive size limits; guard against zip bombs.
- Prevent path traversal, symlink escape, arbitrary absolute paths, and overwrite outside a configured workspace.
- Use safe filename generation and normalized internal relative paths.
- Treat PDB/mmCIF, SDF, MOL2, CSV, JSON, YAML, and archive inputs as untrusted and potentially malformed. Parse with appropriate libraries and resource/time limits.
- Avoid shell interpolation. Use subprocess argument arrays and controlled working directories.
- Do not automatically execute scripts or embedded commands found in uploaded files, workflow bundles, model repositories, or archives.
- Reject unreasonable row counts, atom counts, nesting depth, payload sizes, or string lengths with clear messages.
- Keep original source bytes only when needed and permitted; otherwise preserve checksum and canonicalized output with transformation log.

### 8.3 Data quality and units

- Make unit conversion explicit and tested; never compare `nM` with `µM` without conversion.
- Preserve relation operators and censoring (`<`, `>`, approximate) as structured fields.
- Do not join by display name when a stable identifier is available.
- Disambiguate species, isoforms, chains, biological assemblies, and salts/stereoisomers.
- Make duplicate resolution policies visible and reversible.
- Report missingness and parse errors; never silently drop records.
- Every downloaded record should retain the source URL/accession, retrieval timestamp, license/terms status, and version where available.

---

## 9. Responsible use, privacy, and security

This is software for legitimate therapeutic and biomedical research. Its default configuration should not facilitate harmful biological or chemical activity. Implement a documented, reviewable policy layer that can block or require human review for workflows aimed at creating or optimizing biological agents, toxins, high-consequence toxic compounds, controlled-substance abuse, evasion of safety controls, or other clearly harmful applications. Do not implement policy bypasses, hidden “uncensored” modes, or tool instructions that circumvent those controls. General toxicology prediction and safety assessment may be legitimate research functions; evaluate intent/context and use policy carefully rather than indiscriminately blocking all toxicity work.

### 9.1 LLM/tool sandbox

- LLMs must not execute arbitrary shell commands, write anywhere on the filesystem, change settings, access secrets, or send data externally merely because a prompt asks them to.
- Expose a limited typed tool registry; validate every argument, enforce permissions and resource limits, log the approved action, and require explicit approval for external data transmission or destructive operations.
- Treat retrieved text, PDFs, web pages, model cards, issue text, and structure metadata as untrusted content; prompt injection must not override policy or system-level tool constraints.
- Separate “propose workflow” from “execute workflow.” Show a readable diff/preview of workflow nodes, providers, network transfers, and resource limits before execution.
- Never put confidential files into a hosted LLM context without explicit informed consent. Show which provider will receive the data, which fields/files are included, and how to choose local-only mode.

### 9.2 Credentials and secrets

- Commit `.env.example` with names and placeholder values only. `.env`, provider tokens, SSH keys, local credentials, certificates, signed URLs, and personal configuration must be excluded from Git.
- Prefer `gh auth login`/the established GitHub CLI authentication flow for repository operations. Check the authenticated identity before making changes. Do not print the auth token.
- Use GitHub Actions `GITHUB_TOKEN` with least-privilege permissions. Pin third-party Actions to full commit SHAs; comment the upstream version/tag for readability.
- Prefer short-lived OIDC authentication for compatible deployments over long-lived cloud secrets. Do not set up a cloud deploy that was not explicitly requested/approved.
- Use secret scanning and push protection if available; add local secret scanning in CI (e.g. a maintained scanner) and fail the build on confirmed credential leaks.
- If a real secret is accidentally written to a file, output, prompt, issue, or commit, stop, remove the exposure, and advise the owner to rotate it. Rewriting Git history may be needed; never assume deleting the latest file is sufficient.
- Never request or place raw credentials in `GEMINI.md`, source code, examples, test snapshots, logs, crash reports, or README.

### 9.3 Network/privacy controls

- Local-first mode must have visible, testable semantics. A “local-only” switch should block remote model calls and data connectors, not merely hide buttons.
- Emit a network audit event when a workflow is configured to send data to an external provider; include destination/provider and data categories, not raw secret/content.
- Do not collect scientific inputs or prompts in analytics by default.
- Remote deployment needs HTTPS termination, authentication, authorization, upload protection, CORS policy, rate limits, secure cookie/token handling, secure headers, and clear threat-model documentation.
- Use CSRF protections as appropriate for cookie-authenticated actions; avoid storing long-lived bearer tokens in browser local storage.
- Limit model/adapter processes and external binaries using least privilege and appropriate OS isolation where feasible.
- Ensure errors don't expose keys, private paths, raw request bodies, unredacted provider payloads, or sensitive scientific data.

### 9.4 Threat model

Create `docs/security/THREAT_MODEL.md` listing assets, trust boundaries, attackers, mitigations, and residual risks. Include at least: malicious uploaded chemistry/structure file, malformed archive, compromised dependency, malicious plug-in/model, prompt injection, leaked API key, unauthorized remote API client, path traversal, local privilege misuse, denial-of-service through large workloads, scientific result tampering, dependency supply-chain compromise, and license/data provenance errors.

---

## 10. Testing strategy: correctness before confidence

Build a layered testing pyramid. No one suite is enough. Use synthetic, benign fixtures that are small and redistributable. Avoid downloading multi-gigabyte weights in standard CI. Mark GPU/large-model/live-network tests clearly; they must never masquerade as passing when skipped.

### 10.1 Test layers

**Layer 1 — Static quality**
- Python formatting/lint/type checks selected for the repository (`ruff`, `mypy` or `pyright` as justified).
- Frontend formatting, ESLint/TypeScript typecheck, build.
- Dependency lock consistency.
- Markdown links, code blocks, YAML/JSON schemas, OpenAPI generation checks where practical.

**Layer 2 — Unit tests**
- All core domain schemas and validation rules.
- Canonicalization and descriptor calculation with deterministic fixtures.
- Units, censored values, null/NaN/infinity handling.
- Workflow graph validation, cycles, invalid references, incompatible node ports, config validation and deterministic hashing.
- Queue state machine, retry/timeout/cancel logic, lease expiration and duplicate submissions.
- Cache key correctness and invalidation.
- Secret redaction, path validation, filenames, safe export locations, policy decisions.
- CLI parsing, output JSON schema, exit codes.
- UI pure logic, provider state, error/empty/loading states, schema validation and query serialization.

**Layer 3 — Contract tests**
- One contract suite per adapter/provider.
- Test missing dependency, supported dependency, unsupported backend, bad input, engine crash, timeout, cancellation if supported, malformed output, version detection, and resource estimate.
- Use fake providers for deterministic CI; ensure test names and reports state that they are fakes.
- Verify an adapter cannot claim Vulkan when its real probe fails.

**Layer 4 — Integration tests**
- Create project → import fixture → run workflow → persist results → retrieve status/logs → export report → load exported result.
- Migrations from clean DB and the previous supported schema version.
- Both SQLite and PostgreSQL where configured; test transaction rollback and concurrent job claiming.
- API + worker lifecycle and app restart while jobs are queued/running.
- Offline mode proving no outbound network calls occur in the deterministic core suite (patch/guard network client constructors or use an isolated test environment).

**Layer 5 — End-to-end UI tests**
- First-time onboarding and health screen.
- Create a project and import a sample dataset.
- See row-level validation errors.
- Build/validate/run the deterministic workflow.
- Watch status/events/logs update, cancel a long-running fixture, and see the correct final status.
- Inspect compound details, sort/filter a result table, compare outputs, export a report.
- Provider missing/unavailable states and local-only mode.
- Keyboard-only navigation for core paths, focus traps, responsive layout, and accessible status announcements.
- No console errors, broken routes, or dead controls in core flows.

**Layer 6 — Scientific validation and benchmarks**
- Keep scientific benchmarks separate from ordinary CI. Pin datasets, source versions, task definitions, preprocessing, data splits, metrics, software/model versions, seeds, hardware and tolerances.
- Reproduce baseline results where feasible; otherwise report the exact method and do not claim reproduction.
- Use appropriate metrics (e.g. MAE/RMSE for continuous endpoints, AUROC/AUPRC and calibration metrics for classification, docking pose RMSD/top-k recovery only with a suitable reference set). Choose metrics to match the question; don't report only the most favorable metric.
- Prevent data leakage using scaffold, temporal, target/cluster or other suitable splits. Report dataset leakage risks and limitations.
- For measured endpoints, compare like with like: same assay type, units, organism, conditions, and target definition where possible.
- Use confidence intervals/bootstrap where meaningful; report sample counts, missingness, and exclusions.
- Use a small test fixture for pipeline validity, not to claim predictive excellence.

**Layer 7 — Security and robustness**
- Dependency audit and license audit.
- Secret scanning, static analysis, unsafe subprocess/path audits.
- Property-based tests (Hypothesis or equivalent) on SMILES, CSV, structures, workflow JSON/YAML, and API payloads.
- Fuzz parser boundaries if practical; cap compute/time and run fuzzing in isolation.
- API rate/size-limit tests and remote-auth authorization tests.
- Archive/path traversal/zip-bomb fixtures.
- Malicious prompt-injection fixtures in retrieved text and model outputs.
- Ensure errors are redacted and don't leak secrets.

**Layer 8 — Performance, endurance and recovery**
- Large-but-bounded compound library performance (choose realistic configurable targets and document hardware).
- UI rendering with thousands of rows using virtualization.
- Concurrent job submissions, queue fairness, worker crash/restart, lease recovery, repeated cancellation, timeouts, DB locks, slow disk, full disk, and cache pressure.
- Long-running resource monitoring: RAM growth, file handles, orphan processes, temporary file cleanup.
- Backend benchmark with warm-up and repeated runs; record median and p95 latency, throughput, peak RSS and device memory if measurable.
- Avoid brittle absolute speed thresholds in heterogeneous CI; use correctness and regression bands, and document the benchmark machine.

### 10.2 Mandatory edge-case matrix

Test, at minimum:

**Input/data edge cases**
- Empty file, header-only CSV, empty dataset, duplicate headers, missing SMILES column, whitespace-only SMILES, invalid SMILES, unusual atom/charge/stereo representation, salts, multi-component structures, isotopes, unsupported elements, malformed SDF block, truncated MOL2, huge structure, invalid Unicode, unusual filenames, non-ASCII/emoji directory paths, Windows drive letters, path separators and reserved names.
- CSV with quotes/newlines/commas in fields, delimiter mismatch, malformed quoting, duplicate IDs, huge cell values, null/NaN/Infinity, negative values where invalid, impossible units, censored observations, and mixed data types.
- PDB/mmCIF with missing chains/residues, altlocs, unusual residue names, multiple models, missing atoms, absent ligand, invalid coordinates, NaN coordinate values, metals/cofactors, oversized structure, and valid-but-unusual biological assemblies.
- Corrupted/downloaded model files, wrong checksum, missing metadata, insufficient disk, permission denied, partial download, interrupted extraction, and updated upstream schema.

**Workflow/job edge cases**
- Empty graph, cyclic graph, disconnected nodes, invalid port types, missing input, unknown plugin, changed plugin version, duplicate submission, node failure, transient network failure, non-retryable scientific validation failure, timeout, cancellation before start, cancellation during execution, cancellation after completion, worker killed mid-node, lease expiry, app restart, stale events, malformed engine output and partial artifacts.
- Same workflow with different normalized inputs must not collide in cache. Same workflow with changed model version/config/seed/backend must invalidate the cache as appropriate.
- Job finish event must be emitted once per actual state transition; clients reconnecting to event streams must recover state rather than assume no missed events.

**Model/provider edge cases**
- No model installed, model id unknown, local server unavailable, remote API key missing/expired, HTTP 429, 5xx, timeout, malformed JSON, streaming chunks out of order, unsupported tools, content filter, empty answer, truncated answer, model hallucinated adapter name, invalid tool arguments, model returns NaN/Inf or invalid units, and endpoint advertises a capability it cannot actually use.
- Vulkan device absent, Vulkan runtime missing, driver mismatch, unsupported model operation, failed model loading, memory allocation failure, mixed precision discrepancies, CPU fallback, CPU-only host, no network, and remote provider configured while local-only mode is active.

**API/security/UI edge cases**
- Unauthorized user, wrong project ownership, expired session/token, bad CORS origin, CSRF where relevant, oversized upload, path traversal, malformed/overdeep JSON, HTML/XSS payload in project metadata/logs, prompt-injected document, rate-limit exceeded, and concurrent edits.
- Browser refresh during a job, network disconnect/reconnect, long log lines, empty results, very long identifiers, narrow viewport, 200% zoom, screen-reader status, keyboard-only completion, reduced motion, and no support for a given viewer format.

**Filesystem/host edge cases**
- Windows paths with spaces/non-ASCII characters; Linux case sensitivity; read-only workspace; low disk; temp directory deletion; lock contention; stale PID file; process already running; port in use; missing native runtime; unsupported Python/Node version; file permissions; symlink/path escape.

### 10.3 Property-based and invariant testing

Write invariants such as:
- Every successfully parsed molecule has a valid internal identity record, or a row-level error explains why it does not.
- Normalization is deterministic for a pinned RDKit version and defined settings.
- Invalid inputs never become successful zero-valued predictions.
- Every reported prediction links to a method/version and input provenance.
- All workflow nodes end in a terminal state or remain visibly active/blocked; no orphaned jobs disappear silently.
- Cache reuse is impossible when required cache-key fields differ.
- Cancelled work is not displayed as successful.
- A `local-only` run never calls remote providers/connectors.
- Secret redaction runs on every outward-facing log/error/report path.
- Exported files stay inside the configured destination and match their recorded checksum.

### 10.4 Test commands and reporting

Create a single root-level task interface, e.g. `uv run pytest`, `uv run ruff check .`, `uv run mypy src`, `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm build`, and `pnpm playwright test`, or consolidate via a root task runner. Pick actual commands based on the implementation and keep them documented. CI must run the authoritative commands, not a different reduced set.

Produce machine-readable JUnit/coverage/build artifacts where supported. Enforce a rational coverage floor for core code and critical security/path/policy logic. Do not inflate coverage with meaningless tests. Every skipped optional test must report a reason and must not be represented as passing. Core local and remote-build tests cannot be silently skipped.

---

## 11. Local development and installation experience

### 11.1 The clean-machine contract

A new user should be able to clone the repo, follow a short quick start, install the required base dependencies, run migrations, start backend/worker/frontend, and execute the sample workflow without secrets or a GPU. The docs should not assume an IDE, administrator privileges, Docker, CUDA, or an existing database server.

- Prefer `uv` for Python environment and lockfile management; verify support for Windows and Linux in CI.
- Choose a supported Node.js LTS and pin/use the version file as appropriate. Use one JS package manager and commit its lockfile.
- Provide cross-platform setup instructions. If helper scripts are provided, include PowerShell and POSIX shell variants or use a cross-platform Python task script.
- Keep system requirements explicit: core versus optional scientific extras, supported OS/Python/Node versions, expected storage/RAM, network needs, model weight size where known, and backend support status.
- Ensure paths and commands work with spaces and non-ASCII characters.
- Provide a `doctor` command that diagnoses missing optional dependencies without causing import-time crashes.
- Do not download large models implicitly during installation or first start. Let the user choose which models/weights to download after seeing size, license, storage requirements, and network destination.

### 11.2 Developer quality of life

- Clear startup command(s), sensible ports, readable structured logs, and one local data directory.
- Hot reload for the frontend and backend where practical.
- Document how to run API only, worker only, UI only, tests only, and the full stack.
- Create a reproducible sample dataset/workflow with known expected results and no secrets.
- Include `.env.example`; validate configuration at startup and fail with an actionable error message.
- Provide `reset-demo` or equivalent only if safe, and require explicit confirmation before removing user data.
- Use Alembic migrations with an automated clean-upgrade test. Never silently drop/overwrite user tables during normal startup.
- Support graceful shutdown and worker cleanup.

---

## 12. GitHub repository, workflow and supply-chain requirements

Do not create/push to GitHub until the local bootstrap and core quality checks have passed. Use the authorized GitHub account and make no assumptions about the username or existing repositories.

### 12.1 Before creating the remote repository

1. Check `git status`, current directory, remotes, branches and existing history. Do not accidentally push into an unrelated or already-configured repository.
2. Check GitHub CLI availability and authentication state without showing tokens. Use the authenticated user identity (e.g. via `gh api user`) and verify that this is the intended owner.
3. Check whether `hcs-discovery-studio` already exists under that account. If it exists, stop before overwriting; inspect it and ask for an explicit choice or use a genuinely new slug. Do not delete or replace a repository.
4. Create a **public** repository because the requested project is open source, unless the owner/account settings prevent this or the user explicitly changes the visibility. Do not add an initial README/license on GitHub if doing so would create an unrelated history that conflicts with the verified local history.
5. Set the origin URL, inspect it, and confirm the owner/repository before pushing.
6. Use conventional commits with concise, factual messages; no false claims such as `all tests passed` unless that is supported by the current run.

### 12.2 Git hygiene

- `.gitignore`: `.env*` except `.env.example`, secrets, private keys/certificates, OS/IDE files, `.venv`, node_modules, builds, caches, local DB/data, model weights, checkpoints, generated exports, benchmark artifacts unless intentionally versioned, logs, and temporary files.
- Ensure `git check-ignore` covers likely secret/model/data paths. Add pre-commit secret scanning where feasible.
- Do not put user data, actual scientific datasets requiring restricted terms, model weights, or binaries into Git history. GitHub warns for files above 50 MiB and blocks regular Git files above 100 MiB; use release assets or Git LFS only where appropriate. Prefer not to use Git LFS for model weights when a dedicated model artifact/cache approach is better.
- Add `LICENSE`, `NOTICE`, `CITATION.cff`, contribution guide, code of conduct, security policy, and responsible-use statement.
- Ensure all third-party assets and model/dataset downloads have an explicit provenance/license record. Do not assume a code repository's license also covers its weights or training data.
- Run `git diff --check`, scan staged files for secrets, inspect large files, verify no generated local data was staged, and inspect the complete diff before commit/push.

### 12.3 GitHub Actions security

- Use least-privilege `permissions` at workflow and job level; set `contents: read` by default and grant write permissions only to the specific release/publish job that needs them.
- Pin third-party Actions to full commit SHAs; comment the matching release tag. Review action maintainers and permissions before adoption.
- Use a supported secret scanner, dependency review, CodeQL or equivalent static analysis, and Dependabot/Renovate for dependency updates. Configure workflows to fail on actionable high-severity issues or document an exception with rationale/owner and expiration.
- Never echo secrets or print entire environment variables. Avoid `set -x` in secret-handling scripts. Masking is not a substitute for avoiding disclosure.
- Use separate jobs for tests and release/publish; release jobs must depend on successful tests and must not run on arbitrary untrusted pull-request code with write secrets.
- Use OIDC for a compatible deployment or registry rather than adding long-lived credentials whenever the provider supports it.
- Add artifact attestations/signing where supported by the repository plan and release workflow; if a feature is plan-limited, document it and do not claim the artifact is attested when it is not.
- Generate an SBOM for release artifacts if practical; attach or publish it with the release. Include dependency versions and image digest.
- Pin container base images by digest when practical and update them through a reviewed process. Run containers as non-root, use a small runtime image, avoid shipping compilers/build tools in the runtime layer, and run image vulnerability scanning where practical.

### 12.4 Minimum CI matrix

Set up separate, understandable workflows or a single well-structured matrix for:

- Backend lint/typecheck/unit tests on supported Windows and Linux versions where packages permit.
- Core integration tests and migrations on SQLite; PostgreSQL job where appropriate.
- Frontend lint/typecheck/unit tests/build.
- Playwright core e2e on a supported Linux runner, with trace/screenshot artifacts on failure.
- Adapter contract tests using deterministic fixtures/fakes.
- License and dependency checks, secret scanning, CodeQL/static analysis.
- Container build on PR/push if Docker support is implemented.
- Release workflow triggered by a verified tag only, depending on all required checks, to build artifacts, publish release notes/SBOM/attestations where available, and publish a GHCR image if that is a supported, verified part of the build.

CI must not need a paid external AI API or download multi-gigabyte model weights. Live API checks are separate optional/manual workflows with explicit secrets and no secret logging.

### 12.5 Cloud/release build path

The minimum cloud milestone is a green GitHub Actions build/test from the pushed repository and a reproducible, tagged release build. If a container image is part of the implementation, build it in CI and publish it to GHCR only on the intended release trigger. Validate that the image starts and serves health endpoints; do not infer successful deployment from a successful image build.

Actual deployment to a cloud host is a separate, opt-in milestone. Never create paid compute, a paid database, or a public endpoint without explicit approval. Document storage, authentication, backup, migration, network egress, model-weight distribution, and costs before deployment.

---

## 13. README and documentation quality

The README is part of the product. Make it attractive, accurate, scannable, visual, accessible, and useful to both scientists and developers.

### 13.1 README layout

- Original HCS Discovery Studio banner/logo in SVG where possible; no copied protected logos.
- Product name and one-sentence value proposition.
- Real status badges only: CI, current release/version, license, Python/Node support, coverage only if it is generated from CI, and security checks only if actually enabled.
- “Made with ❤️ by hcsmedia” credit.
- A real application screenshot or short GIF generated from the working product, with meaningful alt text. Do not create fake screenshots for planned features.
- Concise feature list grouped into **Working now**, **Optional integrations**, **Experimental**, and **Planned**.
- Quick-start path for a fresh Windows/Linux user, then a no-secret CPU demo.
- Example CLI commands for `doctor`, importing a small dataset, validating/running workflow, watching a run, and exporting a report.
- UI screenshots for workflow builder, run monitor, compound library, molecule detail, and provider registry only once those screens actually work.
- Architecture and a Mermaid workflow diagram.
- Hardware/backend support matrix, including truthful CPU/Vulkan support and what is optional.
- Data sources and provenance policy.
- Test/benchmark methodology, how to reproduce results, and a report of known limitations.
- Security/responsible-use, privacy/local-only behavior, credential setup, contribution guide, code of conduct, citation, license and acknowledgements.
- Troubleshooting with real common errors and commands.

### 13.2 Required documents

- `docs/architecture/OVERVIEW.md`
- `docs/architecture/WORKFLOW_ENGINE.md`
- `docs/architecture/PLUGIN_API.md`
- `docs/architecture/DATA_MODEL.md`
- `docs/user-guide/INSTALL_WINDOWS.md`
- `docs/user-guide/INSTALL_LINUX.md`
- `docs/user-guide/QUICKSTART.md`
- `docs/user-guide/CLI.md`
- `docs/user-guide/WORKFLOWS.md`
- `docs/user-guide/LOCAL_MODELS.md`
- `docs/user-guide/SCIENTIFIC_LIMITATIONS.md`
- `docs/developer-guide/CONTRIBUTING.md`
- `docs/developer-guide/TESTING.md`
- `docs/research/COMPONENT_AND_LICENSE_AUDIT.md`
- `docs/scientific-validation/VALIDATION_PROTOCOL.md`
- `docs/security/THREAT_MODEL.md`
- `SECURITY.md`
- `CODE_OF_CONDUCT.md`
- `CONTRIBUTING.md`
- `CITATION.cff`
- `CHANGELOG.md`
- `NOTICE`

Documentation must match shipped behavior and exact commands. Run doc/code snippets where possible. Check links and spelling. Avoid broken badges, placeholder text, fake benchmark tables, unsupported “SOTA” claims, and dead links.

---

## 14. Benchmark and scientific evaluation plan

Create `docs/scientific-validation/VALIDATION_PROTOCOL.md` before making predictive accuracy claims. The goal is to make the platform's predictions inspectable and to ensure each adapter reports a well-defined method, not to claim that integrating more models automatically improves drug discovery.

### 14.1 Benchmark design

For each scientific task:
1. Define a specific question and output: e.g. parsing validity, pose generation, experimental affinity prediction, ADMET endpoint, or simulation stability. Do not conflate them.
2. Choose a suitable, publicly usable dataset and pin a named release/commit/download checksum. Record its license, attribution, and exclusions.
3. Define leakage-resistant splits appropriate to the task. For molecular-property tasks, use scaffold or time splits where justified; for target/structure tasks, account for sequence/structure similarity and train/test leakage.
4. Define preprocessing and unit rules up front. Preserve raw source values and the exclusions log.
5. Compare with a named baseline using identical split and input information when possible.
6. Choose metrics before running the experiment. Report metrics and confidence intervals, sample counts, runtime, memory, missingness, and hardware.
7. Repeat with fixed seeds where supported and document nondeterminism.
8. Separate development tuning from held-out evaluation. Never repeatedly tune against the test set and still call it independent.
9. Publish the exact benchmark script, manifest, environment, and result artifact (within data licensing limits).
10. Mark the result as `reproduced`, `partially reproduced`, `not comparable`, or `not reproduced`; explain why.

### 14.2 Scientific caveats in product UI

- Docking scores rank poses according to a scoring function; they are not direct proof of binding or experimental affinity.
- Structure prediction confidence is not a clinical-safety score or proof that an interaction occurs in biology.
- ADMET estimates inherit uncertainty and dataset bias; label individual endpoints and model provenance.
- A model's literature-reported benchmark score does not establish the score achieved in this particular integration or on the user's target distribution.
- Do not call a candidate “safe,” “effective,” “approved,” or “clinically validated” on the basis of computational predictions.
- Never present a recommendation without saying which criteria generated it.

---

## 15. Efficient autonomous development loops

Use a disciplined loop, not unstructured repeated coding. Continue until gates are green or a genuinely external blocker prevents progress. Do not stop just because the first implementation looks good.

### 15.1 The core loop

For each feature or failure:

1. **Observe:** inspect code, tests, CI logs, screenshots, API responses, and reproduction steps. Do not infer root cause from the symptom alone.
2. **Hypothesize:** state the likely root cause and alternate explanations in the agent log.
3. **Reproduce:** add or run the smallest failing test/command/screenshot that proves the issue.
4. **Plan:** choose a minimal maintainable fix that preserves public contracts and scientific meaning.
5. **Implement:** change code and tests together. Avoid unrelated refactors inside a bug fix.
6. **Verify targeted:** rerun the reproduction and relevant unit/contract tests.
7. **Verify adjacent:** run integration tests and type/lint checks for affected components.
8. **Audit:** review diff, security, error behavior, backwards compatibility, docs, and user-visible states.
9. **Record:** log the actual command and result; update the implementation checklist.
10. **Continue:** address the next failing gate. After a green suite, inspect the feature from a clean-user perspective rather than ending immediately.

### 15.2 When to escalate instead of looping blindly

If a test keeps failing after three materially different, evidence-based approaches, stop repeating near-identical changes. Inspect whether the failure is an environment/dependency/upstream issue, isolate a minimal repro, document the evidence and options, and continue on independent work. If a required external credential, account permission, model artifact, or device is unavailable, clearly mark the dependent gate blocked and perform all remaining work that does not depend on it. Never say “all tests passed” when a required check was blocked.

### 15.3 Regression prevention

- Add a regression test for every fixed bug where practical.
- After refactoring a public API, test CLI, API, UI, and workflow imports against it.
- Run dependency updates in isolated branches/changes, with lockfile and compatibility tests.
- Keep schemas and workflow versions explicit; provide migrations or validation errors for older definitions.
- Use feature flags only when they represent a meaningful optional or experimental capability. Remove stale flags before stable release.
- Maintain a known-limitations list and ensure README/UI agree with it.

---

## 16. Phase-by-phase implementation plan and release gates

Implement these phases in order unless a concrete dependency requires a change. Every phase has a gate. Do not move a broken foundation forward simply to make a checklist appear complete.

### Phase 0 — Workspace audit and product decisions

- Inspect current workspace, OS, Python/Node/Git, available disk, Vulkan tools/drivers, browser, package manager, and existing repository/credentials state without revealing secrets.
- Write architecture decision records for Python version, frontend stack, queue design, DB backends, provider contracts, dependency strategy, initial data formats, and license.
- Review the authoritative source links in Section 2 and create a component/license/hardware matrix.
- Inventory optional engines by exact install method and known CPU/GPU/provider restrictions.
- Establish nonfunctional requirements: local-only behavior, supported OS, job size limits, privacy defaults, CLI/API contracts, and what `v1.0.0` will and will not include.

**Gate 0:** architecture and component audit exist; no unjustified CUDA dependency; CPU base scope is realistic; initial repository layout and commands are agreed.

### Phase 1 — Repo skeleton, developer environment, and contracts

- Create project directories, Python package, frontend skeleton, lockfiles, formatting/lint/type tools, environment validation, structured logging, and initial CI.
- Define core schemas for projects/compounds/workflows/runs/artifacts/providers.
- Implement safe path/config helpers and a tested secret-redaction layer.
- Add health/readiness endpoints and CLI entry point with `--help` and `doctor`.
- Establish migration/test setup and a minimal automated build from clean checkout.

**Gate 1:** clean install, lint/type checks, core unit tests and front-end build pass on supported local OS plus CI baseline; there are no placeholder commands that falsely claim success.

### Phase 2 — Persistent domain model and workflow engine

- Implement database schema, migrations, repositories, run manifest, workflow graph schema, DAG validation, persistent job state, event model, worker loop, cancellation/timeouts/retry semantics, artifact storage, and content-addressed cache.
- Define idempotency and lease-recovery behavior.
- Add deterministic fake/test node types only in test/examples; test infrastructure must not register them as real scientific engines in production defaults.
- Implement run status/logging APIs and CLI watch/cancel/artifact commands.

**Gate 2:** integration test from a clean DB can submit a deterministic workflow, restart app/worker, recover valid state, cancel a run, export artifacts, and verify provenance/cache keys.

### Phase 3 — First working scientific vertical slice

- Integrate RDKit for compound parsing/canonicalization/descriptors/fingerprints/2D depiction if available and licensed.
- Implement CSV/SMILES/SDF importing with row-level errors and source provenance.
- Add a small, redistributable, benign example dataset.
- Implement rule-based filtering, transparent multi-objective ranking, result export and reproducibility manifests.
- Implement molecule and dataset detail views.

**Gate 3:** a clean user can run the end-to-end local demo without credentials, CUDA, or large weights. Actual output is verified against deterministic expected results. Malformed records are preserved as explicit row errors, not silently discarded.

### Phase 4 — Complete professional UI / UX

- Implement all core routes needed for the vertical slice: workspace, project, compound library, compound detail, workflow builder or at minimum a validated workflow editor, run monitor, results, provider registry, settings, help/about.
- Connect every action to real backend behavior. Remove nonfunctional buttons and fake charts.
- Add live job events, cancellation, logs, actual artifacts, search/filter/table virtualization, charts, responsive behavior, accessibility, empty/error states, and theme support.
- Generate genuine screenshots with Playwright and visually inspect them.

**Gate 4:** full core E2E path passes, all visible controls are functional, no console errors or critical accessibility/overflow problems remain, UI states are consistent with backend truth.

### Phase 5 — CLI/API parity, local AI gateway, and plugins

- Finish CLI headless workflows and public API endpoints.
- Implement generic local OpenAI-compatible LLM provider, provider discovery/health checks, streaming chat if supported, secret references, local-only enforcement, schema-constrained tool calls, and explicit approval for execution.
- Implement the adapter registry, model metadata, dependency checks, resource estimates, license metadata, and capability state reporting.
- Document plugin authoring and add adapter contract tests.

**Gate 5:** the same tested workflow can be launched and monitored from UI, CLI, and API. Local provider integration is tested against a deterministic stub and, when a local server is available, a marked live smoke test. No remote secrets are required for core CI.

### Phase 6 — First real scientific engine integrations

- Integrate AutoDock Vina as an optional CPU docking engine if packaging/version/license requirements pass the audit.
- Add an explicit structure-preparation and docking workflow with validated inputs, parameter metadata, scores/poses, warnings and provenance.
- Add only those optional adapters that are maintainable and can be accurately described: GNINA, DiffDock, Chemprop, OpenADMET-related models, Boltz-2, Chai-1, or OpenMM in separately scoped follow-up work.
- Keep every optional model in its own dependency group and test path. Do not make app startup depend on model imports.
- Run a small benign smoke fixture and benchmark, record observed hardware/backend behavior, and document limitations.

**Gate 6:** at least one real scientific engine executes locally through the platform without a fake backend; input/output validation, cancellation/error path where supported, provenance, and reproducibility tests pass. Other models may remain clearly optional if the hardware/license requirements make them unsuitable for the initial stable release.

### Phase 7 — Performance, resilience, and scientific validation

- Run concurrency, restart/recovery, low-memory, disk-full, API-limit, large-file and endurance tests.
- Optimize only after profiling. Use staged screening, batching, deduplication, caching, virtualized UI, lazy adapter imports, compact payloads, and resource-aware worker concurrency.
- Verify no cache collisions across different inputs/model versions/configurations.
- Establish a pinned, documented scientific validation protocol and publish actual benchmark results only when reproducible.
- Run target machine CPU and Vulkan probes; benchmark the same supported workload on each verified backend if both exist.

**Gate 7:** no critical data-loss/security/correctness issue is open; benchmark findings include environment and limitations; resource failures are graceful and visible.

### Phase 8 — Security, licenses, and docs audit

- Complete threat model, dependency/license/model/data audit, secret scan, static analysis, subprocess/path review, API auth review, and local-only egress tests.
- Verify all third-party attribution, licenses and citation requirements. Remove incompatible dependencies or disable them transparently.
- Finish README, user guide, developer guide, troubleshooting, screenshots, known limitations, citations, contribution and security documents.
- Test the installation path in a clean environment on Windows and Linux as far as available.

**Gate 8:** no known exposed secrets, no unresolved incompatible license, no critical/high unmitigated security issue without an explicit documented decision, and all installation and quick-start commands are verified.

### Phase 9 — GitHub remote, CI, cloud build, and release candidate

- Confirm correct authenticated GitHub owner and repository existence state.
- Create the public repository under the authorized account with no overwrites.
- Add secure CI/security workflows, pin Actions to full SHAs, set least-privilege permissions, configure required status checks/rulesets if permissions and plan allow, and verify secret-scanning/push-protection availability.
- Review all staged files and history before pushing. Push normal commits only; never include secrets, model weights, local DB, large datasets or private user files.
- Run cloud CI on the pushed commits. Fix any failure, push the fix, and rerun the complete required suite. Do not use a local-only green run as proof cloud CI is green.
- Build the release artifact/image in CI and test start-up/health if an image is included.
- Create a release candidate/tag only after all required gates pass. Re-run tests for the exact commit/tag that will be released.

**Gate 9:** correct GitHub repository contains the reviewed project; all required status checks are green for the release commit; build/release artifacts are present and verified; no secrets or unlicensed assets have been pushed.

### Phase 10 — Stable v1.0.0

- Review user flows end-to-end from a fresh clone and with a clean application data directory.
- Confirm docs, version numbers, changelog, CLI help, API schema, screenshots, and release assets all match the shipped commit.
- Build signed/attested artifacts only if the workflow truly produces and verifies those attestations. If not supported, say so.
- Publish `v1.0.0` only when all critical and required checks pass. Attach release notes, limitations, validated feature matrix, install instructions, SBOM/attestations when available, and benchmark provenance.
- Verify the GitHub release URL, tag, commit, asset checksums and published container/image reference if applicable.
- Update `docs/engineering/IMPLEMENTATION_STATUS.md` and `docs/engineering/AGENT_LOG.md` with final verified outcomes and blockers, then provide the user a concise handoff with repository URL, release URL, exact tests run, hardware/backend results and remaining limitations.

**Gate 10:** release artifact and public repository are verified; stable release claims are supported by evidence; no release-blocking tests are failing or falsely skipped.

---

## 17. Release acceptance checklist

The agent must check off each item with evidence, not intuition. If an item is not applicable, explain why and remove any related product claim.

### Core functionality
- [ ] Clean local install on Windows 11 x64 or supported Windows runner and supported Linux environment.
- [ ] First-run `doctor` gives accurate dependency, database, provider and backend status.
- [ ] Deterministic demo workflow works offline and does not require an API key or CUDA.
- [ ] Import errors are row-level and visible; no silent data loss.
- [ ] RDKit processing and outputs are deterministic under pinned dependency/configuration where expected.
- [ ] At least one real scientific engine integration is tested end-to-end, if included in the stable product claims.
- [ ] UI supports core project → import → workflow → run monitor → result → export path.
- [ ] CLI/API can perform and observe the same core workflow.
- [ ] Job cancellation, worker restart, failure reporting, and artifact integrity work.
- [ ] Cache invalidation is correct for changed input/model/configuration/version.
- [ ] All user-facing controls work or are accurately marked unavailable/experimental.

### CPU/Vulkan and model providers
- [ ] CPU path is verified in local tests and CI.
- [ ] Vulkan status is based on runtime/device probes, not assumptions.
- [ ] No model is labelled Vulkan-compatible unless the adapter's probe/test passes for that model/runtime.
- [ ] CPU fallback behavior is explicit, safe and visible.
- [ ] Unsupported model/backend paths return actionable messages instead of fake outputs/crashes.
- [ ] No CUDA dependency is required for the base install or core tests.
- [ ] Secret/provider configuration is redacted in logs and UI.
- [ ] Local-only mode proves it blocks remote API/data calls.

### Scientific trust
- [ ] Every prediction carries method/version/provenance and units/score interpretation.
- [ ] No model result is represented as proof of efficacy/safety or as a clinical decision.
- [ ] Data license/source and model-weight license checks are documented.
- [ ] Benchmark protocol prevents obvious leakage and records limitations.
- [ ] Reports can be regenerated from archived manifests/artifacts to the declared reproducibility level.
- [ ] Missing, censored, invalid or out-of-domain values are not silently coerced into misleading numbers.

### Quality, security and release
- [ ] Backend lint/type/unit/contract/integration suites pass.
- [ ] Frontend lint/type/unit/build suites pass.
- [ ] Core Playwright E2E tests pass.
- [ ] Security, secret, dependency and license checks pass or have a documented, scoped non-blocking exception.
- [ ] Clean DB migrations and supported upgrade path pass.
- [ ] Edge-case, path, upload, API and malformed-output tests pass.
- [ ] README, install docs and examples match actual behavior.
- [ ] UI screenshots are genuine outputs from the current implementation.
- [ ] Git history has no credentials/private datasets/model weights or unintended generated files.
- [ ] GitHub Actions uses least-privilege permissions and reviewed pinned Actions.
- [ ] Cloud CI and release build pass on the exact release commit/tag.
- [ ] Published repository/tag/release artifacts/checksums are verified.
- [ ] The handoff accurately distinguishes passed, skipped, blocked and planned items.

---

## 18. Mandatory final agent report

When the release gates are complete, provide the user a short, factual handoff containing:

1. **GitHub repository URL** and the authenticated owner/repository confirmed before push.
2. **Stable release URL/tag** and build/container artifact links, if actually published.
3. **What works in v1.0.0:** core UI, CLI/API, workflows, real scientific engines, available model integrations, export formats.
4. **Evidence:** exact test commands and summary/counts; GitHub Actions run links; E2E screenshot/test artifacts; security/license check status.
5. **Hardware/backends:** tested OS, CPU path, Vulkan probe result, exact model/runtime/backend combination tested, and anything not supported. Do not generalize one successful model to all models.
6. **Important limitations:** unsupported models/engines, remote credentials required, large weight downloads, scientific validation gaps, known bugs, unrun optional tests.
7. **Secrets and setup:** state whether credentials were only configured via approved secret mechanisms; never echo their values.
8. **User next steps:** short clean-install commands, sample workflow command, and how to open the UI/monitor jobs.

Do not finish with a vague “done” if any release gate remains blocked. Report partial completion honestly and list the precise remaining blocker. Do not wait for a future background run: complete all feasible work in the current session, then report verified outcomes.

---

## 19. Research references for periodic re-checking

The landscape changes quickly. At the start of implementation and before stable release, re-open authoritative docs/repositories and record checked dates, because model versions, licenses, requirements and API behavior can change.

- RDKit: https://github.com/rdkit/rdkit
- AutoDock Vina docs: https://autodock-vina.readthedocs.io/en/latest/
- AutoDock Vina releases: https://github.com/ccsb-scripps/AutoDock-Vina/releases
- GNINA: https://github.com/gnina/gnina
- OpenMM: https://github.com/openmm/openmm
- Boltz: https://github.com/jwohlwend/boltz
- Boltz-2 overview: https://www.boltz.com/boltz2
- Chai-1: https://github.com/chaidiscovery/chai-lab
- Chemprop: https://github.com/chemprop/chemprop
- OpenADMET: https://github.com/OpenADMET
- Open Targets docs: https://platform-docs.opentargets.org/
- ChEMBL Web Services: https://chembl.gitbook.io/chembl-interface-documentation/web-services
- PubChem PUG REST: https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest
- PDB web APIs: https://www.rcsb.org/docs/programmatic-access/web-apis-overview
- UniProt API help: https://www.uniprot.org/help/api
- Benchling feature overview: https://www.benchling.com/features
- LM Studio local server docs: https://lmstudio.ai/docs/developer/core/server
- llama.cpp: https://github.com/ggml-org/llama.cpp
- `uv` package/project manager: https://github.com/astral-sh/uv
- GitHub Actions hardening: https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions
- GitHub Actions deployment security/OIDC: https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments
- GitHub push protection: https://docs.github.com/en/code-security/concepts/secret-security/push-protection
- GitHub artifact attestations: https://docs.github.com/en/actions/concepts/security/artifact-attestations
- GitHub branch/ruleset status checks: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
- GitHub large file limits: https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github

**Final instruction:** build a real, maintainable and scientifically honest platform—not a mockup. Prefer fewer well-tested, auditable integrations over many superficial ones. Keep iterating until all feasible required gates are green, publish only what was actually verified, and make the final release reproducible, secure, visually excellent, and proudly **Made with ❤️ by hcsmedia**.
