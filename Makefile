.DEFAULT_GOAL := help

.PHONY: help setup setup-agent setup-capstone setup-capstone-app setup-simulator setup-pypsa setup-tools setup-workbench build-workbench build-capstone-app test-workbench test-capstone-app check-workbench install-pi auth-import-pi auth-login doctor run run-llm analysis analysis-generic application capstone-client capstone-agent-run capstone-agent-case capstone-agent-pandapower-task capstone-agent-pandapower-test capstone-agent-pypsa-regional capstone-agent-pypsa-scigrid capstone-agent-pypsa-ac-dc capstone-agent-chat capstone-agent-serve capstone-app-dev report trajectory test test-agent test-capstone-agent test-capstone-client test-makefile-application test-verification-targets test-inventory test-inventory-service test-inventory-domain test-inventory-pi test-pypsa test-simulator test-tools test-e2e validate validate-application validate-provider test-kernel test-domain-package test-generic-tools check-types check-fast check-integration check-release check-runtime-risk check-package-boundaries check-application-boundaries check-protected-paths test-packages test-source-setup test-pi-capture-runtime list-pypsa-models install-pypsa-models list-pypsa-cases run-pypsa-case

help:
	@echo "Grid Static Analysis commands"
	@echo "  make setup                 Install all local dependencies"
	@echo "  make doctor                Inspect local runtime readiness"
	@echo "  make run QUESTION='...'    Run a local deterministic smoke/offline check"
	@echo "  make run-llm QUESTION='...'  Primary natural-language agent path via Pi/LLM"
	@echo "  make analysis [INSTRUCTIONS=...]  Compatibility analysis report; default TASK instruction set"
	@echo "  make analysis-generic APPLICATION=... INSTRUCTIONS=...  Generic composite application output"
	@echo "  make application [INSTRUCTIONS=...] [PROVIDER=...] [MODEL=...]  Run the formal registered application"
	@echo "  make capstone-client REQUEST=path  Run a registered pandapower or PyPSA client request"
	@echo "  make capstone-agent-run REQUEST=path  Run a registered application headlessly"
	@echo "  make capstone-agent-case CASE=id  Run one of the five catalog cases with the real Provider/LLM path"
	@echo "    CASE=pandapower-scripted-task | pandapower-scripted-test"
	@echo "    CASE=regional-demand-stress | scigrid-dispatch | ac-dc-interconnection"
	@echo "  make capstone-agent-pandapower-task  Run IEEE-39 潮流与线路筛查"
	@echo "  make capstone-agent-pandapower-test  Run IEEE-39 约束与单支路校核"
	@echo "  make capstone-agent-pypsa-regional   Run 区域负荷增长情景"
	@echo "  make capstone-agent-pypsa-scigrid     Run 德国输电网日内调度概览"
	@echo "  make capstone-agent-pypsa-ac-dc       Run AC/DC 跨区互联结构核查"
	@echo "  make capstone-agent-chat APPLICATION=id [MODE=provider] [CASE=id]  Open one interactive run"
	@echo "  make capstone-agent-serve [CAPSTONE_PORT=8766]  Start local HTTP/SSE sessions"
	@echo "  make capstone-app-dev [CAPSTONE_APP_HOST=0.0.0.0] [CAPSTONE_APP_PORT=5173]  Start the App dev server"
	@echo "  make build-capstone-app    Build the Vercel-ready static App"
	@echo "  make test-capstone-app     Run focused App tests"
	@echo "  make report [INSTRUCTIONS=...]  Compatibility alias for make analysis"
	@echo "  make build-workbench         Build packaged trajectory workbench assets"
	@echo "  make trajectory [PORT=8765]  Build and serve the local trajectory workbench"
	@echo "  make install-pi            Install the pinned Pi runtime"
	@echo "  make auth-import-pi        Import local Pi Codex OAuth to this project"
	@echo "  make auth-login            Log in to Pi Codex OAuth for this project"
	@echo "  make test                  Run all offline verification"
	@echo "  make test-inventory-service  Test the read-only inventory authority"
	@echo "  make test-inventory-domain   Test the inventory Domain Pack SPI"
	@echo "  make test-inventory-pi       Test unchanged generic Pi with inventory tools"
	@echo "  make test-inventory          Run all inventory reference-domain tests"
	@echo "  make list-pypsa-models       List registered PyPSA model assets and install state"
	@echo "  make install-pypsa-models    Install all six checked PyPSA example Networks"
	@echo "  make list-pypsa-cases        List local PyPSA business cases"
	@echo "  make run-pypsa-case CASE=... [DEMO=1 | INSTRUCTIONS=path]  Run a scripted PyPSA case"
	@echo "  make test-e2e              Run offline CLI and scripted Pi-to-gridctl scenarios"
	@echo "  make validate              Run deterministic WP-A validation"
	@echo "  make validate-application  Run provider-free generic application instantiation validation"
	@echo "  make validate-provider PROVIDER=... [MODEL=...]  Run optional billed provider validation"
	@echo "  make check-application-boundaries  Verify generic application ownership boundaries"
	@echo "  Manual: docs/MANUAL-VALIDATION.md (human verification for every entry above)"

setup: setup-agent setup-capstone setup-capstone-app setup-simulator setup-pypsa setup-tools setup-workbench build-workbench

setup-agent:
	uv sync --project packages/grid-agent

setup-capstone:
	uv sync --project packages/capstone-agent
	uv sync --project packages/pypsa-agent

setup-capstone-app:
	npm ci --prefix packages/capstone-app

build-capstone-app:
	npm run build --prefix packages/capstone-app

test-capstone-app:
	npm test --prefix packages/capstone-app

capstone-app-dev:
	npm run dev --prefix packages/capstone-app -- --host "$(if $(CAPSTONE_APP_HOST),$(CAPSTONE_APP_HOST),127.0.0.1)" --port "$(if $(CAPSTONE_APP_PORT),$(CAPSTONE_APP_PORT),5173)"

setup-simulator:
	uv sync --project packages/grid-simulator

setup-pypsa:
	uv sync --project packages/pypsa-sector-coupling-domain-pack
	uv sync --project packages/pypsa-capacity-planning-domain-pack
	uv sync --project packages/pypsa-power-operations-domain-pack

list-pypsa-models:
	uv run --project packages/pypsa-sector-coupling-domain-pack python -m pypsa_model_authority.model_library list

install-pypsa-models:
	uv run --project packages/pypsa-sector-coupling-domain-pack python -m pypsa_model_authority.model_library install --all

list-pypsa-cases:
	uv run --project packages/pypsa-power-operations-domain-pack python validation/pypsa_cases.py list

run-pypsa-case:
	@uv run --project packages/pypsa-power-operations-domain-pack python validation/pypsa_cases.py run "$(CASE)" $(if $(DEMO),--demo) $(if $(INSTRUCTIONS),--instructions "$(INSTRUCTIONS)")

capstone-client:
	@test -n "$(REQUEST)" || (echo "Usage: make capstone-client REQUEST=path" >&2; exit 2)
	@python3 tools/capstone_client.py --request "$(REQUEST)"

capstone-agent-run:
	@test -n "$(REQUEST)" || (echo "Usage: make capstone-agent-run REQUEST=path" >&2; exit 2)
	@uv run --project packages/capstone-agent capstone-agent run --request "$(REQUEST)"

capstone-agent-case:
	@test -n "$(CASE)" || (echo "Usage: make capstone-agent-case CASE=<registered-case-id>" >&2; exit 2)
	@request="validation/client/$(CASE).json"; \
	case "$(CASE)" in \
		pandapower-scripted-task) request="validation/client/pandapower-task.json" ;; \
		pandapower-scripted-test) request="validation/client/pandapower-test.json" ;; \
		regional-demand-stress) request="validation/client/pypsa-regional.json" ;; \
		scigrid-dispatch) request="validation/client/pypsa-scigrid.json" ;; \
		ac-dc-interconnection) request="validation/client/pypsa-ac-dc.json" ;; \
	esac; \
	test -f "$$request" || { echo "Unknown case or missing request: $(CASE)" >&2; exit 2; }; \
	$(MAKE) capstone-agent-run REQUEST="$$request"

capstone-agent-pandapower-task:
	@$(MAKE) capstone-agent-case CASE=pandapower-scripted-task

capstone-agent-pandapower-test:
	@$(MAKE) capstone-agent-case CASE=pandapower-scripted-test

capstone-agent-pypsa-regional:
	@$(MAKE) capstone-agent-case CASE=regional-demand-stress

capstone-agent-pypsa-scigrid:
	@$(MAKE) capstone-agent-case CASE=scigrid-dispatch

capstone-agent-pypsa-ac-dc:
	@$(MAKE) capstone-agent-case CASE=ac-dc-interconnection

capstone-agent-chat:
	@test -n "$(APPLICATION)" || (echo "Usage: make capstone-agent-chat APPLICATION=id [MODE=provider] [CASE=id]" >&2; exit 2)
	@uv run --project packages/capstone-agent capstone-agent chat --application "$(APPLICATION)" --mode "$(if $(MODE),$(MODE),provider)" $(if $(CASE),--case "$(CASE)") $(if $(PROVIDER),--provider "$(PROVIDER)") $(if $(MODEL),--model "$(MODEL)")

capstone-agent-serve:
	@uv run --project packages/capstone-agent capstone-agent serve --host 127.0.0.1 --port "$(CAPSTONE_PORT)"

setup-tools:
	npm ci --prefix packages/pi-capability-tools
	npm ci --prefix packages/pi-grid-tools

setup-workbench:
	npm ci --prefix packages/trajectory-workbench

build-workbench:
	npm run build --prefix packages/trajectory-workbench

test-workbench: check-workbench
	npm test --prefix packages/trajectory-workbench

check-workbench:
	npm run check --prefix packages/trajectory-workbench

install-pi:
	uv run --project packages/grid-agent grid-agent install-pi

auth-import-pi:
	uv run --project packages/grid-agent grid-agent auth-import-pi

auth-login:
	uv run --project packages/grid-agent grid-agent auth-login

doctor:
	uv run --project packages/grid-agent grid-agent doctor --json

QUESTION ?= IEEE-39节点系统中线路11连接哪两个母线?
# QUESTION ?= 母线电压正常运行范围是多少?
# QUESTION ?= N-1静态安全校核需要检查哪些越限类型?
# QUESTION ?= ‘潮流计算工具（pandapower runpp）需要输入哪些参数？’
# QUESTION ?= 对IEEE-39节点系统运行交流潮流，并输出有功网损;
# QUESTION ?= 筛选负载率最高的5条线路
# QUESTION ?= 对线路17开展N-1校核
# QUESTION ?= 母线低电压、线路过载等风险及证据（仿真结果）
#
run:
	@test -n "$(QUESTION)" || (echo "Usage: make run QUESTION='IEEE-39节点系统中线路11连接哪两个母线?'" >&2; exit 2)
	uv run --project packages/grid-agent grid-agent run --offline "$(QUESTION)"

run-llm:
	@test -n "$(QUESTION)" || (echo "Usage: make run-llm QUESTION='...' [PROVIDER=openai]" >&2; exit 2)
	uv run --project packages/grid-agent grid-agent run $(if $(PROVIDER),--provider "$(PROVIDER)") "$(QUESTION)"

ANALYSIS_DEFAULT_INSTRUCTIONS ?= validation/questions/task.md.txt

analysis:
	@instruction_file="$(if $(INSTRUCTIONS),$(INSTRUCTIONS),$(ANALYSIS_DEFAULT_INSTRUCTIONS))"; test -f "$$instruction_file" || (echo "Instruction file not found: $$instruction_file" >&2; exit 2); uv run --project packages/grid-agent grid-agent analysis --instructions "$$instruction_file" $(if $(PROVIDER),--provider "$(PROVIDER)") $(if $(MODEL),--model "$(MODEL)")

analysis-generic:
	@test -n "$(APPLICATION)" || (echo "Usage: make analysis-generic APPLICATION=... INSTRUCTIONS=... [PROVIDER=...] [MODEL=...]" >&2; exit 2)
	@test -n "$(INSTRUCTIONS)" || (echo "Usage: make analysis-generic APPLICATION=... INSTRUCTIONS=... [PROVIDER=...] [MODEL=...]" >&2; exit 2)
	@test -f "$(INSTRUCTIONS)" || (echo "Instruction file not found: $(INSTRUCTIONS)" >&2; exit 2)
	@uv run --project packages/grid-agent grid-agent analysis-generic --application "$(APPLICATION)" --instructions "$(INSTRUCTIONS)" $(if $(PROVIDER),--provider "$(PROVIDER)") $(if $(MODEL),--model "$(MODEL)")

application:
	@$(MAKE) --no-print-directory analysis-generic \
		APPLICATION="$(if $(APPLICATION),$(APPLICATION),pandapower-static-analysis)" \
		INSTRUCTIONS="$(if $(INSTRUCTIONS),$(INSTRUCTIONS),$(ANALYSIS_DEFAULT_INSTRUCTIONS))" \
		$(if $(PROVIDER),PROVIDER="$(PROVIDER)") \
		$(if $(MODEL),MODEL="$(MODEL)")

report: analysis

PORT ?= 8765
CAPSTONE_PORT ?= 8766

trajectory: build-workbench
	uv run --project packages/grid-agent grid-agent trajectory serve --host 127.0.0.1 --port "$(PORT)" --runs-root runs

test: test-agent test-simulator test-tools test-capstone-agent test-capstone-app test-capstone-client test-makefile-application test-verification-targets test-kernel test-domain-package test-generic-tools test-inventory test-pypsa test-workbench

test-capstone-agent:
	uv run --project packages/capstone-agent pytest packages/capstone-agent/tests --ignore=packages/capstone-agent/tests/test_registered_workers.py -q

test-capstone-client:
	uv run --project packages/grid-agent pytest tools/tests/test_capstone_client.py -q

test-makefile-application:
	bash tools/test_makefile_application.sh

test-verification-targets:
	uv run --project packages/grid-agent pytest tools/tests/test_verification_targets.py tools/tests/test_runtime_risk_exception.py tools/tests/test_projection_benchmark.py tools/tests/test_benchmark_optimization.py -q

.PHONY: benchmark-optimization
benchmark-optimization:
	uv run --project packages/grid-agent python tools/benchmark_optimization.py --events 1000 10000 100000 --output runs/optimization/benchmarks/report.json

test-agent:
	uv run --project packages/grid-agent pytest packages/grid-agent/tests --ignore=packages/grid-agent/tests/e2e -q

test-inventory-service:
	uv run --project packages/inventory-reference-service pytest packages/inventory-reference-service/tests -q

test-inventory-domain:
	uv run --project packages/inventory-domain-pack pytest packages/inventory-domain-pack/tests --ignore=packages/inventory-domain-pack/tests/test_generic_pi_transport.py -q

test-inventory-pi:
	uv run --project packages/inventory-domain-pack pytest packages/inventory-domain-pack/tests/test_generic_pi_transport.py -q

test-inventory: test-inventory-service test-inventory-domain test-inventory-pi

test-pypsa:
	uv run --project packages/pypsa-sector-coupling-domain-pack pytest packages/pypsa-model-authority/tests packages/pypsa-network-modeling-domain-pack/tests packages/pypsa-sector-coupling-domain-pack/tests -q
	uv run --project packages/pypsa-capacity-planning-domain-pack pytest packages/pypsa-capacity-planning-domain-pack/tests -q
	uv run --project packages/pypsa-power-operations-domain-pack pytest packages/pypsa-power-operations-domain-pack/tests -q
	uv run --project packages/pypsa-power-operations-domain-pack pytest validation/test_pypsa_cases.py -q
	uv run --project packages/pypsa-agent pytest packages/pypsa-agent/tests -q

# Stable provider-free entry for authors copying the inventory Domain Pack pattern.
test-domain-pack-conformance: check-package-boundaries
	uv run --project packages/inventory-domain-pack pytest packages/inventory-domain-pack/tests/test_application_conformance.py packages/inventory-domain-pack/tests/test_http_authority_experiment.py packages/inventory-domain-pack/tests/test_generic_pi_transport.py -q

test-domain-package: check-package-boundaries
	uv run --project packages/grid-agent pytest packages/pandapower-domain-pack/tests -q

test-kernel:
	uv run --project packages/grid-agent pytest packages/capability-agent-kernel/tests -q

test-generic-tools:
	npm run check --prefix packages/pi-capability-tools
	npm test --prefix packages/pi-capability-tools

test-simulator:
	uv run --project packages/grid-simulator pytest packages/grid-simulator/tests -q

test-tools: check-runtime-risk
	npm run check --prefix packages/pi-grid-tools
	npm test --prefix packages/pi-grid-tools

check-types: check-workbench
	uv run --project packages/grid-agent pyright

check-fast: check-package-boundaries check-types test

test-pi-capture-runtime:
	node tools/test_pi_capture_runtime.mjs --wrapper generic --mode success
	node tools/test_pi_capture_runtime.mjs --wrapper generic --mode failure
	node tools/test_pi_capture_runtime.mjs --wrapper grid --mode success
	node tools/test_pi_capture_runtime.mjs --wrapper grid --mode failure

check-integration: test-pi-capture-runtime test-e2e validate validate-application

check-release: check-fast check-integration test-packages test-source-setup

check-runtime-risk:
	python3 tools/check_runtime_risk_exception.py

test-e2e:
	uv run --project packages/grid-agent pytest packages/grid-agent/tests/e2e -q
	uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_registered_workers.py -q

validate: check-runtime-risk check-protected-paths
	uv run --project packages/grid-agent python validation/run.py --mode offline --suite task-required --report runs/validation-offline.json
	uv run --project packages/grid-agent python validation/run.py --mode scripted-pi --suite static-analysis-core --report runs/validation-scripted.json
	uv run --project packages/grid-agent python validation/run.py --mode scripted-pi --suite static-analysis-full --report runs/validation-static-analysis-full.json
	python3 tools/capability_matrix.py --check

validate-application:
	uv run --project packages/grid-agent python validation/run.py --mode application --suite application-instantiation --report runs/validation-application-instantiation.json

check-package-boundaries:
	python3 tools/check_package_boundaries.py

check-application-boundaries: check-package-boundaries

check-protected-paths:
	python3 tools/check_protected_paths.py \
		--config configs/runtime/application-instantiation-protected-paths.json

test-packages:
	bash tools/test_package_artifacts.sh

test-source-setup:
	bash tools/test_source_setup.sh

VALIDATION_SUITE ?= static-analysis-full

validate-provider:
	uv run --project packages/grid-agent python validation/run.py --mode provider --suite "$(VALIDATION_SUITE)" --provider "$(PROVIDER)" $(if $(MODEL),--model "$(MODEL)") --report runs/validation-provider.json
