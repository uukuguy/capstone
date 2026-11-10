ARG CAPSTONE_BACKEND_IMAGE=capstone-backend:local

FROM ${CAPSTONE_BACKEND_IMAGE} AS managed-runtime

FROM node:24.20.0-bookworm-slim@sha256:ba849c60be29959425b8734d57b8b4b7d56f98edd9504c9af091d5281095a71e AS node

FROM python:3.12-slim-bookworm@sha256:54c85f3c47607a77f32adec749d3c81d1348bf25833671f512b26a9b6d778cb3

COPY --from=node /usr/local/bin/node /usr/local/bin/node

RUN apt-get update && apt-get install --no-install-recommends -y ca-certificates curl git nftables && rm -rf /var/lib/apt/lists/* && pip install --no-cache-dir uv==0.10.7 httpx==0.28.1 jsonschema==4.26.0 referencing==0.37.0 mcp==1.30.0

WORKDIR /opt/general

COPY configs/runtime/native-analysis.json configs/runtime/native-analysis.lock.txt configs/runtime/

RUN --mount=type=cache,target=/root/.cache/uv uv pip install --system --require-hashes --only-binary :all: -r configs/runtime/native-analysis.lock.txt

RUN apt-get update && python -c 'import json, subprocess; from pathlib import Path; packages=json.loads(Path("configs/runtime/native-analysis.json").read_text())["apt_packages"]; subprocess.run(["apt-get", "install", "--no-install-recommends", "-y", *packages], check=True)' && rm -rf /var/lib/apt/lists/* && python -c 'from pathlib import Path; import re, matplotlib; p=Path(matplotlib.get_data_path()) / "matplotlibrc"; s=re.sub(r"(?m)^#?(backend|font\.family|font\.sans-serif)\s*:.*$", "", p.read_text()); p.write_text(s + "\nbackend: Agg\nfont.family: sans-serif\nfont.sans-serif: Noto Sans CJK SC, DejaVu Sans\n")'

COPY packages/capability-agent-kernel/src/capability_agent/runtime/execution_queue.py capability_agent/runtime/execution_queue.py

RUN mkdir -p /var/lib/general-pi/tasks /var/lib/general-pi/receipts /var/lib/general-pi/profiles /run/capstone-private \
    && chmod 0711 /var/lib/general-pi /var/lib/general-pi/tasks \
    && chmod 0700 /var/lib/general-pi/receipts /var/lib/general-pi/profiles /run/capstone-private

COPY --from=managed-runtime /app/.grid-agent/runtime/pi/source/ /opt/pi/

COPY --from=node /usr/local/lib/node_modules/npm/ /usr/local/lib/node_modules/npm/

RUN ln -s /opt/pi/node_modules /opt/general/node_modules \
    && ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && ln -s /opt/pi/node_modules/typescript/bin/tsc /usr/local/bin/tsc \
    && ln -s /opt/pi/node_modules/tsx/dist/cli.mjs /usr/local/bin/tsx

# Report tools and smoke checks: changes do not reinstall system packages.

COPY tools/native_analysis_smoke.py \
     tools/native_report.py \
     tools/native_presentation_library.py \
     tools/native_presentation_template.py \
     tools/native_presentation_layout.py tools/

COPY tools/presentation-templates/ tools/presentation-templates/

RUN chmod 0755 /opt/general/tools/native_report.py /opt/general/tools/native_presentation_library.py \
    && ln -s /opt/general/tools/native_report.py /usr/local/bin/capstone-report \
    && ln -s /opt/general/tools/native_presentation_library.py /usr/local/bin/capstone-presentation

RUN python tools/native_analysis_smoke.py

# Frequently changed application modules: explicit allowlist, one layer.

COPY packages/capstone-agent/src/capstone_agent/__init__.py \
     packages/capstone-agent/src/capstone_agent/tool_execution_receipt.py \
     packages/capstone-agent/src/capstone_agent/presentation_template_contract.py \
     packages/capstone-agent/src/capstone_agent/native_presentation_tasks.py \
     packages/capstone-agent/src/capstone_agent/runtime_resources.py \
     packages/capstone-agent/src/capstone_agent/resource_installation.py \
     packages/capstone-agent/src/capstone_agent/application_capacity.py \
     packages/capstone-agent/src/capstone_agent/model_context_policy.py \
     packages/capstone-agent/src/capstone_agent/pi_delegation.py \
     packages/capstone-agent/src/capstone_agent/business_context.py \
     packages/capstone-agent/src/capstone_agent/answer_presentation.py \
     packages/capstone-agent/src/capstone_agent/native_network_policy.py \
     packages/capstone-agent/src/capstone_agent/native_environment.py \
     packages/capstone-agent/src/capstone_agent/resource_permissions.py \
     packages/capstone-agent/src/capstone_agent/capacity_contract.py \
     packages/capstone-agent/src/capstone_agent/general_pi_executor.py \
     packages/capstone-agent/src/capstone_agent/general_pi_server.py \
     packages/capstone-agent/src/capstone_agent/skill_activity.py \
     packages/capstone-agent/src/capstone_agent/general_pi_storage.py \
     packages/capstone-agent/src/capstone_agent/general_pi_relay.py \
     packages/capstone-agent/src/capstone_agent/native_timing.py \
     packages/capstone-agent/src/capstone_agent/data_gateway_mcp.py \
     packages/capstone-agent/src/capstone_agent/data_gateway_relay.py \
     packages/capstone-agent/src/capstone_agent/domain_tool_client.py \
     packages/capstone-agent/src/capstone_agent/domain_tool_grant.py \
     packages/capstone-agent/src/capstone_agent/data_gateway_views.py \
     packages/capstone-agent/src/capstone_agent/gateway_connections.py \
     packages/capstone-agent/src/capstone_agent/gateway_connections_runtime.py \
     packages/capstone-agent/src/capstone_agent/gateway_diagnostics.py \
     packages/capstone-agent/src/capstone_agent/grid_source_topology.py \
     packages/capstone-agent/src/capstone_agent/grid_electrical_view.py \
     packages/capstone-agent/src/capstone_agent/incremental_artifacts.py \
     packages/capstone-agent/src/capstone_agent/native_llm_pool.py \
     packages/capstone-agent/src/capstone_agent/native_model_request_pool.py \
     packages/capstone-agent/src/capstone_agent/bounded_http_loop.py \
     packages/capstone-agent/src/capstone_agent/conversation_context.py \
     packages/capstone-agent/src/capstone_agent/request_intent.py \
     packages/capstone-agent/src/capstone_agent/native_task_context.py \
     packages/capstone-agent/src/capstone_agent/native_diagnosis.py \
     packages/capstone-agent/src/capstone_agent/native_tool_composition.py \
     packages/capstone-agent/src/capstone_agent/task_planning_policy.py \
     packages/capstone-agent/src/capstone_agent/progress.py \
     packages/capstone-agent/src/capstone_agent/native_tool_diagnostics.py \
     packages/capstone-agent/src/capstone_agent/stream_progress.py \
     packages/capstone-agent/src/capstone_agent/resource_manifest.py \
     packages/capstone-agent/src/capstone_agent/continuation_resources.py \
     packages/capstone-agent/src/capstone_agent/native_resource_staging.py \
     packages/capstone-agent/src/capstone_agent/native_resource_references.py \
     packages/capstone-agent/src/capstone_agent/native_document_types.py \
     packages/capstone-agent/src/capstone_agent/native_product_roles.py \
     packages/capstone-agent/src/capstone_agent/native_research_bridge.py \
     packages/capstone-agent/src/capstone_agent/native_graph_context.py \
     packages/capstone-agent/src/capstone_agent/native_graph_events.py \
     packages/capstone-agent/src/capstone_agent/native_resources.py \
     packages/capstone-agent/src/capstone_agent/session_skill_preferences.py \
     packages/capstone-agent/src/capstone_agent/bounded_mcp.py \
     packages/capstone-agent/src/capstone_agent/general_pi_resource_seed.py \
     packages/capstone-agent/src/capstone_agent/workbench_llm_profiles.py \
     packages/capstone-agent/src/capstone_agent/native_failure_origin.py \
     packages/capstone-agent/src/capstone_agent/runtime_cleanup.py \
     packages/capstone-agent/src/capstone_agent/managed_resource*.py \
     packages/capstone-agent/src/capstone_agent/workspace_scope.py capstone_agent/

# Application resources and policy files: explicit allowlist, one layer.

COPY configs/runtime/application-capacity.json \
     packages/capstone-agent/src/capstone_agent/resources/gateway-electrical-view-v1.schema.json \
     packages/capstone-agent/src/capstone_agent/resources/gateway-electrical-view-v2.schema.json \
     packages/capstone-agent/src/capstone_agent/resources/general-data-gateway.mjs \
     packages/capstone-agent/src/capstone_agent/resources/general-domain-tools.mjs \
     packages/capstone-agent/src/capstone_agent/resources/resource-reference-tools.mjs \
     packages/capstone-agent/src/capstone_agent/resources/managed-resource-tools.mjs \
     packages/capstone-agent/src/capstone_agent/resources/presentation-templates.mjs \
     packages/capstone-agent/src/capstone_agent/resources/investigation-skills.mjs \
     packages/capstone-agent/src/capstone_agent/resources/tool-result-context.mjs \
     packages/capstone-agent/src/capstone_agent/resources/async-call-pool.mjs \
     packages/capstone-agent/src/capstone_agent/resources/llm-call-tools.mjs \
     packages/capstone-agent/src/capstone_agent/resources/llm-call-pool-policy.json \
     packages/capstone-agent/src/capstone_agent/resources/model-request-pool.mjs \
     packages/capstone-agent/src/capstone_agent/resources/model-request-pool-policy.json \
     packages/capstone-agent/src/capstone_agent/resources/committed-delivery.mjs \
     packages/capstone-agent/src/capstone_agent/resources/research-policy-catalog.json \
     packages/capstone-agent/src/capstone_agent/resources/graph-work-policy-1.12.json \
     packages/capstone-agent/src/capstone_agent/resources/graph-work-policy-1.16.json \
     packages/capstone-agent/src/capstone_agent/resources/task-planning-policy-*.md \
     packages/pi-capability-tools/src/research-tools.mjs \
     packages/pi-capability-tools/src/runtime-limits.mjs \
     packages/pi-capability-tools/src/execution-guidance.mjs \
     packages/pi-capability-tools/src/model-request-capture.mjs \
     packages/capstone-agent/src/capstone_agent/resources/general-research.mjs \
     packages/capstone-agent/src/capstone_agent/resources/research-guidance.mjs \
     packages/pi-capability-tools/src/task-record-tools.mjs \
     packages/capstone-agent/src/capstone_agent/resources/general-context.mjs \
     packages/capstone-agent/src/capstone_agent/resources/general-sdk.mjs \
     packages/capstone-agent/src/capstone_agent/resources/tool-composition.mjs \
     packages/capstone-agent/src/capstone_agent/resources/tool-composition-worker.mjs \
     packages/capstone-agent/src/capstone_agent/resources/tool-call-scheduler.mjs \
     packages/capstone-agent/src/capstone_agent/resources/tool-composition-policy.json \
     packages/capstone-agent/src/capstone_agent/resources/semantic-data-context.mjs \
     packages/capstone-agent/src/capstone_agent/resources/observation-data.mjs \
     packages/capstone-agent/src/capstone_agent/resources/observation-read-budget.mjs \
     packages/capstone-agent/src/capstone_agent/resources/observed-action.mjs \
     packages/capstone-agent/src/capstone_agent/resources/general-tool-discovery.mjs \
     packages/capstone-agent/src/capstone_agent/resources/tool-identity.mjs \
     packages/capstone-agent/src/capstone_agent/resources/gateway-tool-use.mjs \
     packages/capstone-agent/src/capstone_agent/resources/systematic-diagnosis.mjs \
     packages/capstone-agent/src/capstone_agent/resources/enterprise-research-runtime.mjs \
     packages/capstone-agent/src/capstone_agent/resources/enterprise-cycle-contract.mjs \
     packages/capstone-agent/src/capstone_agent/resources/enterprise-cycle-state.mjs \
     packages/capstone-agent/src/capstone_agent/resources/enterprise-graph-contract.mjs \
     packages/capstone-agent/src/capstone_agent/resources/enterprise-graph-state.mjs \
     packages/capstone-agent/src/capstone_agent/resources/enterprise-graph-runtime.mjs \
     packages/capstone-agent/src/capstone_agent/resources/task-goal-state.mjs \
     packages/capstone-agent/src/capstone_agent/resources/task-node-return.mjs \
     packages/capstone-agent/src/capstone_agent/resources/task-turn-guidance.mjs \
     packages/capstone-agent/src/capstone_agent/resources/research-context-window.mjs \
     packages/capstone-agent/src/capstone_agent/resources/graph-context-client.mjs \
     packages/capstone-agent/src/capstone_agent/resources/research-products.mjs \
     packages/capstone-agent/src/capstone_agent/resources/delivery-review.mjs \
     packages/capstone-agent/src/capstone_agent/resources/product-path-policy.json \
     packages/capstone-agent/src/capstone_agent/resources/managed-subagents.mjs \
     packages/capstone-agent/src/capstone_agent/resources/delegation-tool.mjs \
     packages/capstone-agent/src/capstone_agent/resources/delegation-scheduler.mjs \
     packages/capstone-agent/src/capstone_agent/resources/general-mcp.mjs capstone_agent/resources/

COPY configs/runtime/capacity-policy.json configs/runtime/capacity-policy.json

COPY configs/runtime/resource-permissions.json configs/runtime/resource-permissions.json

COPY packages/capability-agent-kernel/src/capability_agent/runtime/step_events.py capstone_runtime_events.py

RUN python -c 'from capstone_agent.gateway_diagnostics import checked_diagnostics; assert checked_diagnostics(None) is None'

COPY configs/runtime/data-gateway.json configs/runtime/data-gateway.json

COPY packages/enterprise-research-domain-pack/src/enterprise_research/ enterprise_research/

COPY packages/pi-capability-tools/src/research-runtime/ capstone_agent/resources/research-runtime/

COPY packages/capstone-agent/src/capstone_agent/resources/subagents/ capstone_agent/resources/subagents/

COPY configs/runtime/general-pi/ config/

COPY configs/runtime/general-pi/ configs/runtime/general-pi/

COPY configs/runtime/capstone-pi/settings.json configs/runtime/capstone-pi/settings.json

COPY configs/runtime/agent-resources.json configs/runtime/agent-resources.json

COPY configs/llm-providers.json llm-providers.json

COPY configs/runtime/pi-runtime.lock.json pi-runtime.lock.json

ENV PYTHONUNBUFFERED=1 CAPSTONE_GENERAL_SANDBOX=container PORT=8790

RUN python -c "from capstone_agent.general_pi_executor import collect_artifacts; from capstone_agent.native_product_roles import read_product_roles; from capstone_agent.session_skill_preferences import scoped_skill_names" && python -c 'from capstone_agent.native_task_context import checked_native_context, RESEARCH_POLICY_TEXT, SPLIT_RESEARCH_POLICY_TEXT; [checked_native_context({"selected_task_records": [], "selected_task_source": None, "records_truncated": False, "policy": {"schema": "capstone-conversation-policy/1", "system_policy": policy, "allowed_tools": tools, "external_lookup_enabled": False}}) for policy, tools in [(RESEARCH_POLICY_TEXT, ["agent_research_cycle"]), (SPLIT_RESEARCH_POLICY_TEXT, ["agent_research_plan", "agent_research_record", "agent_research_assess"])]]' && python -c 'from capstone_agent.native_task_context import checked_native_context, REVIEWED_RESEARCH_POLICY_TEXT; checked_native_context({"selected_task_records": [], "selected_task_source": None, "records_truncated": False, "policy": {"schema": "capstone-conversation-policy/1", "system_policy": REVIEWED_RESEARCH_POLICY_TEXT, "allowed_tools": ["agent_research_plan", "agent_research_record", "agent_research_assess"], "external_lookup_enabled": False}})' && python -c 'from capstone_agent.native_task_context import checked_native_context, registered_research_policies; [checked_native_context({"selected_task_records": [], "selected_task_source": None, "records_truncated": False, **({"graph_work": {"edition": entry.work_edition, "started_at_ms": 1792562400000}} if entry.work_edition else {}), "policy": {"schema": "capstone-conversation-policy/1", "system_policy": entry.system_policy, "allowed_tools": ["agent_research_cycle"] if entry.application_version == "1.1.0" else ["agent_research_plan", "agent_research_record", "agent_research_assess"], "external_lookup_enabled": False}}) for entry in registered_research_policies()]' && python -c 'from capstone_agent.native_task_context import registered_research_policies; from enterprise_research import ResearchPolicy; [entry.capability() for entry in registered_research_policies()]; [(entry.work_policy(), ResearchPolicy(entry.pack_version, variant=entry.variant).progress_guidance()) for entry in registered_research_policies() if entry.work_edition]' && node --check capstone_agent/resources/research-guidance.mjs && node --input-type=module -e 'await import("./capstone_agent/resources/general-sdk.mjs"); await import("./capstone_agent/resources/delivery-review.mjs"); await import("./capstone_agent/resources/systematic-diagnosis.mjs")'

COPY configs/runtime/workbench-llm-profiles.json configs/runtime/workbench-llm-profiles.json

EXPOSE 8790

CMD ["python", "-m", "capstone_agent.general_pi_resource_seed"]
