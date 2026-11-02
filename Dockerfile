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

# Locked third-party dependencies. These inputs stay ahead of application source.
COPY packages/capability-agent-kernel/pyproject.toml packages/capability-agent-kernel/uv.lock packages/capability-agent-kernel/
COPY packages/capstone-agent/pyproject.toml packages/capstone-agent/uv.lock packages/capstone-agent/
COPY packages/capstone-model-capability-spi/pyproject.toml packages/capstone-model-capability-spi/uv.lock packages/capstone-model-capability-spi/
COPY packages/enterprise-research-domain-pack/pyproject.toml packages/enterprise-research-domain-pack/
COPY packages/grid-agent/pyproject.toml packages/grid-agent/uv.lock packages/grid-agent/
COPY packages/grid-simulator/pyproject.toml packages/grid-simulator/uv.lock packages/grid-simulator/
COPY packages/inventory-domain-pack/pyproject.toml packages/inventory-domain-pack/uv.lock packages/inventory-domain-pack/
COPY packages/inventory-reference-service/pyproject.toml packages/inventory-reference-service/uv.lock packages/inventory-reference-service/
COPY packages/pandapower-domain-pack/pyproject.toml packages/pandapower-domain-pack/uv.lock packages/pandapower-domain-pack/
COPY packages/pypsa-agent/pyproject.toml packages/pypsa-agent/uv.lock packages/pypsa-agent/
COPY packages/pypsa-capacity-planning-domain-pack/pyproject.toml packages/pypsa-capacity-planning-domain-pack/uv.lock packages/pypsa-capacity-planning-domain-pack/
COPY packages/pypsa-model-authority/pyproject.toml packages/pypsa-model-authority/uv.lock packages/pypsa-model-authority/
COPY packages/pypsa-network-modeling-domain-pack/pyproject.toml packages/pypsa-network-modeling-domain-pack/uv.lock packages/pypsa-network-modeling-domain-pack/
COPY packages/pypsa-power-operations-domain-pack/pyproject.toml packages/pypsa-power-operations-domain-pack/uv.lock packages/pypsa-power-operations-domain-pack/
COPY packages/pypsa-sector-coupling-domain-pack/pyproject.toml packages/pypsa-sector-coupling-domain-pack/uv.lock packages/pypsa-sector-coupling-domain-pack/
RUN --mount=type=cache,id=capstone-python-downloads,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --no-install-local --project packages/grid-agent \
    && uv sync --frozen --no-dev --no-install-project --no-install-local --project packages/grid-simulator \
    && uv sync --frozen --no-dev --no-install-project --no-install-local --project packages/pypsa-agent \
    && uv sync --frozen --no-dev --no-install-project --no-install-local --project packages/capstone-agent

COPY packages/pi-capability-tools/package.json packages/pi-capability-tools/package-lock.json packages/pi-capability-tools/
COPY packages/pi-grid-tools/package.json packages/pi-grid-tools/package-lock.json packages/pi-grid-tools/
RUN --mount=type=cache,id=capstone-npm-downloads,target=/root/.npm \
    npm ci --prefix packages/pi-capability-tools \
    && npm ci --prefix packages/pi-grid-tools

COPY packages/capability-agent-kernel/src/capability_agent/runtime/capacity.py packages/capability-agent-kernel/src/capability_agent/runtime/capacity.py
COPY packages/capability-agent-kernel/src/capability_agent/runtime/lock.py packages/capability-agent-kernel/src/capability_agent/runtime/lock.py
COPY packages/capability-agent-kernel/src/capability_agent/runtime/locator.py packages/capability-agent-kernel/src/capability_agent/runtime/locator.py
COPY packages/capability-agent-kernel/src/capability_agent/runtime/installer.py packages/capability-agent-kernel/src/capability_agent/runtime/installer.py
COPY configs/runtime/pi-runtime.lock.json configs/runtime/pi-runtime.lock.json
COPY configs/runtime/patches/ configs/runtime/patches/
COPY deploy/install_pinned_pi.py deploy/install_pinned_pi.py
RUN python deploy/install_pinned_pi.py

COPY packages/capstone-agent/src/capstone_agent/__init__.py packages/capstone-agent/src/capstone_agent/__init__.py
COPY packages/capstone-agent/src/capstone_agent/resource_installation.py packages/capstone-agent/src/capstone_agent/resource_installation.py
COPY packages/capstone-agent/src/capstone_agent/runtime_resources.py packages/capstone-agent/src/capstone_agent/runtime_resources.py
COPY configs/runtime/power-samples.lock.json configs/runtime/prepared-mcp-v1.schema.json configs/runtime/
COPY tools/power_sample_smoke.py tools/power_sample_smoke.py
RUN UV_PYTHON_INSTALL_DIR=/app/.grid-agent/runtime/python \
    PYTHONPATH=/app/packages/capstone-agent/src \
    /app/packages/capstone-agent/.venv/bin/python -m capstone_agent.resource_installation --config-root configs/runtime

COPY packages/pypsa-model-authority/src/pypsa_model_authority/__init__.py packages/pypsa-model-authority/src/pypsa_model_authority/__init__.py
COPY packages/pypsa-model-authority/src/pypsa_model_authority/model_library.py packages/pypsa-model-authority/src/pypsa_model_authority/model_library.py
COPY packages/pypsa-model-authority/src/pypsa_model_authority/resources/model-library.json packages/pypsa-model-authority/src/pypsa_model_authority/resources/model-library.json
COPY deploy/local-model-assets/ /opt/capstone-models/
ENV CAPSTONE_PYPSA_MODEL_LIBRARY_DIR=/opt/capstone-models
RUN export PYTHONPATH=/app/packages/pypsa-model-authority/src \
    && python -m pypsa_model_authority.model_library install --all \
    && python -c 'from pypsa_model_authority.model_library import list_official_examples, verified_asset_path; [verified_asset_path(item.catalog_id) for item in list_official_examples()]'

# Volatile application source. A source-only change starts at this copy.
COPY packages/ packages/
COPY configs/ configs/
COPY validation/ validation/
COPY tools/ tools/
COPY scripts/ scripts/
COPY schemas/ schemas/
COPY third-party-notices/ third-party-notices/
COPY deploy/entrypoint.sh deploy/entrypoint.sh
COPY deploy/launch_host_runtime.py deploy/launch_host_runtime.py
COPY deploy/dev_trial_runtime.py deploy/dev_trial_runtime.py
COPY deploy/bake_catalog_snapshot.py deploy/bake_catalog_snapshot.py
COPY Dockerfile Dockerfile
COPY deploy/ensure_bucket.py deploy/ensure_bucket.py
COPY deploy/preserve_local_runtime.py deploy/preserve_local_runtime.py

ENV UV_NO_SYNC=1 \
    UV_NO_DEV=1 \
    CAPSTONE_POWERMCP_MANAGED_ROOT=/app/.grid-agent/runtime/agent-resources \
    PYTHONUNBUFFERED=1 \
    PORT=8766

RUN --mount=type=cache,id=capstone-python-downloads,target=/root/.cache/uv \
    UV_NO_SYNC=0 uv sync --locked --no-dev --project packages/grid-agent \
    && UV_NO_SYNC=0 uv sync --locked --no-dev --project packages/grid-simulator \
    && UV_NO_SYNC=0 uv sync --locked --no-dev --project packages/pypsa-agent \
    && UV_NO_SYNC=0 uv sync --locked --no-dev --project packages/capstone-agent \
    && uv run --no-sync --project packages/capstone-agent python deploy/bake_catalog_snapshot.py \
    && groupadd --system capstone \
    && useradd --system --gid capstone --home-dir /app --no-create-home capstone \
    && mkdir -p /app/runs /app/.capstone-agent /app/.grid-agent /tmp/uv-cache \
    && rm -rf /root/.npm /root/.cache/pip \
    && chown -R capstone:capstone /app /opt/capstone-models /tmp/uv-cache \
    && python -c 'import hashlib; from pathlib import Path; skip={"node_modules","__pycache__",".venv"}; root=Path("packages"); digest=hashlib.sha256();\
[digest.update(path.relative_to(root).as_posix().encode()+b"\0"+path.read_bytes()) for path in sorted(p for p in root.rglob("*") if p.is_file() and skip.isdisjoint(p.parts))]; Path("deploy/source-identity.txt").write_text(digest.hexdigest()+"\n")'

ENV UV_CACHE_DIR=/tmp/uv-cache
ARG CAPSTONE_SOURCE_REVISION=development
LABEL org.opencontainers.image.revision=$CAPSTONE_SOURCE_REVISION
RUN printf '%s\n' "$CAPSTONE_SOURCE_REVISION" > deploy/image-source.txt
USER capstone
EXPOSE 8766
ENTRYPOINT ["/app/deploy/entrypoint.sh"]
CMD ["api"]
