# Install on Linux

Tested on Ubuntu 24.04 in CI (Python 3.12, Node 22). Other modern glibc
distributions should work when RDKit wheels are available.

## Requirements

- x86_64 Linux with glibc 2.28 or newer
- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Node.js 22 and npm (only for frontend development or building the SPA)
- No GPU, CUDA, Docker or API key is required for the CPU demo

## Install the toolchain

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Install Node.js 22 with your distribution's package manager, NodeSource or
`nvm`. Then verify:

```bash
uv --version
node --version
npm --version
```

If `uv` is not found after installation, add `$HOME/.local/bin` to `PATH`.

## Get the code

```bash
git clone https://github.com/timfromhcs/hcs-discovery-studio.git
cd hcs-discovery-studio
```

## Install backend dependencies

```bash
uv sync --dev
```

RDKit is installed from a prebuilt wheel; a C/C++ toolchain is normally not
required. If pip attempts a source build on an unsupported platform, use a
supported Python 3.12 environment or a manylinux-compatible distribution.

## Verify

```bash
uv run hcs-discovery doctor
```

## Build the web application

```bash
cd apps/web
npm ci
npm run build
cd ../..
```

## Run

```bash
uv run hcs-discovery serve
```

Open <http://127.0.0.1:8787>. The server binds to loopback by default and starts
an embedded worker.

For development:

```bash
uv run hcs-discovery serve --no-worker   # terminal 1
uv run hcs-discovery worker              # terminal 2
cd apps/web && npm run dev               # terminal 3
```

Vite proxies `/api` to `127.0.0.1:8787`.

## Headless / server use

To bind beyond loopback you must set a bearer token. The application refuses to
start without one:

```bash
export HCS_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export HCS_HOST=0.0.0.0
uv run hcs-discovery serve
```

Then send `Authorization: Bearer <token>` with API requests. Do not put the token
in a URL, a committed file or a shell history you share. A reverse proxy with
TLS is strongly recommended; this project does not terminate TLS itself.

## Data location

The default is `./data` relative to the working directory. For a service-style
deployment, use an absolute path:

```bash
export HCS_DATA_DIR=/var/lib/hcs-discovery
```

The directory must be writable by the process. Back up the database and the
`runs/` directory together.

## Common problems

| Symptom | Cause | Fix |
|---|---|---|
| `uv: command not found` | `~/.local/bin` not on `PATH` | Add it and reopen the shell |
| RDKit import error | Unsupported platform or partial install | Recreate the venv with `uv sync --dev --reinstall` |
| Permission denied on `data/` | Directory owned by another user | Use a writable `HCS_DATA_DIR` |
| Port already in use | Another process on 8787 | `--port 8788` |
| Blank UI | `apps/web/dist` missing | Build the frontend |
| Refuses to bind `0.0.0.0` | No `HCS_API_TOKEN` | Set a token or use loopback |

## Uninstall

Remove the repository and the data directory. No system service is installed.
