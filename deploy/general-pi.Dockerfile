ARG CAPSTONE_BACKEND_IMAGE=capstone-backend:local
FROM ${CAPSTONE_BACKEND_IMAGE} AS managed-runtime
FROM node:24.20.0-bookworm-slim@sha256:ba849c60be29959425b8734d57b8b4b7d56f98edd9504c9af091d5281095a71e AS node
FROM python:3.12-slim-bookworm@sha256:54c85f3c47607a77f32adec749d3c81d1348bf25833671f512b26a9b6d778cb3
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=managed-runtime /app/.grid-agent/runtime/pi/source/ /opt/pi/
COPY --from=managed-runtime /usr/local/bin/uv /usr/local/bin/uv
RUN apt-get update && apt-get install --no-install-recommends -y ca-certificates curl git \
    && rm -rf /var/lib/apt/lists/* && pip install --no-cache-dir httpx==0.28.1 jsonschema==4.26.0 referencing==0.37.0
WORKDIR /opt/general
COPY packages/capstone-agent/src/capstone_agent/__init__.py capstone_agent/__init__.py
COPY packages/capstone-agent/src/capstone_agent/runtime_resources.py capstone_agent/runtime_resources.py
COPY packages/capstone-agent/src/capstone_agent/resource_installation.py capstone_agent/resource_installation.py
COPY configs/runtime/power-samples.lock.json configs/runtime/power-samples.lock.json
COPY configs/runtime/prepared-mcp-v1.schema.json configs/runtime/prepared-mcp-v1.schema.json
COPY tools/power_sample_smoke.py tools/power_sample_smoke.py
RUN UV_PYTHON_INSTALL_DIR=/opt/general/.grid-agent/runtime/python \
    python -m capstone_agent.resource_installation --config-root configs/runtime \
    && mkdir /opt/general/resource-seed \
    && cp -a /opt/general/.grid-agent/runtime/agent-resources /opt/general/resource-seed/agent-resources \
    && cp -a /opt/general/.grid-agent/runtime/python /opt/general/resource-seed/python \
    && mkdir -p /var/lib/general-pi/tasks /var/lib/general-pi/receipts /var/lib/general-pi/profiles \
    && chmod 0711 /var/lib/general-pi /var/lib/general-pi/tasks \
    && chmod 0700 /var/lib/general-pi/receipts /var/lib/general-pi/profiles
COPY packages/capstone-agent/src/capstone_agent/pi_delegation.py capstone_agent/pi_delegation.py
COPY packages/capstone-agent/src/capstone_agent/business_context.py capstone_agent/business_context.py
COPY packages/capstone-agent/src/capstone_agent/general_pi_executor.py capstone_agent/general_pi_executor.py
COPY packages/capstone-agent/src/capstone_agent/general_pi_server.py capstone_agent/general_pi_server.py
COPY packages/capstone-agent/src/capstone_agent/general_pi_storage.py capstone_agent/general_pi_storage.py
COPY packages/capstone-agent/src/capstone_agent/general_pi_relay.py capstone_agent/general_pi_relay.py
COPY packages/capstone-agent/src/capstone_agent/bounded_http_loop.py capstone_agent/bounded_http_loop.py
COPY packages/capstone-agent/src/capstone_agent/conversation_context.py capstone_agent/conversation_context.py
COPY packages/capstone-agent/src/capstone_agent/request_intent.py capstone_agent/request_intent.py
COPY packages/capstone-agent/src/capstone_agent/resources/general-context.mjs capstone_agent/resources/general-context.mjs
COPY packages/capstone-agent/src/capstone_agent/resources/general-sdk.mjs capstone_agent/resources/general-sdk.mjs
COPY packages/capstone-agent/src/capstone_agent/resources/general-mcp.mjs capstone_agent/resources/general-mcp.mjs
COPY packages/capstone-agent/src/capstone_agent/native_resources.py capstone_agent/native_resources.py
COPY packages/capstone-agent/src/capstone_agent/bounded_mcp.py capstone_agent/bounded_mcp.py
COPY packages/capstone-agent/src/capstone_agent/general_pi_resource_seed.py capstone_agent/general_pi_resource_seed.py
COPY configs/runtime/general-pi/ config/
COPY configs/runtime/general-pi/ configs/runtime/general-pi/
COPY configs/runtime/capstone-pi/settings.json configs/runtime/capstone-pi/settings.json
COPY configs/runtime/agent-resources.json configs/runtime/agent-resources.json
COPY configs/llm-providers.json llm-providers.json
COPY configs/runtime/pi-runtime.lock.json pi-runtime.lock.json
ENV PYTHONUNBUFFERED=1 CAPSTONE_GENERAL_SANDBOX=container PORT=8790
EXPOSE 8790
CMD ["python", "-m", "capstone_agent.general_pi_resource_seed"]
