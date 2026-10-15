"""Choose a bounded development gate; unknown changes require product checks."""
from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import re
from urllib.parse import unquote
import subprocess


DOC_FILES = {"README.md", "README.zh-CN.md", "AGENTS.md", "CLAUDE.md",
             "tools/render_project_overview.py"}
GOVERNANCE_FILES = {".github/workflows/verify.yml", "tools/ci_scope.py",
                    "tools/tests/test_ci_scope.py", "tools/tests/test_verification_targets.py"}


def classify(paths: list[str], *, target: str = "dev", release: bool = False) -> str:
    if target == "main" or release:
        return "release"
    if not paths:
        return "product"
    governance = False
    for path in paths:
        if ".." in PurePosixPath(path).parts:
            return "product"
        if path in GOVERNANCE_FILES or path.startswith("tools/issue_automation/") or (
                path.startswith("tools/tests/test_issue_automation") and path.endswith(".py")):
            governance = True
        elif path not in DOC_FILES and not path.startswith(("docs/", "tools/project_overview/")):
            return "product"
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
        print(classify(paths, target=args.target, release=args.release))


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
