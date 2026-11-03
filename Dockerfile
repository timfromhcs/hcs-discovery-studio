# syntax=docker/dockerfile:1.7
# One image for the local workbench and for a container host (Vercel Container
# Registry, a VPS, a laptop). Same API, same SPA, same GPU-agnostic CPU path.

# --------------------------------------------------------------------------- web
FROM node:22-slim AS web
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web/ ./
# The browser and the native engine share one WGSL file; the import in
# src/lib/gpuTanimoto.ts resolves four levels up to the repository's src/ tree, so
# the kernel is copied to that same relative location instead of duplicating it.
COPY src/hcs_discovery/gpu/kernels /src/hcs_discovery/gpu/kernels
RUN npm run build

# ----------------------------------------------------------------------- runtime
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HCS_DATA_DIR=/data \
    HCS_WEB_DIST=/app/apps/web/dist \
    HCS_HOST=0.0.0.0 \
    HCS_PORT=8787

# curl backs the healthcheck. RDKit's Draw module links against X render libraries
# even when it only writes SVG, so the three runtime libs are required; no X server
# is installed or started.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl libxrender1 libxext6 libsm6 libexpat1 libfontconfig1 libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

# The API refuses a non-loopback bind without a bearer token, so the container is
# only useful with HCS_API_TOKEN set. It is intentionally not baked into the image.
RUN useradd --create-home --uid 10001 hcs
WORKDIR /app

COPY pyproject.toml README.md LICENSE NOTICE hatch_build.py ./
COPY src ./src
COPY migrations ./migrations
COPY examples ./examples
COPY --from=web /web/dist ./apps/web/dist

RUN pip install --no-cache-dir . \
    && mkdir -p /data \
    && chown -R hcs:hcs /data /app

USER hcs
VOLUME ["/data"]
EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8787/api/v1/health || exit 1

# HCS_HOST/HCS_PORT come from the environment (0.0.0.0:8787 by default here).
CMD ["hcs-discovery", "serve"]
