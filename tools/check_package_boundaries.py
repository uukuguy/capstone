#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import re
import sys
import tomllib
from collections.abc import Iterable
from pathlib import Path


RULES = {
    "packages/capability-agent-kernel/src": (
        "grid_agent",
        "grid_simulator",
        "pandapower_domain",
        "pandapower",
    ),
    "packages/pandapower-domain-pack/src": ("grid_agent",),
}
PACKAGE_ROOTS = (
    Path("packages/capability-agent-kernel"),
    Path("packages/pandapower-domain-pack"),
)
SOURCE_PATH_PATTERN = re.compile(r"packages/[^'\"\s]+/src")


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
    for source_root, forbidden_modules in RULES.items():
        absolute_source_root = root / source_root
        if absolute_source_root.exists():
            violations.extend(
                check_python_sources(
                    root,
                    absolute_source_root,
                    forbidden_modules,
                )
            )

    for package_root in PACKAGE_ROOTS:
        absolute_package_root = root / package_root
        if absolute_package_root.exists():
            violations.extend(check_pyproject(root, absolute_package_root))

    return violations


def check_python_sources(
    root: Path,
    source_root: Path,
    forbidden_modules: tuple[str, ...],
) -> list[str]:
    violations: list[str] = []
    for path in sorted(source_root.rglob("*.py")):
        relative_path = path.relative_to(root).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for module in imported_modules(tree):
            if is_forbidden(module, forbidden_modules):
                violations.append(f"{relative_path} imports {module}")
        for source_path in source_path_literals(tree):
            violations.append(f"{relative_path} contains source path {source_path}")
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


def check_pyproject(root: Path, package_root: Path) -> list[str]:
    pyproject = package_root / "pyproject.toml"
    if not pyproject.exists():
        return []
    document = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    relative_path = pyproject.relative_to(root).as_posix()
    violations: list[str] = []
    if contains_grid_agent_dependency(document.get("project", {})):
        violations.append(f"{relative_path} depends on grid-agent")
    for source_path in source_literals_in_value(document):
        violations.append(f"{relative_path} contains source path {source_path}")
    return violations


def contains_grid_agent_dependency(project: object) -> bool:
    if not isinstance(project, dict):
        return False
    dependencies = project.get("dependencies", ())
    optional_dependencies = project.get("optional-dependencies", {})
    return any(
        canonical_dependency_name(dependency_name(dependency)) == "grid-agent"
        for dependency in dependency_strings(dependencies)
    ) or any(
        canonical_dependency_name(dependency_name(dependency)) == "grid-agent"
        for dependency in dependency_strings(optional_dependencies)
    )


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
    return re.split(r"\s*(?:[<>=!~]=?|;|\[)", dependency, maxsplit=1)[0].strip()


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
