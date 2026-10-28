# Contributing to HCS Discovery Studio

Thanks for helping build open, reproducible drug-discovery tooling. This project
values correctness over speed, honest limitations over marketing, and
reproducible evidence over confident claims.

## Before you start

- Read `CODE_OF_CONDUCT.md`.
- Read `SECURITY.md` before reporting anything security-sensitive.
- For substantial features, open an issue that describes the scientific
  question, the proposed interface, and how correctness will be tested.
- Do not add a model adapter, benchmark claim or dataset without a license and
  provenance record.

## Development setup

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), Node.js 22 and npm.

```bash
git clone https://github.com/timfromhcs/hcs-discovery-studio.git
cd hcs-discovery-studio
uv sync --dev
cd apps/web && npm ci && cd ../..
uv run hcs-discovery doctor
```

The application uses `./data` by default. Set `HCS_DATA_DIR` to keep local data
somewhere else.

## Local gates

Run every gate before opening a pull request:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest -q

cd apps/web
npm run typecheck
npm run build
npm run test:e2e
```

`npm run test:e2e` starts its own server on `127.0.0.1:8791` with a clean
`.e2e-data` directory and requires `apps/web/dist` to exist.

If your change affects packaging, also build and smoke-test the wheel:

```bash
uv build --wheel
```

See `docs/developer-guide/TESTING.md` for the test layout and
`docs/engineering/PACKAGING.md` for the wheel check.

## Code conventions

- Python: 120-character lines, Ruff formatting, type hints on public functions,
  Pydantic models at boundaries, no silent exception swallowing.
- TypeScript/React: strict TypeScript, TanStack Query for server state, local
  component state for editor state, no new global state library without a
  concrete need.
- CSS: use the existing design tokens in `apps/web/src/styles/global.css`.
  Do not introduce a second styling system.
- Node IDs, API fields and artifact names are part of the reproducibility
  contract. Renaming one requires a migration or a version bump.
- Never log or persist a credential. Use the redaction helpers and
  `Settings.public_dict()`.
- Never claim a feature works because the code compiles. Exercise it through
  the UI, CLI or API and record what you actually observed.

## Scientific changes

- A descriptor or score must name its method, version, units and direction.
- A new filter threshold is a project criterion, not a universal law. Label it
  as such.
- Do not call a ranking a prediction of efficacy, safety or binding.
- New datasets need a source URL, license, retrieval date and checksum.
- Benchmarks must follow `docs/scientific-validation/VALIDATION_PROTOCOL.md`.
  A benchmark result is `reproduced`, `partially reproduced`, `not comparable`
  or `not reproduced`; it is never simply "SOTA".
- If a result depends on randomness, record the seed and the sources of
  nondeterminism.

## Documentation changes

- Commands in docs must be runnable exactly as written.
- Screenshots must come from the working application. Do not mock a feature
  that is not implemented.
- Update `CHANGELOG.md` and `docs/engineering/IMPLEMENTATION_STATUS.md` when the
  shipped behavior changes.
- Check relative links and spelling.

## Commit and pull-request style

Use concise conventional commits, for example:

```text
feat(workflow): add deterministic Morgan similarity node
fix(api): reject non-loopback bind without a token
docs(security): document local-only network policy
test(runs): cover expired lease recovery
```

A pull request should state:

1. what changed and why,
2. the exact commands and results used to verify it,
3. user-visible limitations or follow-up work,
4. any license, data or security implications.

Do not include generated local databases, run artifacts, model weights, `.env`
files or screenshots of fabricated states.

## Licensing

By contributing, you agree that your contribution is licensed under
Apache-2.0. Do not copy code, data, images or model weights that you do not have
the right to redistribute. Record third-party additions in `NOTICE` and
`docs/research/COMPONENT_AND_LICENSE_AUDIT.md`.
