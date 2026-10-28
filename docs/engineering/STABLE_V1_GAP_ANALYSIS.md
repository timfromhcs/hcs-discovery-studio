# Stable v1.0.0 Gap Analysis and Action Plan

**Date:** 2026-10-28  
**Current Baseline Commit:** `bd44f206b7c6a5897e503ef63dc7847461b65f63`  
**Current Shipped Version:** `0.1.0` preview  
**Target Version:** `1.0.0` Stable  
**Brand:** `Open science. Reproducible discovery. Made with ❤️ by hcsmedia.`  

---

## 1. Verified Baseline Facts (Reproduced Locally)

| Dimension | Measured Value / Status | Verification Evidence |
|---|---|---|
| Host Platform | Windows 11 Build 26200, AMD Ryzen 7 7735HS (8C/16T, 19.8 GB RAM) | PowerShell CIM queries |
| Python Runtime | Python 3.12.13 (via `uv 0.12.3`) | `uv run python --version` |
| Chemistry Engine | RDKit 2026.09.1 | `hcs-discovery doctor` |
| Graphics / Vulkan | AMD Radeon(TM) Graphics (iGPU), Vulkan 1.4.315 / 1.4.357, Driver 2.0.353 | `vulkaninfo --summary` |
| Web Toolchain | Node v22.23.1, npm 10.9.8, Vite 8.3.5, React 19.3.1, TypeScript 7.0.2 | `apps/web/package.json` |
| Code Formatting | 108 files formatted | `uv run ruff format --check .` (0 errors) |
| Static Linting | Ruff lint clean | `uv run ruff check .` (0 errors) |
| Type Checking | 62 Python files clean; TypeScript clean | `uv run mypy` (0 errors); `npm run typecheck` (0 errors) |
| Backend Tests | 82 passed, 0 failed, 58 warnings | `pytest -q --cov=hcs_discovery` (75% coverage) |
| Frontend E2E | 3 passed, 0 failed (11.2s) | `playwright test` against `127.0.0.1:8791` |
| Packaged Wheel | `hcs_discovery_studio-0.1.0-py3-none-any.whl` built | `uv build --wheel` |
| Wheel Smoke Test | Clean venv install, serves SPA, healthcheck 200 OK | `Invoke-RestMethod http://127.0.0.1:8793/api/v1/health` |
| CPU Smoke Journey | Project create -> import CSV -> triage workflow -> worker execution -> results -> HTML/MD reports | CLI commands on isolated test database |

---

## 2. Proven Defects and Correctness Gaps

### 2.1 Database Auto-Initialization on Fresh CLI Invocations
- **Problem:** Invoking `hcs-discovery project create` on a fresh data directory fails with `OperationalError: no such table: audit_events`. While `serve` and `worker` execute `init_db()`, `get_session_factory()` does not ensure schema existence for direct CLI or API calls on new databases.
- **Fix:** Ensure `init_db()` is called or database tables are verified lazily/idempotently upon database engine/session creation or CLI entrypoints before executing queries.

### 2.2 Pareto Front Nondominated Sorting Correctness
- **Problem:** In `src/hcs_discovery/workflow/nodes.py`, the Pareto ranking compares candidates sequentially against the currently accumulated members of a front. This algorithm is order-dependent and violates mathematical dominance invariance when input rows are permuted or when ties/zero-weights occur.
- **Fix:** Replace with standard nondominated sorting (Deb et al. / Fast Non-dominated Sorting algorithm). Add property tests verifying dominance invariance under row permutation, identical ties, and missing values.

### 2.3 Filter Validation and Type Safety
- **Problem:** `RuleConfig` checks `between` for `value2`, but does not strictly validate operator-to-value compatibility prior to workflow queueing. Incompatible values (e.g. non-numeric strings for numeric thresholds) bypass validation and crash during node execution.
- **Fix:** Pre-validate operator schemas, ensure value finiteness and range sanity (`min <= max`), and enforce explicit missing-value handling policies.

### 2.4 Chemistry Descriptor Error Boundary
- **Problem:** The descriptor loop catches generic `Exception` and assigns `None`, obscuring implementation defects from legitimate per-compound chemistry parsing limits.
- **Fix:** Separate expected chemistry calculation errors (e.g., sanitization failure, non-standard valences) from internal execution exceptions. Log structured error details without leaking sensitive structures.

### 2.5 Multi-Objective Semantics and Outlier Sensitivity
- **Problem:** Min-max normalized composite ranking is strictly dataset-relative and susceptible to extreme outlier compression. All objectives are treated as simple min/max dimensions.
- **Fix:** Support explicit objective roles: `maximize`, `minimize`, `target_range`, `constraint`, and `informational`. Isolate composite scoring weights from Pareto dominance so zero-weight dimensions do not skew the Pareto front.

### 2.6 Residual Data and Disk Cleanup on Deletion
- **Problem:** Deleting a project or dataset removes database records but leaves upload files and run directories on disk.
- **Fix:** Implement robust retention and cascading deletion policies for both database entities and on-disk run artifacts, with preview/dry-run options.

### 2.7 Bounded Cache Lifecycle
- **Problem:** Content-addressed node cache (`cache/`) grows without bounds. `prune` removes items without configurable size/age thresholds.
- **Fix:** Add configurable cache size and age limits, LRU eviction, and `cache prune --dry-run` and `cache status` views.

---

## 3. Real Scientific Engine Requirements (v1.0.0 Mandate)

| Engine / Adapter | Current Status | Mandated Stable Requirement | Implementation Path |
|---|---|---|---|
| **RDKit** | Working (0.1.0) | Complete descriptor validation, reference benchmarks, SVG sanitization | Add reference molecule benchmark suites and sanitized SVG generation |
| **AutoDock Vina** | Planned metadata only | Real CPU-capable docking workflow: target/ligand prep, box definition, parameter bounds, pose parsing, PDBQT/SDF artifacts | Implement native CPU Vina adapter with bundled or discoverable runner, parameter validation, pose extraction, and smoke benchmark |
| **Learned Properties** | Planned metadata only | Real model family adapter (e.g., Chemprop / validated QSAR models) with train/test split awareness, uncertainty, applicability domain | Implement property prediction adapter with offline fixture models, applicability domain checks, and baseline comparison metrics |
| **External Connectors** | Planned metadata only | PubChem and ChEMBL connectors with strict network policy enforcement (offline by default, explicit user opt-in) | Implement client connectors with rate-limiting, retries, local caching, and offline mock test suites |

---

## 4. UI/UX, Workflows, and Local Agent Requirements

### 4.1 Workflow DAG Capabilities
- Move beyond linear chains: support fan-out branching from a single source node.
- Explicit merge/join nodes based on compound identity keys (not physical row order).
- Conditional execution and bounded parameter sweeps.

### 4.2 Local Research Assistant (Agent)
- Implement genuine local agent architecture with three explicit modes:
  1. **Ask:** Read-only queries over current project, manifest, and engine status.
  2. **Plan:** Structured plan generation with required tools, inputs, and limitations.
  3. **Run:** Controlled execution of allowlisted server tools with user approval boundaries.
- Strict input validation to prevent prompt-injection from molecular metadata or external text.

### 4.3 Branding and Visual Design
- Original SVG branding assets:
  - `apps/web/public/favicon.svg`
  - `apps/web/public/brand/hcs-discovery-mark.svg`
  - `apps/web/public/brand/hcs-discovery-wordmark.svg`
  - `docs/assets/branding/social-preview.png` (1280x640, <1MB)
- Visual accessibility review and responsive validation at 320px, 390px, 768px, 1280px, 1440px across light/dark themes.

---

## 5. Execution Order and Phasing

1. **Phase 1: Foundations & Correctness**
   - Fix database auto-initialization across CLI and services.
   - Implement nondominated sorting for Pareto fronts with permutation-invariance tests.
   - Harden workflow node validation (filter operators, missing value semantics, objective types).
   - Implement bounded cache eviction and file cleanup on deletion.
2. **Phase 2: Scientific Integrations**
   - Implement CPU AutoDock Vina docking adapter with pose parsing and run tests.
   - Implement learned property prediction adapter with applicability domain and benchmark metrics.
   - Implement PubChem / ChEMBL connectors with offline fixtures and strict network policy.
3. **Phase 3: Workflows & Results Explorer**
   - Add DAG branching and key-based merge nodes.
   - Enhance results table (saved filters, multi-column sort, full export).
4. **Phase 4: Agentic Assistant & UI Polish**
   - Implement Ask / Plan / Run agent with allowlisted tool calls.
   - Generate official HCS brand assets and UI enhancements.
   - Visual QA and accessibility checks across themes and viewport breakpoints.
5. **Phase 5: Packaging & Release Gates**
   - Standalone bundle / package smoke testing for Windows & Linux.
   - Cloud CI gate reproduction and release-candidate verification.
