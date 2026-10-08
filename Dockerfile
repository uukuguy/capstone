FROM node:24.20.0-bookworm-slim@sha256:ba849c60be29959425b8734d57b8b4b7d56f98edd9504c9af091d5281095a71e AS node

FROM python:3.12-slim-bookworm@sha256:54c85f3c47607a77f32adec749d3c81d1348bf25833671f512b26a9b6d778cb3

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates git libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv==0.10.7

WORKDIR /app
COPY packages/ packages/
COPY configs/ configs/
COPY validation/ validation/
COPY tools/ tools/
COPY scripts/ scripts/
COPY schemas/ schemas/
COPY third-party-notices/ third-party-notices/
COPY deploy/entrypoint.sh deploy/entrypoint.sh
COPY deploy/launch_host_runtime.py deploy/launch_host_runtime.py
COPY deploy/bake_catalog_snapshot.py deploy/bake_catalog_snapshot.py
COPY Dockerfile Dockerfile
COPY deploy/ensure_bucket.py deploy/ensure_bucket.py
COPY deploy/local-model-assets/ /opt/capstone-models/

ENV UV_NO_SYNC=1 \
    UV_NO_DEV=1 \
    CAPSTONE_PYPSA_MODEL_LIBRARY_DIR=/opt/capstone-models \
    PYTHONUNBUFFERED=1 \
    PORT=8766

RUN UV_NO_SYNC=0 uv sync --locked --no-dev --project packages/grid-agent \
    && UV_NO_SYNC=0 uv sync --locked --no-dev --project packages/grid-simulator \
    && UV_NO_SYNC=0 uv sync --locked --no-dev --project packages/pypsa-agent \
    && UV_NO_SYNC=0 uv sync --locked --no-dev --project packages/capstone-agent \
    && npm ci --prefix packages/pi-capability-tools \
    && npm ci --prefix packages/pi-grid-tools \
    && UV_NO_SYNC=0 uv run --no-sync --project packages/grid-agent grid-agent install-pi \
    && UV_NO_SYNC=0 uv run --no-sync --project packages/pypsa-agent \
       python -m pypsa_model_authority.model_library install --all \
    && UV_NO_SYNC=0 uv run --no-sync --project packages/pypsa-agent \
       python -c 'from pypsa_model_authority.model_library import list_official_examples, verified_asset_path; [verified_asset_path(item.catalog_id) for item in list_official_examples()]' \
    && uv run --no-sync --project packages/capstone-agent python deploy/bake_catalog_snapshot.py \
    && groupadd --system capstone \
    && useradd --system --gid capstone --home-dir /app --no-create-home capstone \
    && mkdir -p /app/runs /app/.capstone-agent /app/.grid-agent /tmp/uv-cache \
    && rm -rf /root/.cache/uv /root/.npm /root/.cache/pip \
    && chown -R capstone:capstone /app /opt/capstone-models /tmp/uv-cache

ENV UV_CACHE_DIR=/tmp/uv-cache
USER capstone
EXPOSE 8766
ENTRYPOINT ["/app/deploy/entrypoint.sh"]
CMD ["api"]
