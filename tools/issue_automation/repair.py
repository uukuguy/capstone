"""Export inert source and validate candidates only in a secret-free container."""
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid

from .policy import public_text, safe_path


def is_test_file(path):
    name = Path(path).name
    return name.startswith("test_") and name.endswith(".py") or name.endswith((".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx"))


def validate_edit(path, original, content):
    name = Path(path).name
    if name in {"package.json", "package-lock.json", "pyproject.toml", "uv.lock", "Makefile", "conftest.py", "pytest.ini", "setup.cfg", "tox.ini", "Dockerfile", "Caddyfile"} or ".config." in name or name.startswith(("tsconfig", "testSetup", "testHelpers", "testUtils")) or path.endswith(".snap"):
        raise ValueError("Gate and dependency configuration is protected")
    if original and (is_test_file(path) or "/tests/" in path) and content != original:
        raise ValueError("Existing tests and test helpers must remain unchanged; add a new regression file")


class Source:
    def __init__(self, root, ref="main"):
        self.root = Path(root).resolve()
        self.ref = ref
        self.sha = self.git("rev-parse", "--verify", ref + "^{commit}").decode().strip()
        if not re.fullmatch(r"[a-f0-9]{40,64}", self.sha):
            raise ValueError("Invalid trusted source identity")

    def git(self, *args):
        result = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, timeout=30, env={"PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8"})
        if result.returncode:
            raise ValueError("Trusted source is unavailable")
        return result.stdout

    def entries(self):
        if hasattr(self, "_entries"):
            return self._entries
        result = []
        for entry in self.git("ls-tree", "-r", "-z", self.sha).split(b"\0"):
            if entry:
                meta, path = entry.split(b"\t", 1)
                mode, kind, blob = meta.decode().split()
                if kind == "blob" and mode in {"100644", "100755"}:
                    result.append((path.decode(), blob))
        self._entries = result
        return result

    def index(self, policy):
        result = []
        for path, _ in self.entries():
            try:
                safe_path(path, policy.source_prefixes)
                result.append(path)
            except ValueError:
                pass
        if len("\n".join(result).encode()) > policy.max_context_bytes // 2:
            raise ValueError("Source index exceeds limit; narrow trusted source prefixes")
        return result

    def read(self, path, policy):
        safe_path(path, policy.source_prefixes)
        rows = dict(self.entries())
        if path not in rows:
            raise ValueError("Selected path is not a regular tracked source file")
        raw = self.git("cat-file", "blob", rows[path])
        if len(raw) > policy.max_file_bytes or b"\0" in raw:
            raise ValueError("Selected source is too large or binary")
        text = raw.decode("utf-8")
        public_text(text, max_chars=policy.max_file_bytes)
        return text

    def read_or_new_test(self, path, policy):
        safe_path(path, policy.source_prefixes)
        if path in dict(self.entries()):
            return self.read(path, policy)
        safe_path(path, policy.edit_prefixes)
        if not is_test_file(path):
            raise ValueError("Only allowlisted new regression test files can be selected")
        return ""

    def export(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(directory, 0o755)  # Readable only through the private task parent or sandbox bind.
        for path, blob in self.entries():
            # Export only tracked regular text; no git metadata, user data or auth.
            if path != ".gitignore" and not path.startswith(".github/"):
                try:
                    safe_path(path, (path.split("/")[0],))
                except ValueError:
                    continue
            raw = self.git("cat-file", "blob", blob)
            if len(raw) > 2000000 or b"\0" in raw:
                continue
            try:
                raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            target = directory / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_bytes(raw)
                # Executable files have trusted bytes from main, but run only in Docker.
                if path in self.executable_paths():
                    target.chmod(0o755)
        return directory

    def executable_paths(self):
        if not hasattr(self, "_executable_paths"):
            self._executable_paths = set()
            for entry in self.git("ls-tree", "-r", "-z", self.sha).split(b"\0"):
                if entry:
                    meta, path = entry.split(b"\t", 1)
                    if meta.startswith(b"100755 "):
                        self._executable_paths.add(path.decode())
        return self._executable_paths


class DockerSandbox:
    def __init__(self, policy, runner=None):
        self.policy = policy
        self.runner = runner or subprocess.run

    def run(self, root, checks, seconds):
        if not re.fullmatch(r"(?:[A-Za-z0-9./:_-]+@)?sha256:[a-f0-9]{64}", self.policy.sandbox_image):
            raise ValueError("Sandbox needs a trusted prepared image pinned by digest")
        environment = {name: os.environ[name] for name in ("PATH", "DOCKER_HOST", "HOME", "LANG") if name in os.environ}
        receipts = []
        deadline = time.monotonic() + seconds
        for check in checks:
            name = "capstone-issue-check-" + uuid.uuid4().hex
            args = ["docker", "run", "--name", name, "--rm", "--pull=never", "--network=none", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit=128", "--memory=2g", "--cpus=2", "--user=65534:65534", "--tmpfs=/tmp:rw,nosuid,nodev,size=512m", "--mount", "type=bind,src=" + str(Path(root).resolve()) + ",dst=/source,readonly", "--workdir=/source", "--env=HOME=/tmp", "--env=PYTHONDONTWRITEBYTECODE=1", "--entrypoint", check[0], self.policy.sandbox_image, *check[1:]]
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Sandbox deadline exceeded")
            # Output is private, bounded by the check process. Never publish raw logs.
            with open(os.devnull, "wb") as sink:
                try:
                    result = self.runner(args, stdout=sink, stderr=sink, env=environment, timeout=remaining)
                finally:
                    self.runner(["docker", "rm", "--force", name], stdout=sink, stderr=sink, env=environment, timeout=20)
                    # A successful listing with no matching container confirms
                    # removal. Daemon errors must leave cleanup unconfirmed.
                    remaining = self.runner(["docker", "container", "ls", "--all", "--quiet", "--filter", "name=^/" + name + "$"], stdout=subprocess.PIPE, stderr=sink, env=environment, timeout=20)
                    if remaining.returncode or remaining.stdout.strip():
                        raise RuntimeError("Sandbox cleanup could not confirm container removal")
            receipts.append({"argv": list(check), "exit_code": result.returncode})
        return {"passed": all(r["exit_code"] == 0 for r in receipts), "checks": receipts, "image": self.policy.sandbox_image}


class Repair:
    def __init__(self, policy, source, model, sandbox, directory):
        self.policy, self.source, self.model, self.sandbox = policy, source, model, sandbox
        self.directory = Path(directory)

    def prepare(self, task, paths):
        if not isinstance(paths, list) or not 1 <= len(paths) <= self.policy.max_files or len(set(paths)) != len(paths):
            raise ValueError("Invalid source selection")
        files = {path: self.source.read_or_new_test(path, self.policy) for path in paths}
        root = self.directory / task
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.source.export(root / "base")
        self.source.export(root / "candidate")
        result = {"task_id": task, "source_sha": self.source.sha, "paths": paths, "files": files, "candidate_directory": str(root / "candidate"), "edit_prefixes": self.policy.edit_prefixes, "checks": self.policy.checks}
        (root / "prepared.json").write_text(json.dumps(result, ensure_ascii=False))
        return result

    def validate_manual(self, task, patch, cancelled=lambda: False):
        root = self.directory / task
        prepared = json.loads((root / "prepared.json").read_text())
        if prepared["source_sha"] != self.source.sha:
            raise ValueError("Trusted source changed")
        if not self.policy.checks or set(patch) != {"summary", "files", "reproduction_check"}:
            raise ValueError("Trusted checks and a bounded result are required")
        public_text(patch["summary"])
        if not re.search(r"[\u4e00-\u9fff]", patch["summary"]):
            raise ValueError("Repair summary must be Chinese")
        reproduction = patch["reproduction_check"]
        if isinstance(reproduction, bool) or not isinstance(reproduction, int) or not 0 <= reproduction < len(self.policy.checks):
            raise ValueError("Invalid reproduction check")
        if not isinstance(patch["files"], list) or not 1 <= len(patch["files"]) <= self.policy.max_files:
            raise ValueError("Invalid replacement list")
        files = {}
        for item in patch["files"]:
            if not isinstance(item, dict) or set(item) != {"path", "content"}:
                raise ValueError("Invalid replacement")
            path = safe_path(item["path"], self.policy.edit_prefixes)
            content = item["content"]
            if path not in prepared["files"] or path in files or not isinstance(content, str) or not content.strip() or "\0" in content or len(content.encode()) > self.policy.max_file_bytes:
                raise ValueError("Replacement is outside selected source or exceeds bounds")
            public_text(content, max_chars=self.policy.max_file_bytes)
            validate_edit(path, prepared["files"][path], content)
            files[path] = content
        # Rebuild a validation-only copy from trusted source. Ignore all workspace
        # edits outside the explicitly reviewed replacements; no executable host work.
        validation_root = self.source.export(root / ("validation-" + str(time.time_ns())))
        for path, content in files.items():
            (validation_root / path).parent.mkdir(parents=True, exist_ok=True)
            (validation_root / path).write_text(content)
        if cancelled():
            raise ValueError("Repair is paused")
        deadline = time.monotonic() + self.policy.task_deadline_seconds
        baseline_root = self.source.export(root / ("baseline-" + str(time.time_ns())))
        for path, content in files.items():
            if is_test_file(path):
                (baseline_root / path).parent.mkdir(parents=True, exist_ok=True)
                (baseline_root / path).write_text(content)
        baseline = self.sandbox.run(baseline_root, (self.policy.checks[reproduction],), self.policy.task_deadline_seconds)
        if baseline["passed"]:
            raise ValueError("Issue was not reproduced on trusted source")
        if cancelled():
            raise ValueError("Repair is paused")
        validation = self.sandbox.run(validation_root, self.policy.checks, max(1, deadline - time.monotonic()))
        if not validation["passed"]:
            raise ValueError("Candidate checks failed")
        result = {"files": files, "summary": patch["summary"], "baseline": baseline, "validation": validation, "source_sha": self.source.sha}
        (root / "result.json").write_text(json.dumps(result, ensure_ascii=False))
        return result

    def run(self, task, feedback, triage, cancelled=lambda: False):
        policy = self.policy
        if not policy.checks:
            raise ValueError("Trusted sandbox checks are not configured")
        deadline = time.monotonic() + policy.task_deadline_seconds
        root = self.directory / task
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        receipt_path = root / "result.json"
        if receipt_path.exists():
            return json.loads(receipt_path.read_text())
        selection = self.model.request(task, "select", {"feedback": feedback, "triage": triage, "source_index": self.source.index(policy), "max_files": policy.max_files})
        paths = selection.get("paths", [])
        if set(selection) != {"paths"} or not isinstance(paths, list) or not 1 <= len(paths) <= policy.max_files or len(set(paths)) != len(paths):
            raise ValueError("Invalid source selection")
        context = {path: self.source.read(path, policy) for path in paths}
        source_root = self.source.export(root / "base")
        candidate = self.source.export(root / "candidate")
        failed = None
        for round_number in range(policy.max_rounds):
            if cancelled() or time.monotonic() >= deadline:
                raise ValueError("Repair is paused or expired")
            patch = self.model.request(task, "repair", {"feedback": feedback, "triage": triage, "source_sha": self.source.sha, "files": context, "edit_prefixes": policy.edit_prefixes, "trusted_checks": policy.checks, "previous_check": failed})
            if set(patch) != {"summary", "files", "reproduction_check"} or not isinstance(patch["files"], list) or not 1 <= len(patch["files"]) <= policy.max_files:
                raise ValueError("Invalid repair contract")
            public_text(patch["summary"])
            reproduction = patch["reproduction_check"]
            if isinstance(reproduction, bool) or not isinstance(reproduction, int) or not 0 <= reproduction < len(policy.checks):
                raise ValueError("Invalid trusted reproduction check")
            replacements = {}
            for item in patch["files"]:
                if not isinstance(item, dict) or set(item) != {"path", "content"}:
                    raise ValueError("Invalid replacement")
                path = safe_path(item["path"], policy.edit_prefixes)
                if path not in context or path in replacements:
                    raise ValueError("Replacement must use a selected tracked source path")
                content = item["content"]
                if not isinstance(content, str) or len(content.encode()) > policy.max_file_bytes or "\0" in content or not content.strip():
                    raise ValueError("Invalid text replacement")
                public_text(content, max_chars=policy.max_file_bytes)
                validate_edit(path, context[path], content)
                replacements[path] = content
                (candidate / path).write_text(content, encoding="utf-8")
            baseline = self.sandbox.run(source_root, (policy.checks[reproduction],), max(1, deadline - time.monotonic()))
            if baseline["passed"]:
                raise ValueError("Issue was not reproduced on the trusted base source")
            if cancelled():
                raise ValueError("Repair is paused")
            failed = self.sandbox.run(candidate, policy.checks, max(1, deadline - time.monotonic()))
            if failed["passed"]:
                result = {"files": replacements, "summary": patch["summary"], "baseline": baseline, "validation": failed, "round": round_number + 1, "source_sha": self.source.sha}
                receipt_path.write_text(json.dumps(result, ensure_ascii=False))
                os.chmod(receipt_path, 0o600)
                return result
            context.update(replacements)
        raise ValueError("Candidate checks failed; no pull request was published")
