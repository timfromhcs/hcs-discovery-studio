## What changed

<!-- Describe the problem and the change. Link related issues. -->

## Verification

<!-- List the exact commands you ran and their outcomes. Do not claim checks you did not run. -->

- [ ] `uv run ruff format --check .`
- [ ] `uv run ruff check .`
- [ ] `uv run mypy`
- [ ] `uv run pytest -q`
- [ ] `npm run typecheck` and `npm run build` in `apps/web`
- [ ] `npm run test:e2e` in `apps/web` (when UI behaviour changed)
- [ ] Documentation and screenshots updated when user-visible behaviour changed

## Scientific and security impact

- [ ] No secrets, private datasets, model weights, local databases or generated artifacts are included.
- [ ] Any new engine, model or dataset is recorded with source, version, license and validation status.
- [ ] No scientific claim is made beyond the evidence in the change.
- [ ] New UI controls are functional or explicitly marked planned/unavailable.

## Screenshots

<!-- Required for visual changes. Use genuine captures from the running application. -->
