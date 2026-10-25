"""Choose a bounded development gate; unknown changes require product checks."""
from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path, PurePosixPath
import re
from urllib.parse import unquote
import subprocess
import tomllib


DOC_FILES = {"README.md", "README.zh-CN.md", "AGENTS.md", "CLAUDE.md",
             "tools/render_project_overview.py"}
GOVERNANCE_FILES = {".github/workflows/verify.yml", "tools/ci_scope.py",
                    "configs/development/issue-automation.json",
                    "tools/tests/test_ci_scope.py", "tools/tests/test_verification_targets.py"}

# Assembly and native-runtime contracts have bounded cross-package gates.
# Authority protocols, solvers and unknown dependencies still require product.
FOUNDATION_FILES = {
    'packages/capability-agent-kernel/src/capability_agent/' + path
    for path in ('application/composition.py', 'application/profile.py',
                 'application/registry.py', 'application/native.py', 'application/runner.py',
                 'domain/__init__.py', 'domain/manifest.py', 'domain/profile.py', 'tools/catalog.py')
} | {
    'packages/grid-agent/src/grid_agent/application/composition.py',
    'packages/grid-agent/src/grid_agent/hosted.py',
    'packages/grid-agent/src/grid_agent/thread_model_diagram.py',
    'packages/pypsa-agent/src/pypsa_agent/thread_model_diagram.py',
    'packages/pypsa-agent/src/pypsa_agent/worker.py',
}

CONVERSATION_RUNTIME_FILES = {
    'deploy/general-pi.Dockerfile',
    'packages/pi-capability-tools/src/research-tools.mjs',
    'packages/pi-capability-tools/src/research-context-window.mjs',
}
RUNTIME_FILES = {
    'compose.yaml', 'deploy/local.env.example',
    'configs/runtime/data-gateway.json', 'scripts/verify_data_gateway_research.py',
    'packages/grid-simulator/src/grid_simulator/powermcp_sidecar.py',
}
RUNTIME_DEPENDENCIES = {'packages/capstone-agent/pyproject.toml'} | {
    f'packages/{package}/uv.lock' for package in ('capstone-agent', 'grid-agent', 'pypsa-agent')
}
# MCP's additional transport/auth packages. Any other dependency change expands
# the gate, including a solver version changed only through a downstream lock.
MCP_PACKAGES = {'mcp', 'httpx-sse', 'sse-starlette', 'pydantic-settings',
                'python-multipart', 'pywin32', 'pyjwt'}


def runtime_dependency_document(path: str, old: dict, new: dict) -> bool:
    if path not in RUNTIME_DEPENDENCIES:
        return False

    def without_mcp(document):
        value = deepcopy(document)
        if path.endswith('pyproject.toml'):
            project = value.get('project', {})
            project['dependencies'] = [entry for entry in project.get('dependencies', [])
                                       if not re.match(r'^mcp(?:[<>=!~;\[]|$)', entry)]
        else:
            packages = []
            for package in value.get('package', []):
                if package.get('name') in MCP_PACKAGES:
                    continue
                if package.get('name') == 'capstone-agent':
                    for owner, key in ((package, 'dependencies'),
                                       (package.get('metadata', {}), 'requires-dist')):
                        if key in owner:
                            owner[key] = [item for item in owner[key] if item.get('name') != 'mcp']
                packages.append(package)
            value['package'] = packages
        return value

    return without_mcp(old) == without_mcp(new)


def runtime_dependency_diff(paths: list[str], base: str, head: str) -> bool:
    changed = set(paths) & RUNTIME_DEPENDENCIES
    if not changed:
        return False
    for path in changed:
        try:
            old, new = [tomllib.loads(subprocess.check_output(
                ['git', 'show', f'{revision}:{path}'], text=True)) for revision in (base, head)]
        except (subprocess.CalledProcessError, tomllib.TOMLDecodeError):
            return False
        if not runtime_dependency_document(path, old, new):
            return False
    return True


def classify(paths: list[str], *, target: str = "dev", release: bool = False,
             runtime_dependencies: bool = False) -> str:
    if target == "main" or release:
        return "release"
    if not paths:
        return "product"
    governance = False
    shared_agent = False
    foundation = False
    native_runtime = False
    conversation_runtime = False
    for path in paths:
        if ".." in PurePosixPath(path).parts:
            return "product"
        if path.startswith("packages/capstone-agent/src/capstone_agent/") and (
                PurePosixPath(path).name in {"kernel_pi_session.py", "pi_delegation.py"}):
            return "product"
        if (path in CONVERSATION_RUNTIME_FILES
                or (path.startswith('packages/capstone-agent/src/capstone_agent/') and path.endswith('.py')
                    and PurePosixPath(path).name.startswith('general_pi_'))
                or (PurePosixPath(path).parent == PurePosixPath('packages/capstone-agent/tests')
                    and path.endswith('.test.mjs'))
                or (path.startswith(('packages/capstone-agent/src/capstone_agent/resources/',
                                     'packages/capstone-agent/tests/fixtures/'))
                    and path.endswith(('.mjs', '.json')))):
            conversation_runtime = True
        elif path in RUNTIME_FILES or (runtime_dependencies and path in RUNTIME_DEPENDENCIES):
            native_runtime = True
        elif path in FOUNDATION_FILES or (
                path.startswith('packages/capability-agent-kernel/tests/') and path.endswith('.py')):
            foundation = True
        elif path in GOVERNANCE_FILES or path.startswith("tools/issue_automation/") or (
                path.startswith("tools/tests/test_issue_automation") and path.endswith(".py")):
            governance = True
        elif path.endswith(".py") and path.startswith((
                "packages/capstone-agent/src/capstone_agent/",
                "packages/capstone-agent/tests/")):
            shared_agent = True
        elif path.startswith("packages/capstone-app/src/") and (path.endswith((
                ".ts", ".tsx", ".css")) or path.startswith("packages/capstone-app/src/fixtures/") and path.endswith('.json')):
            shared_agent = True
        elif path not in DOC_FILES and not path.startswith(("docs/", "tools/project_overview/")):
            return "product"
    if native_runtime or foundation and conversation_runtime:
        return 'native-runtime'
    if conversation_runtime:
        return 'conversation-runtime'
    if foundation:
        return 'foundation'
    if shared_agent:
        return "shared-agent"
    return "governance" if governance else "docs"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--target", default="dev")
    parser.add_argument("--release", action="store_true")
    parser.add_argument("--check-docs", action="store_true")
    args = parser.parse_args()
    # Include both names of a rename so moving product code into docs is not a shortcut.
    output = subprocess.check_output(["git", "diff", "--no-renames", "--name-only", "-z",
                                      args.base, args.head, "--"], text=True)
    paths = [p for p in output.split("\0") if p]
    if args.check_docs:
        check_document_links(Path.cwd(), paths)
        print("Changed Markdown file links passed")
    else:
        print(classify(paths, target=args.target, release=args.release,
                       runtime_dependencies=runtime_dependency_diff(paths, args.base, args.head)))


def is_ignored_delivery_link(root: Path, document: Path, target: str) -> bool:
    """Allow absent operator delivery artifacts, never absent repository docs."""
    if target.startswith("/") or not re.fullmatch(r"[A-Za-z0-9._/-]+", target):
        return False
    parts = target.split("/")
    while parts and parts[0] in {".", ".."}:
        parts.pop(0)
    if not parts or any(not part or part.startswith(".") for part in parts):
        return False
    candidate = document.parent / target
    if any(path.is_symlink() for path in (candidate, *candidate.parents)):
        return False
    root = root.resolve()
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root / "runs/user-local-offline"):
        return False
    relative = resolved.relative_to(root)
    if any(part.startswith(".") for part in relative.parts):
        return False
    if resolved.name != "README.md" and not resolved.name.endswith((".tar.gz", ".tar.gz.sha256")):
        return False
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "check-ignore", "-q", "--", relative.as_posix()],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def check_document_links(root: Path, paths: list[str]) -> None:
    root = root.resolve()
    missing = []
    for path in paths:
        file = root / path
        if not path.endswith(".md") or not file.is_file():
            continue
        text = re.sub(r"```.*?```", "", file.read_text(), flags=re.S)
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            target = target.strip().strip("<>").split("#", 1)[0]
            if not target or re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("/"):
                continue
            if not (file.parent / unquote(target)).exists() and not is_ignored_delivery_link(root, file, target):
                missing.append(f"{path}: {target}")
    if missing:
        raise ValueError("Missing relative document links: " + "; ".join(missing))


if __name__ == "__main__":
    main()
