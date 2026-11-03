# Zero to hero — HCS Discovery Studio (English)

A complete first day, in order. Every command and every claim here is one you can
check; if something does not reproduce, that is a bug in this guide, not a
"known limitation".

> **What this is**: an open, local-first workbench for computational drug
> discovery. Import a compound library, triage it with transparent rules, score
> similarity (CPU or GPU), dock with AutoDock Vina if you install it, inspect every
> row and every event, and export a report.
>
> **What this is not**: a clinical decision system, a regulator-approved device, or
> evidence of binding, safety or efficacy. Rankings are prioritisation signals.

---

## 1. Pick how you run it

| You want | Use | Time |
|---|---|---|
| Nothing installed, just look | the hosted static build (Offline lab only, no backend) | 1 min |
| A real local workbench | one-file executable or wheel | 3 min |
| A server / another machine | Docker image | 5 min |
| To develop | source checkout with `uv` and Node | 10 min |

### Option A — one-file executable (Windows)

```powershell
uv pip install "pyinstaller==6.22.3"     # build-only tool, not in the lockfile
uv run python scripts/release/build_executable.py
build\exe-dist\hcs-discovery.exe doctor
build\exe-dist\hcs-discovery.exe serve
```

Open <http://127.0.0.1:8787>. The server embeds a worker, so runs execute without a
second process.

### Option B — wheel

```bash
python -m venv .venv
. .venv/bin/activate           # Windows: .venv\Scripts\Activate.ps1
pip install hcs_discovery_studio-2.0.0-py3-none-any.whl
hcs-discovery doctor
hcs-discovery serve
```

### Option C — Docker

```bash
export HCS_API_TOKEN=$(openssl rand -hex 24)
docker compose up --build
curl -H "Authorization: Bearer $HCS_API_TOKEN" http://127.0.0.1:8787/api/v1/health
```

The API refuses a non-loopback bind without a token — that is deliberate. Put a
TLS-terminating proxy in front of it before exposing it.

### Option D — source

```bash
git clone https://github.com/timfromhcs/hcs-discovery-studio.git
cd hcs-discovery-studio
uv sync --dev
cd apps/web && npm ci && npm run build && cd ../..
uv run hcs-discovery serve
```

---

## 2. First project, first run (CLI)

```bash
hcs-discovery project create --name "Demo project"
# note the project id printed above
hcs-discovery dataset import examples/datasets/demo_library.csv --project <project-id>
hcs-discovery workflow run examples/workflows/triage.yaml \
  --project <project-id> --dataset <dataset-id>
hcs-discovery run status <run-id>
hcs-discovery report export <run-id> --format html --output report.html
```

What happened: your file was parsed row by row (16 of 17 rows imported; the
duplicate is retained with its reason), RDKit standardised the structures, the
workflow computed descriptors, flagged rows against the thresholds, ranked the
survivors and wrote a summary. Every node, event and artifact is in the run
record.

Use `--json` before or after any subcommand for machine-readable output.

---

## 3. Similarity search (CPU, GPU, or both)

```bash
hcs-discovery similarity search --query "CC(=O)Oc1ccccc1C(=O)O" \
  --file examples/datasets/demo_library.csv --k 10

hcs-discovery similarity search --query "c1ccccc1" --file library.csv \
  --engine gpu --boost auto --threshold 0.7 --output scores.csv --json
```

- `--engine auto` uses a hardware GPU when present and the CPU reference otherwise.
- `--engine gpu` **fails** (exit code 3) when no hardware adapter exists instead of
  pretending.
- On a GPU, the integer popcounts are compared against the CPU reference before a
  value is returned. A mismatch is an error, not a slightly different number.
- `--boost hybrid` splits the library between the GPU and CPU threads. It is
  measured, not promised: see `docs/validation/gpu-tanimoto.md`.

`hcs-discovery gpu probe` shows the adapter; `hcs-discovery gpu bench` re-measures
parity and throughput on *your* machine.

---

## 4. The offline lab (no server at all)

Open `/lab` in the interface (or the hosted static build).

1. Import a CSV with a `smiles` column, a `.smi` file, or an `.sdf`.
2. RDKit WebAssembly computes the descriptors **in your browser**.
3. The page triages and ranks with the same rules and weights as the server
   template, and says that the score is dataset-relative.
4. "Score library" runs Tanimoto similarity through WebGPU — or the CPU reference
   if your browser/device has no adapter, labelled as such.
5. The stored copy lives in IndexedDB on this device. "Delete stored copy" really
   deletes it. Nothing is uploaded.

This is the mode that works on a phone, on a plane, and on a static host with no
backend.

---

## 5. Automation: API, MCP, workflows

**HTTP API** — versioned at `/api/v1`, OpenAPI at `/api/v1/openapi.json`.

```bash
curl -X POST http://127.0.0.1:8787/api/v1/similarity/search \
  -H "Content-Type: application/json" \
  -d '{"dataset_id":"<id>","query_smiles":"c1ccccc1","k":5,"engine":"cpu"}'
```

**MCP** — for local AI assistants:

```bash
hcs-discovery mcp serve     # JSON-RPC 2.0 on stdin/stdout
```

Tools: `hcs_doctor`, `hcs_similarity_search`, `hcs_gpu_bench`,
`hcs_workflow_validate`, `hcs_models_list`. Read-only, bounded inputs, no shell.

**Constraint selection (SAT)** — ask for a subset that must satisfy hard rules:

```bash
hcs-discovery sat select --group "low=a,b" --group "mid=c,d" --k-max 2
hcs-discovery sat solve --cnf formula.cnf     # exit 5 means unsatisfiable
```

---

## 6. When something looks wrong

| Symptom | Check |
|---|---|
| "frontend not built" | `cd apps/web && npm ci && npm run build` |
| `program not found: hcs` | The command is `hcs-discovery`. |
| Non-loopback bind refused | Set `HCS_API_TOKEN`; TLS is your proxy's job. |
| GPU not used | `hcs-discovery gpu probe`; software adapters are ignored on purpose. |
| GPU parity failure | That is a real failure — the result is withheld. Report it with the adapter name. |
| Browser chemistry fails | The CSP must allow `'wasm-unsafe-eval'` and `'unsafe-eval'`; the app sets this itself. |
| E2E port conflict | Playwright uses 8791 (backend) and 8792 (static); stop other servers. |

`hcs-discovery doctor` answers most of these at once.

---

## 7. The honesty checklist

Before you cite a number from this project, check which of these it is:

- **Measured on this host** (a report in `docs/validation/` names the hardware).
- **Verified in CI** (link to the run in `docs/engineering/IMPLEMENTATION_STATUS.md`).
- **Planned** (a registry card marked `planned`; it cannot be run).
- **Weak and labelled as such** (ESOL RMSE ≈ 0.97 and R² ≈ 0.07 — barely better
  than a constant baseline).

If a claim does not fit one of those, it is a documentation bug. Open an issue.
