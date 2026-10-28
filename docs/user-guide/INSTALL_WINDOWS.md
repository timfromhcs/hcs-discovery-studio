# Install on Windows

Tested on Windows 11 (build 26200) with PowerShell 7. Windows 10 should work but
is not part of the current test matrix.

## Requirements

- Windows 10/11 x64
- Python 3.12 (3.13 is allowed by the package metadata but 3.12 is the tested
  version)
- [uv](https://docs.astral.sh/uv/)
- Node.js 22 and npm (only for frontend development or building the SPA)
- No GPU, CUDA, Docker or API key is required for the CPU demo

## Install the toolchain

Open PowerShell:

```powershell
winget install --id astral-sh.uv -e
winget install --id OpenJS.NodeJS.LTS -e
```

Close and reopen the terminal so `uv` and `npm` are on `PATH`. Verify:

```powershell
uv --version
node --version
npm --version
```

`uv` can download and manage Python 3.12 itself. If you already have Python,
`uv sync` will use a compatible interpreter.

## Get the code

```powershell
git clone https://github.com/timfromhcs/hcs-discovery-studio.git
cd hcs-discovery-studio
```

If you downloaded a ZIP instead, extract it and `cd` into the folder.

## Install backend dependencies

```powershell
uv sync --dev
```

This creates `.venv` and installs the locked dependencies, including RDKit.

## Verify the environment

```powershell
uv run hcs-discovery doctor
```

A healthy output ends with `diagnostics (ok)` and shows RDKit, the SQLite
database and the local data directory. Warnings are acceptable; errors are not.

If PowerShell reports that `uv` wrote to stderr but the command still produced
output, check `$LASTEXITCODE` rather than assuming failure. `uv` uses stderr for
progress messages.

## Build the web application

```powershell
cd apps\web
npm ci
npm run build
cd ..\..
```

`npm run build` writes `apps\web\dist`. The backend serves that directory when
present. The published wheel already contains the built SPA; this step is only
needed for a source checkout.

## Run

```powershell
uv run hcs-discovery serve
```

Open <http://127.0.0.1:8787>. The command starts the API, the bundled UI and an
embedded worker.

For development with hot reload:

```powershell
# terminal 1
uv run hcs-discovery serve --no-worker

# terminal 2
uv run hcs-discovery worker

# terminal 3
cd apps\web
npm run dev
```

Vite serves the UI at <http://127.0.0.1:5173> and proxies `/api` to
`127.0.0.1:8787`.

## Install the wheel instead

```powershell
uv build --wheel
uv pip install dist\hcs_discovery_studio-0.1.0-py3-none-any.whl
hcs-discovery serve
```

The wheel includes the built UI. It still needs the runtime dependencies from
`pyproject.toml`; install it into an environment that already has them or let
pip resolve them.

## Common problems

| Symptom | Cause | Fix |
|---|---|---|
| `hcs-discovery` is not recognized | Console script not installed or venv not active | Use `uv run hcs-discovery ...` from the repo |
| `ModuleNotFoundError: rdkit` | Dependencies not synced | `uv sync --dev` |
| Port 8787 already in use | Another instance is running | `uv run hcs-discovery serve --port 8788` |
| UI shows a blank page or JSON 404 | `apps/web/dist` missing | `cd apps\web; npm ci; npm run build` |
| `uv sync` fails with a file lock | A server is running from `.venv` | Stop it, then retry |
| Data appears in the wrong place | `HCS_DATA_DIR` is relative to the current directory | Set an absolute `HCS_DATA_DIR` |

## Where data lives

By default: `.\data\hcs.sqlite3`, with run artifacts under `.\data\runs`. Set
`HCS_DATA_DIR` to an absolute path to keep data outside the repository.

## Uninstall

Delete the repository folder and the data directory. There is no system-wide
installation, service or registry entry.
