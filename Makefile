.DEFAULT_GOAL := help

.PHONY: help setup setup-agent setup-simulator setup-pypsa setup-tools setup-workbench build-workbench test-workbench check-workbench install-pi auth-import-pi auth-login doctor run run-llm analysis analysis-generic application report trajectory test test-agent test-makefile-application test-verification-targets test-inventory test-inventory-service test-inventory-domain test-inventory-pi test-pypsa test-simulator test-tools test-e2e validate validate-application validate-provider test-kernel test-domain-package test-generic-tools check-types check-fast check-integration check-release check-runtime-risk check-package-boundaries check-application-boundaries check-protected-paths test-packages test-source-setup test-pi-capture-runtime

help:
	@echo "Grid Static Analysis commands"
	@echo "  make setup                 Install all local dependencies"
	@echo "  make doctor                Inspect local runtime readiness"
	@echo "  make run QUESTION='...'    Run a local deterministic smoke/offline check"
	@echo "  make run-llm QUESTION='...'  Primary natural-language agent path via Pi/LLM"
	@echo "  make analysis [INSTRUCTIONS=...]  Compatibility analysis report; default TASK instruction set"
	@echo "  make analysis-generic APPLICATION=... INSTRUCTIONS=...  Generic composite application output"
	@echo "  make application [INSTRUCTIONS=...] [PROVIDER=...] [MODEL=...]  Run the formal registered application"
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
	@echo "  make test-e2e              Run offline CLI and scripted Pi-to-gridctl scenarios"
	@echo "  make validate              Run deterministic WP-A validation"
	@echo "  make validate-application  Run provider-free generic application instantiation validation"
	@echo "  make validate-provider PROVIDER=... [MODEL=...]  Run optional billed provider validation"
	@echo "  make check-application-boundaries  Verify generic application ownership boundaries"
	@echo "  Manual: docs/MANUAL-VALIDATION.md (human verification for every entry above)"

setup: setup-agent setup-simulator setup-pypsa setup-tools setup-workbench build-workbench

setup-agent:
	uv sync --project packages/grid-agent

setup-simulator:
	uv sync --project packages/grid-simulator

setup-pypsa:
	uv sync --project packages/pypsa-power-operations-domain-pack

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

trajectory: build-workbench
	uv run --project packages/grid-agent grid-agent trajectory serve --host 127.0.0.1 --port "$(PORT)" --runs-root runs

test: test-agent test-simulator test-tools test-makefile-application test-verification-targets test-kernel test-domain-package test-generic-tools test-inventory test-pypsa test-workbench

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
	uv run --project packages/pypsa-power-operations-domain-pack pytest packages/pypsa-model-authority/tests packages/pypsa-network-modeling-domain-pack/tests packages/pypsa-power-operations-domain-pack/tests -q

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
