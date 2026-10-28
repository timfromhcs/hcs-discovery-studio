# Component and license audit

Audit date: 2026-10-28. This is an engineering record, not legal advice.

## Scope

- Python runtime dependencies in `pyproject.toml` / `uv.lock`.
- Frontend dependencies in `apps/web/package.json` /
  `apps/web/package-lock.json`.
- Assets shipped in the repository, the SPA build and the wheel.
- Planned model engines listed in the registry but not bundled.

No third-party source code, model weights, datasets or images are vendored in
this repository. Dependencies are installed from package indexes at build or
install time.

## Python dependencies

| Component | Version audited | License | Use | Obligations / notes |
|---|---|---|---|---|
| CPython | 3.12.13 | PSF-2.0 | Runtime | Include PSF license when redistributing Python itself; we depend on it, we do not bundle it |
| FastAPI | 0.162.0 | MIT | HTTP API | Retain copyright and permission notice |
| Starlette | transitive | BSD-3-Clause | ASGI toolkit | Retain notice |
| Uvicorn | 0.54.0 | BSD-3-Clause | ASGI server | Retain notice |
| Pydantic | 2.14.1 | MIT | Validation | Retain notice |
| pydantic-settings | 2.16.1 | MIT | Settings | Retain notice |
| SQLAlchemy | 2.1.6 | MIT | ORM | Retain notice |
| Alembic | 1.20.1 | MIT | Migrations | Retain notice |
| RDKit | 2026.9.1 | BSD-3-Clause | Chemistry | Retain notice; cite RDKit in research outputs |
| Typer | 0.27.3 | MIT | CLI | Retain notice |
| Click | 8.5.0 | BSD-3-Clause | CLI runtime | Retain notice |
| PyYAML | 6.0.3 | MIT | Workflow parsing | Retain notice |
| Jinja2 | 3.1.6 | BSD-3-Clause | Report/template dependency | Retain notice |
| python-multipart | 0.0.32 | Apache-2.0 | Upload parsing | Include Apache-2.0 notice if redistributed |
| httpx | 0.28.1 | BSD-3-Clause | Optional LLM client and tests | Retain notice |
| NumPy | 2.5.4 | BSD-3-Clause | RDKit dependency | Retain notice |
| Pillow | 13.0.0 | HPND | RDKit depiction dependency | Retain copyright and permission notice |
| pytest | 9.2.0 | MIT | Tests (dev) | Not shipped at runtime |
| pytest-cov | transitive | MIT | Tests (dev) | Not shipped |
| Hypothesis | 6.170.12 | MPL-2.0 | Tests (dev) | MPL is file-level; no modified Hypothesis files are distributed |
| Ruff | 0.17.3 | MIT | Lint/format (dev) | Not shipped |
| mypy | 2.4.0 | MIT | Type check (dev) | Not shipped |
| types-PyYAML | dev | Apache-2.0 | Typing stubs (dev) | Not shipped |

## Frontend dependencies

| Component | Version audited | License | Use | Obligations / notes |
|---|---|---|---|---|
| React | 19.3.1 | MIT | UI runtime | Retain notice |
| React DOM | 19.3.1 | MIT | UI runtime | Retain notice |
| React Router DOM | 7.18.5 | MIT | Routing | Retain notice |
| TanStack Query | 5.105.0 | MIT | Server state | Retain notice |
| Vite | 7.3.7 | MIT | Build/dev server | Not shipped in the SPA bundle |
| TypeScript | 5.9.3 | Apache-2.0 | Type checking/build | Not shipped |
| @vitejs/plugin-react | 5.2.0 | MIT | Build plugin | Not shipped |
| @types/react, @types/react-dom | 19.3.0 | MIT | Typing (dev) | Not shipped |
| Playwright | 1.64.1 | Apache-2.0 | E2E tests (dev) | Not shipped |

The production SPA bundle contains React, React DOM, React Router and TanStack
Query code. Their MIT notices must accompany a redistribution of the bundle. The
repository's `NOTICE` lists them; a distributor of a binary should include the
full license texts.

## Assets

| Asset | Origin | License |
|---|---|---|
| `apps/web/public/favicon.svg` | Original geometric mark drawn for this project | Apache-2.0 |
| Inline SVG icons in `components/Icon.tsx` | Original line icons | Apache-2.0 |
| Brand mark in reports and UI | Original geometry | Apache-2.0 |
| `docs/screenshots/*.png` | Captured from the running application | Apache-2.0 (project), contains no third-party imagery |
| `examples/datasets/demo_library.csv` | Hand-assembled SMILES of public drug molecules | Apache-2.0 for the compilation; structures themselves are facts |
| `examples/workflows/triage.yaml` | Original | Apache-2.0 |

No third-party logo, icon font, stock photo or web font is used. The UI uses
system font stacks.

## Planned engines (not bundled)

| Engine | Repository license note | Weight/data status |
|---|---|---|
| AutoDock Vina | Apache-2.0 (upstream repository) | No weights bundled |
| OpenMM | MIT, with LGPL dependencies | No simulation data bundled |
| Chemprop | MIT | Weights are endpoint-specific and not bundled |
| Boltz-2 | MIT for repository | Weights and training data require separate audit |
| Chai-1 | Apache-2.0 for repository | Weights and training data require separate audit |

A permissive repository license does not automatically cover model weights or
training data. Any future integration must record the exact weight revision,
checksum and terms before download or use.

## Datasets

The only dataset in the repository is the small demo library. It is not a
benchmark, has no measured endpoints and is not subject to restricted terms.
Any external dataset added later must record:

- source URL and retrieval date,
- license and attribution,
- checksum,
- preprocessing and exclusions,
- redistribution constraints.

## Distribution checklist

When publishing a wheel or container:

- [ ] Include `LICENSE` and `NOTICE`.
- [ ] Include the MIT/BSD/Apache notices for bundled frontend and Python code.
- [ ] Do not claim that a dependency's license covers its weights or data.
- [ ] Do not ship a dataset you cannot redistribute.
- [ ] Keep `uv.lock` and `package-lock.json` with the release.
- [ ] Publish an SBOM with resolved versions.
- [ ] Re-run the license policy check in CI.

## Open questions

- The wheel bundles the compiled SPA. A strict reading of some MIT/BSD notice
  requirements means the full license texts should be included in the wheel
  distribution. The repository NOTICE is a summary; a future release should add
  a generated `THIRD_PARTY_LICENSES` file to the wheel.
- Container distribution is not implemented, so base-image and OS package
  licenses are out of scope for 0.1.0.
- Legal review of the Apache-2.0 NOTICE content has not been performed.
