"""Guard the M6 Case/Harness ownership and compatibility boundaries."""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[3]
CAPSTONE_SRC = ROOT / "packages" / "capstone-agent" / "src" / "capstone_agent"
COMPAT_SRC = (
    ROOT
    / "packages"
    / "grid-agent"
    / "src"
    / "grid_agent"
    / "compat"
    / "v1_0_1.py"
)


def _import_targets(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    targets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            targets.append(node.module)
    return tuple(targets)


def _load_compatibility_adapter() -> ModuleType:
    spec = importlib.util.spec_from_file_location("capstone_compat_v1_0_1", COMPAT_SRC)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load compatibility adapter: {COMPAT_SRC}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_case_and_harness_sources_do_not_import_legacy_application_roots() -> None:
    implementation = sorted(CAPSTONE_SRC.glob("case_*.py")) + [CAPSTONE_SRC / "harness.py"]

    assert implementation
    for path in implementation:
        forbidden = tuple(
            target
            for target in _import_targets(path)
            if target == "grid_agent"
            or target.startswith("grid_agent.")
            or target == "pypsa_agent"
            or target.startswith("pypsa_agent.")
        )
        assert not forbidden, f"{path.relative_to(ROOT)} imports legacy roots: {forbidden}"


def test_case_service_does_not_call_pi_or_authority_internals() -> None:
    case_sources = [
        CAPSTONE_SRC / "case_definition.py",
        CAPSTONE_SRC / "case_execution.py",
        CAPSTONE_SRC / "case_service.py",
    ]
    forbidden_tokens = (
        "grid_agent",
        "pypsa_agent",
        "pandapower",
        "pypsa",
        "gridctl",
        "subprocess",
        "HarnessPiClient",
        "HarnessDSHClient",
        "PiPromptSession",
        "Authority",
    )

    for path in case_sources:
        source = path.read_text(encoding="utf-8")
        present = tuple(token for token in forbidden_tokens if token in source)
        assert not present, f"{path.relative_to(ROOT)} reaches runtime/authority internals: {present}"


def test_legacy_adapters_do_not_import_case_execution_internals() -> None:
    legacy_sources = (
        ROOT / "packages" / "grid-agent" / "src",
        ROOT / "packages" / "pypsa-agent" / "src",
    )
    forbidden = ("capstone_agent.case_definition", "capstone_agent.case_execution", "capstone_agent.case_service")

    for source_root in legacy_sources:
        for path in source_root.rglob("*.py"):
            imports = _import_targets(path)
            present = tuple(target for target in imports if target in forbidden)
            assert not present, f"{path.relative_to(ROOT)} imports Case internals: {present}"


def test_compatibility_stdout_is_one_two_field_json_object() -> None:
    module = _load_compatibility_adapter()
    assert module.LEGACY_COMMANDS == ("run", "analysis", "report")

    output = module.V1_0_1CompatibilityAdapter().render(
        question_id="q-architecture-boundary",
        answer_output="runs/example/report.md",
    )

    assert output.count("\n") == 1
    assert len(output.splitlines()) == 1
    payload = json.loads(output)
    assert set(payload) == {"question_id", "answer_output"}
    assert payload == {
        "question_id": "q-architecture-boundary",
        "answer_output": "runs/example/report.md",
    }
