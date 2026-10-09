ARG CAPSTONE_BACKEND_IMAGE=capstone-backend:local
FROM ${CAPSTONE_BACKEND_IMAGE} AS managed-runtime
FROM node:24.20.0-bookworm-slim@sha256:ba849c60be29959425b8734d57b8b4b7d56f98edd9504c9af091d5281095a71e AS node
FROM python:3.12-slim-bookworm@sha256:54c85f3c47607a77f32adec749d3c81d1348bf25833671f512b26a9b6d778cb3
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=managed-runtime /app/.grid-agent/runtime/pi/source/ /opt/pi/
RUN apt-get update && apt-get install --no-install-recommends -y ca-certificates curl git \
    && rm -rf /var/lib/apt/lists/* && pip install --no-cache-dir httpx==0.28.1
WORKDIR /opt/general
COPY packages/capstone-agent/src/capstone_agent/__init__.py capstone_agent/__init__.py
COPY packages/capstone-agent/src/capstone_agent/pi_delegation.py capstone_agent/pi_delegation.py
COPY packages/capstone-agent/src/capstone_agent/general_pi_executor.py capstone_agent/general_pi_executor.py
COPY packages/capstone-agent/src/capstone_agent/general_pi_server.py capstone_agent/general_pi_server.py
COPY packages/capstone-agent/src/capstone_agent/general_pi_storage.py capstone_agent/general_pi_storage.py
COPY packages/capstone-agent/src/capstone_agent/conversation_context.py capstone_agent/conversation_context.py
COPY packages/capstone-agent/src/capstone_agent/request_intent.py capstone_agent/request_intent.py
COPY packages/capstone-agent/src/capstone_agent/resources/general-context.mjs capstone_agent/resources/general-context.mjs
COPY configs/runtime/general-pi/ config/
COPY configs/llm-providers.json llm-providers.json
COPY configs/runtime/pi-runtime.lock.json pi-runtime.lock.json
ENV PYTHONUNBUFFERED=1 CAPSTONE_GENERAL_SANDBOX=container PORT=8790
EXPOSE 8790
CMD ["python", "-m", "capstone_agent.general_pi_server"]
