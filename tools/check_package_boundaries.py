#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import re
import sys
import tomllib
from collections.abc import Iterable
from pathlib import Path


FORBIDDEN_IMPORTS_BY_SOURCE_ROOT = {
    "packages/capability-agent-kernel/src": (
        "grid_agent",
        "grid_simulator",
        "pandapower_domain",
        "pandapower",
    ),
    "packages/pandapower-domain-pack/src": ("grid_agent",),
    "packages/inventory-reference-service/src": (
        "capability_agent",
        "grid_agent",
        "grid_simulator",
        "inventory_domain",
        "pandapower_domain",
        "pandapower",
    ),
    "packages/inventory-domain-pack/src": (
        "grid_agent",
        "grid_simulator",
        "pandapower_domain",
        "pandapower",
    ),
    "packages/grid-agent/src/grid_agent/cli": (
        "grid_agent.domain",
        "grid_agent.domains",
    ),
    "packages/grid-agent/src/grid_agent": (
        "grid_agent.analysis.capabilities",
        "grid_agent.analysis.domain_projection",
        "grid_agent.analysis.integrity",
        "grid_agent.analysis.models",
        "grid_agent.domain",
        "grid_agent.domains",
        "grid_agent.tools.catalog",
        "grid_agent.tools.guide",
        "grid_agent.trajectory.answers",
        "grid_agent.trajectory.artifacts",
        "grid_agent.trajectory.canonical",
        "grid_agent.trajectory.events",
        "grid_agent.trajectory.reader",
        "grid_agent.trajectory.recorder",
        "grid_agent.trajectory.replay",
    ),
}
GRID_AGENT_COMPATIBILITY_SHIMS = frozenset(
    {
        "analysis/capabilities.py",
        "analysis/domain_projection.py",
        "analysis/integrity.py",
        "analysis/models.py",
        "domain/__init__.py",
        "domain/authority.py",
        "domain/contracts.py",
        "domain/execution.py",
        "domain/manifest.py",
        "domain/profile.py",
        "domain/projection.py",
        "domains/__init__.py",
        "domains/pandapower.py",
        "tools/catalog.py",
        "tools/guide.py",
        "trajectory/__init__.py",
        "trajectory/answers.py",
        "trajectory/artifacts.py",
        "trajectory/canonical.py",
        "trajectory/events.py",
        "trajectory/reader.py",
        "trajectory/recorder.py",
        "trajectory/replay.py",
        "compat/v1_0_1_report.py",
    }
)
EXACT_FORBIDDEN_IMPORTS_BY_SOURCE_ROOT = {
    "packages/grid-agent/src/grid_agent/cli": (
        "grid_agent.application",
        "grid_agent.application.prepare_domain_runtime",
    ),
}
SOURCE_PATH_LITERAL_ROOTS = (
    "packages/capability-agent-kernel/src",
    "packages/pandapower-domain-pack/src",
    "packages/inventory-reference-service/src",
    "packages/inventory-domain-pack/src",
)
GENERIC_SEMANTIC_LITERAL_SOURCE_ROOTS = (
    # The complete Kernel is domain-neutral.  Keep semantic vocabulary out of
    # runtime, trajectory, and tool modules as well as application assembly;
    # only explicit composition roots may name a business domain.
    "packages/capability-agent-kernel/src/capability_agent",
)
FORBIDDEN_DEPENDENCIES_BY_PACKAGE_ROOT = {
    Path("packages/capability-agent-kernel"): ("grid-agent",),
    Path("packages/pandapower-domain-pack"): ("grid-agent",),
    Path("packages/inventory-reference-service"): (
        "capability-agent-kernel",
        "inventory-domain-pack",
        "grid-agent",
        "grid-simulator",
        "pandapower-domain-pack",
        "pandapower",
    ),
    Path("packages/inventory-domain-pack"): (
        "grid-agent",
        "grid-simulator",
        "pandapower-domain-pack",
        "pandapower",
    ),
}
SOURCE_PATH_PATTERN = re.compile(r"packages/[^'\"\s]+/src")
FORBIDDEN_GENERIC_PATTERNS = {
    "grid_agent": re.compile(r"\bgrid_agent\b"),
    "grid_simulator": re.compile(r"\bgrid_simulator\b"),
    "gridctl": re.compile(r"(?<![a-z0-9_])gridctl(?![a-z0-9_])"),
    "grid_": re.compile(r"\bgrid_[a-z0-9_]*\b"),
    "pandapower_domain": re.compile(r"\bpandapower_domain\b"),
    "pandapower": re.compile(r"\bpandapower\b"),
    "power-flow": re.compile(r"\bpower[-_ ]?flow\b"),
    "voltage": re.compile(r"\bvoltage\b"),
    "bus": re.compile(r"\bbus(?:es)?\b"),
    "branch": re.compile(r"\bbranch(?:es)?\b"),
    "n-1": re.compile(r"\bn[-_ ]?1\b"),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root to scan.",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    violations = sorted(check_boundaries(root))
    if violations:
        for violation in violations:
            print(violation, file=sys.stderr)
        return 1
    print("package-boundaries: ok")
    return 0


def check_boundaries(root: Path) -> list[str]:
    violations: list[str] = []
    for source_root, forbidden_modules in FORBIDDEN_IMPORTS_BY_SOURCE_ROOT.items():
        absolute_source_root = root / source_root
        if absolute_source_root.exists():
            violations.extend(
                check_python_sources(
                    root,
                    absolute_source_root,
                    forbidden_modules,
                    excluded_paths=(
                        GRID_AGENT_COMPATIBILITY_SHIMS
                        if source_root == "packages/grid-agent/src/grid_agent"
                        else frozenset()
                    ),
                )
            )
    for source_root, forbidden_modules in EXACT_FORBIDDEN_IMPORTS_BY_SOURCE_ROOT.items():
        absolute_source_root = root / source_root
        if absolute_source_root.exists():
            violations.extend(
                check_python_sources(
                    root,
                    absolute_source_root,
                    forbidden_modules,
                    exact=True,
                )
            )
    for source_root in SOURCE_PATH_LITERAL_ROOTS:
        absolute_source_root = root / source_root
        if absolute_source_root.exists():
            violations.extend(check_source_path_literals(root, absolute_source_root))

    for source_root in GENERIC_SEMANTIC_LITERAL_SOURCE_ROOTS:
        absolute_source_root = root / source_root
        if absolute_source_root.exists():
            violations.extend(
                check_generic_semantic_literals(root, absolute_source_root)
            )

    for package_root, forbidden_dependencies in (
        FORBIDDEN_DEPENDENCIES_BY_PACKAGE_ROOT.items()
    ):
        absolute_package_root = root / package_root
        if absolute_package_root.exists():
            violations.extend(
                check_pyproject(
                    root,
                    absolute_package_root,
                    forbidden_dependencies,
                )
            )

    return violations


def check_python_sources(
    root: Path,
    source_root: Path,
    forbidden_modules: tuple[str, ...],
    *,
    exact: bool = False,
    excluded_paths: frozenset[str] = frozenset(),
) -> list[str]:
    violations: list[str] = []
    for path in sorted(source_root.rglob("*.py")):
        if path.relative_to(source_root).as_posix() in excluded_paths:
            continue
        relative_path = path.relative_to(root).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for module in imported_modules(tree):
            if (
                module in forbidden_modules
                if exact
                else is_forbidden(module, forbidden_modules)
            ):
                violations.append(f"{relative_path} imports {module}")
    return violations


def check_source_path_literals(root: Path, source_root: Path) -> list[str]:
    violations: list[str] = []
    for path in sorted(source_root.rglob("*.py")):
        relative_path = path.relative_to(root).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for source_path in source_path_literals(tree):
            violations.append(f"{relative_path} contains source path {source_path}")
    return violations


def check_generic_semantic_literals(root: Path, source_root: Path) -> list[str]:
    violations: list[str] = []
    for path in sorted(source_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8").lower()
        for token, pattern in FORBIDDEN_GENERIC_PATTERNS.items():
            if pattern.search(text):
                relative = path.relative_to(root).as_posix()
                violations.append(
                    f"{relative} contains grid-owned semantic token {token}"
                )
    return violations


def imported_modules(tree: ast.AST) -> Iterable[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if alias.name == "*":
                    yield node.module
                else:
                    yield f"{node.module}.{alias.name}"


def source_path_literals(tree: ast.AST) -> Iterable[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for match in SOURCE_PATH_PATTERN.finditer(node.value):
                yield match.group(0)


def check_pyproject(
    root: Path,
    package_root: Path,
    forbidden_dependencies: tuple[str, ...],
) -> list[str]:
    pyproject = package_root / "pyproject.toml"
    if not pyproject.exists():
        return []
    document = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    relative_path = pyproject.relative_to(root).as_posix()
    violations: list[str] = []
    dependencies = dependency_names(document.get("project", {}))
    for forbidden_dependency in forbidden_dependencies:
        if forbidden_dependency in dependencies:
            violations.append(
                f"{relative_path} depends on {forbidden_dependency}"
            )
    for source_path in source_literals_in_value(document):
        violations.append(f"{relative_path} contains source path {source_path}")
    return violations


def dependency_names(project: object) -> set[str]:
    if not isinstance(project, dict):
        return set()
    dependencies = project.get("dependencies", ())
    optional_dependencies = project.get("optional-dependencies", {})
    return {
        canonical_dependency_name(dependency_name(dependency))
        for dependency in dependency_strings(dependencies)
    } | {
        canonical_dependency_name(dependency_name(dependency))
        for dependency in dependency_strings(optional_dependencies)
    }


def dependency_strings(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from dependency_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from dependency_strings(item)


def dependency_name(dependency: str) -> str:
    return re.split(r"\s*(?:@|[<>=!~]=?|;|\[)", dependency, maxsplit=1)[0].strip()


def canonical_dependency_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def source_literals_in_value(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield from (match.group(0) for match in SOURCE_PATH_PATTERN.finditer(value))
    elif isinstance(value, list):
        for item in value:
            yield from source_literals_in_value(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from source_literals_in_value(item)


def is_forbidden(module: str, forbidden_modules: tuple[str, ...]) -> bool:
    return any(
        module == forbidden or module.startswith(f"{forbidden}.")
        for forbidden in forbidden_modules
    )


if __name__ == "__main__":
    raise SystemExit(main())
