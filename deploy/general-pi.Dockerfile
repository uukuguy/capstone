ARG CAPSTONE_BACKEND_IMAGE=capstone-backend:local
FROM ${CAPSTONE_BACKEND_IMAGE} AS managed-runtime
FROM node:24.20.0-bookworm-slim@sha256:ba849c60be29959425b8734d57b8b4b7d56f98edd9504c9af091d5281095a71e AS node
FROM python:3.12-slim-bookworm@sha256:54c85f3c47607a77f32adec749d3c81d1348bf25833671f512b26a9b6d778cb3
COPY --from=node /usr/local/bin/node /usr/local/bin/node
RUN apt-get update && apt-get install --no-install-recommends -y ca-certificates curl git nftables \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv==0.10.7 httpx==0.28.1 jsonschema==4.26.0 referencing==0.37.0 mcp==1.30.0
WORKDIR /opt/general

# Scientific packages follow only their lock. Later source and the backend image stay below.
COPY configs/runtime/native-analysis.json configs/runtime/native-analysis.json
COPY configs/runtime/native-analysis.lock.txt configs/runtime/native-analysis.lock.txt
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --require-hashes --only-binary :all: -r configs/runtime/native-analysis.lock.txt
COPY tools/native_analysis_smoke.py tools/native_analysis_smoke.py
RUN apt-get update \
    && python -c 'import json, subprocess; from pathlib import Path; packages=json.loads(Path("configs/runtime/native-analysis.json").read_text())["apt_packages"]; subprocess.run(["apt-get", "install", "--no-install-recommends", "-y", *packages], check=True)' \
    && rm -rf /var/lib/apt/lists/* \
    && python -c 'from pathlib import Path; import re, matplotlib; p=Path(matplotlib.get_data_path()) / "matplotlibrc"; s=re.sub(r"(?m)^#?(backend|font\.family|font\.sans-serif)\s*:.*$", "", p.read_text()); p.write_text(s + "\nbackend: Agg\nfont.family: sans-serif\nfont.sans-serif: Noto Sans CJK SC, DejaVu Sans\n")'

COPY packages/capstone-agent/src/capstone_agent/__init__.py capstone_agent/__init__.py
COPY packages/capstone-agent/src/capstone_agent/runtime_resources.py capstone_agent/runtime_resources.py
COPY packages/capstone-agent/src/capstone_agent/resource_installation.py capstone_agent/resource_installation.py
COPY configs/runtime/power-samples.lock.json configs/runtime/power-samples.lock.json
COPY configs/runtime/prepared-mcp-v1.schema.json configs/runtime/prepared-mcp-v1.schema.json
COPY tools/power_sample_smoke.py tools/power_sample_smoke.py
# Reuse the backend image's downloaded wheels. uv still installs CPython 3.12.12
# into this image so its alias symlink stays inside the native runtime path.
RUN --mount=type=bind,from=managed-runtime,source=/root/.cache/uv,target=/tmp/uv-seed,ro \
    --mount=type=cache,target=/root/.cache/uv \
    cp -a /tmp/uv-seed/. /root/.cache/uv/ \
    && rm -f /root/.cache/uv/.lock \
    && UV_PYTHON_INSTALL_DIR=/opt/general/.grid-agent/runtime/python \
    python -m capstone_agent.resource_installation --config-root configs/runtime \
    && mkdir /opt/general/resource-seed \
    && cp -a /opt/general/.grid-agent/runtime/agent-resources /opt/general/resource-seed/agent-resources \
    && cp -a /opt/general/.grid-agent/runtime/python /opt/general/resource-seed/python \
    && mkdir -p /var/lib/general-pi/tasks /var/lib/general-pi/receipts /var/lib/general-pi/profiles \
    && chmod 0711 /var/lib/general-pi /var/lib/general-pi/tasks \
    && chmod 0700 /var/lib/general-pi/receipts /var/lib/general-pi/profiles

COPY --from=managed-runtime /app/.grid-agent/runtime/pi/source/ /opt/pi/
RUN ln -s /opt/pi/node_modules /opt/general/node_modules
COPY --from=node /usr/local/lib/node_modules/npm/ /usr/local/lib/node_modules/npm/
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && ln -s /opt/pi/node_modules/typescript/bin/tsc /usr/local/bin/tsc \
    && ln -s /opt/pi/node_modules/tsx/dist/cli.mjs /usr/local/bin/tsx
COPY tools/native_report.py tools/native_report.py
RUN chmod 0755 /opt/general/tools/native_report.py \
    && ln -s /opt/general/tools/native_report.py /usr/local/bin/capstone-report
# The smoke checks capstone-report, npm, tsc, and tsx, so it follows those links.
RUN python tools/native_analysis_smoke.py

# Volatile executor and research source.
COPY packages/capstone-agent/src/capstone_agent/application_capacity.py capstone_agent/application_capacity.py
COPY configs/runtime/application-capacity.json capstone_agent/resources/application-capacity.json
COPY packages/capstone-agent/src/capstone_agent/pi_delegation.py capstone_agent/pi_delegation.py
COPY packages/capstone-agent/src/capstone_agent/business_context.py capstone_agent/business_context.py
COPY packages/capstone-agent/src/capstone_agent/general_pi_executor.py capstone_agent/general_pi_executor.py
COPY packages/capstone-agent/src/capstone_agent/native_network_policy.py capstone_agent/native_network_policy.py
COPY packages/capstone-agent/src/capstone_agent/native_environment.py capstone_agent/native_environment.py
COPY packages/capstone-agent/src/capstone_agent/general_pi_server.py capstone_agent/general_pi_server.py
COPY packages/capability-agent-kernel/src/capability_agent/runtime/step_events.py capstone_runtime_events.py
COPY packages/capstone-agent/src/capstone_agent/general_pi_storage.py capstone_agent/general_pi_storage.py
COPY packages/capstone-agent/src/capstone_agent/general_pi_relay.py capstone_agent/general_pi_relay.py
COPY packages/capstone-agent/src/capstone_agent/data_gateway_mcp.py capstone_agent/data_gateway_mcp.py
COPY packages/capstone-agent/src/capstone_agent/data_gateway_relay.py capstone_agent/data_gateway_relay.py
COPY packages/capstone-agent/src/capstone_agent/resources/general-data-gateway.mjs capstone_agent/resources/general-data-gateway.mjs
COPY configs/runtime/data-gateway.json configs/runtime/data-gateway.json
COPY packages/capstone-agent/src/capstone_agent/bounded_http_loop.py capstone_agent/bounded_http_loop.py
COPY packages/capstone-agent/src/capstone_agent/conversation_context.py capstone_agent/conversation_context.py
COPY packages/capstone-agent/src/capstone_agent/request_intent.py capstone_agent/request_intent.py
COPY packages/capstone-agent/src/capstone_agent/native_task_context.py capstone_agent/native_task_context.py
COPY packages/capstone-agent/src/capstone_agent/resources/research-policy-catalog.json capstone_agent/resources/research-policy-catalog.json
COPY packages/capstone-agent/src/capstone_agent/resources/graph-work-policy-1.12.json capstone_agent/resources/graph-work-policy-1.12.json
COPY packages/capstone-agent/src/capstone_agent/resources/graph-work-policy-1.16.json capstone_agent/resources/graph-work-policy-1.16.json
COPY packages/capstone-agent/src/capstone_agent/task_planning_policy.py capstone_agent/task_planning_policy.py
COPY packages/capstone-agent/src/capstone_agent/resources/task-planning-policy-*.md capstone_agent/resources/
COPY packages/capstone-agent/src/capstone_agent/progress.py capstone_agent/progress.py
COPY packages/capstone-agent/src/capstone_agent/stream_progress.py capstone_agent/stream_progress.py
COPY packages/capstone-agent/src/capstone_agent/resource_manifest.py capstone_agent/resource_manifest.py
COPY packages/capstone-agent/src/capstone_agent/continuation_resources.py capstone_agent/continuation_resources.py
COPY packages/capstone-agent/src/capstone_agent/native_resource_staging.py capstone_agent/native_resource_staging.py
COPY packages/capstone-agent/src/capstone_agent/native_document_types.py capstone_agent/native_document_types.py
COPY packages/capstone-agent/src/capstone_agent/native_product_roles.py capstone_agent/native_product_roles.py
COPY packages/capstone-agent/src/capstone_agent/native_research_bridge.py capstone_agent/native_research_bridge.py
COPY packages/capstone-agent/src/capstone_agent/native_graph_context.py capstone_agent/native_graph_context.py
COPY packages/capstone-agent/src/capstone_agent/native_graph_events.py capstone_agent/native_graph_events.py
COPY packages/enterprise-research-domain-pack/src/enterprise_research/ enterprise_research/
COPY packages/pi-capability-tools/src/research-tools.mjs capstone_agent/resources/research-tools.mjs
COPY packages/pi-capability-tools/src/research-runtime/ capstone_agent/resources/research-runtime/
COPY packages/pi-capability-tools/src/runtime-limits.mjs capstone_agent/resources/runtime-limits.mjs
COPY packages/pi-capability-tools/src/execution-guidance.mjs capstone_agent/resources/execution-guidance.mjs
COPY packages/pi-capability-tools/src/model-request-capture.mjs capstone_agent/resources/model-request-capture.mjs
COPY packages/capstone-agent/src/capstone_agent/resources/general-research.mjs capstone_agent/resources/general-research.mjs
COPY packages/capstone-agent/src/capstone_agent/resources/research-guidance.mjs capstone_agent/resources/research-guidance.mjs
COPY packages/pi-capability-tools/src/task-record-tools.mjs capstone_agent/resources/task-record-tools.mjs
COPY packages/capstone-agent/src/capstone_agent/resources/general-context.mjs capstone_agent/resources/general-context.mjs
COPY packages/capstone-agent/src/capstone_agent/resources/general-sdk.mjs capstone_agent/resources/general-sdk.mjs
COPY packages/capstone-agent/src/capstone_agent/resources/enterprise-research-runtime.mjs capstone_agent/resources/enterprise-research-runtime.mjs
COPY packages/capstone-agent/src/capstone_agent/resources/enterprise-cycle-contract.mjs capstone_agent/resources/enterprise-cycle-contract.mjs
COPY packages/capstone-agent/src/capstone_agent/resources/enterprise-cycle-state.mjs capstone_agent/resources/enterprise-cycle-state.mjs
COPY packages/capstone-agent/src/capstone_agent/resources/enterprise-graph-contract.mjs capstone_agent/resources/enterprise-graph-contract.mjs
COPY packages/capstone-agent/src/capstone_agent/resources/enterprise-graph-state.mjs capstone_agent/resources/enterprise-graph-state.mjs
COPY packages/capstone-agent/src/capstone_agent/resources/enterprise-graph-runtime.mjs capstone_agent/resources/enterprise-graph-runtime.mjs
COPY packages/capstone-agent/src/capstone_agent/resources/task-goal-state.mjs capstone_agent/resources/task-goal-state.mjs
COPY packages/capstone-agent/src/capstone_agent/resources/task-node-return.mjs capstone_agent/resources/task-node-return.mjs
COPY packages/capstone-agent/src/capstone_agent/resources/task-turn-guidance.mjs capstone_agent/resources/task-turn-guidance.mjs
COPY packages/capstone-agent/src/capstone_agent/resources/research-context-window.mjs capstone_agent/resources/research-context-window.mjs
COPY packages/capstone-agent/src/capstone_agent/resources/graph-context-client.mjs capstone_agent/resources/graph-context-client.mjs
COPY packages/capstone-agent/src/capstone_agent/resources/research-products.mjs capstone_agent/resources/research-products.mjs
COPY packages/capstone-agent/src/capstone_agent/resources/delivery-review.mjs capstone_agent/resources/delivery-review.mjs
COPY packages/capstone-agent/src/capstone_agent/resources/product-path-policy.json capstone_agent/resources/product-path-policy.json
COPY packages/capstone-agent/src/capstone_agent/resources/managed-subagents.mjs capstone_agent/resources/managed-subagents.mjs
COPY packages/capstone-agent/src/capstone_agent/resources/delegation-tool.mjs capstone_agent/resources/delegation-tool.mjs
COPY packages/capstone-agent/src/capstone_agent/resources/delegation-scheduler.mjs capstone_agent/resources/delegation-scheduler.mjs
COPY packages/capstone-agent/src/capstone_agent/resources/subagents/ capstone_agent/resources/subagents/
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
RUN python -c "from capstone_agent.general_pi_executor import collect_artifacts; from capstone_agent.native_product_roles import read_product_roles" \
    && python -c 'from capstone_agent.native_task_context import checked_native_context, RESEARCH_POLICY_TEXT, SPLIT_RESEARCH_POLICY_TEXT; [checked_native_context({"selected_task_records": [], "selected_task_source": None, "records_truncated": False, "policy": {"schema": "capstone-conversation-policy/1", "system_policy": policy, "allowed_tools": tools, "external_lookup_enabled": False}}) for policy, tools in [(RESEARCH_POLICY_TEXT, ["agent_research_cycle"]), (SPLIT_RESEARCH_POLICY_TEXT, ["agent_research_plan", "agent_research_record", "agent_research_assess"])]]' \
    && python -c 'from capstone_agent.native_task_context import checked_native_context, REVIEWED_RESEARCH_POLICY_TEXT; checked_native_context({"selected_task_records": [], "selected_task_source": None, "records_truncated": False, "policy": {"schema": "capstone-conversation-policy/1", "system_policy": REVIEWED_RESEARCH_POLICY_TEXT, "allowed_tools": ["agent_research_plan", "agent_research_record", "agent_research_assess"], "external_lookup_enabled": False}})' \
    && python -c 'from capstone_agent.native_task_context import checked_native_context, registered_research_policies; [checked_native_context({"selected_task_records": [], "selected_task_source": None, "records_truncated": False, **({"graph_work": {"edition": entry.work_edition, "started_at_ms": 1792562400000}} if entry.work_edition else {}), "policy": {"schema": "capstone-conversation-policy/1", "system_policy": entry.system_policy, "allowed_tools": ["agent_research_cycle"] if entry.application_version == "1.1.0" else ["agent_research_plan", "agent_research_record", "agent_research_assess"], "external_lookup_enabled": False}}) for entry in registered_research_policies()]' \
    && python -c 'from capstone_agent.native_task_context import registered_research_policies; from enterprise_research import ResearchPolicy; [entry.capability() for entry in registered_research_policies()]; [(entry.work_policy(), ResearchPolicy(entry.pack_version, variant=entry.variant).progress_guidance()) for entry in registered_research_policies() if entry.work_edition]' \
    && node --check capstone_agent/resources/research-guidance.mjs \
    && node --input-type=module -e 'await import("./capstone_agent/resources/delivery-review.mjs")'
EXPOSE 8790
CMD ["python", "-m", "capstone_agent.general_pi_resource_seed"]
