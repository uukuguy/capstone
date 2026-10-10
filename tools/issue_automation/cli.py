"""Manual-first development commands. No timer or background execution."""
import argparse
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

from .github import GitHub
from .model import Model, load_image
from .policy import Policy, feedback, CHECK_PROFILES, checked_edit_prefixes
from .repair import DockerSandbox, Repair, Source
from .service import Service, release_status
from .store import Store


def operator_override(root, policy):
    path = Path(root) / ".capstone-agent/issue-automation/operator.json"
    if not path.exists():
        return replace(policy, edit_prefixes=checked_edit_prefixes(policy.edit_prefixes, policy.check_profile)).validate()
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600 or metadata.st_uid != os.getuid() or metadata.st_size > 24000:
        raise ValueError("Operator settings must be an owner-only regular file")
    result = subprocess.run(["git", "-C", str(root), "check-ignore", "--quiet", str(path)], capture_output=True, timeout=10)
    if result.returncode:
        raise ValueError("Operator settings must be ignored")
    values = json.loads(path.read_text())
    allowed = {"write_enabled", "publisher_login", "publisher_app_id", "publisher_installation_id", "publisher_private_key_path", "display_name", "model_enabled", "endpoint", "model", "api_key_env", "task_budget_usd", "daily_budget_usd", "request_reserve_usd", "task_token_budget", "daily_token_budget", "max_request_input_tokens", "input_usd_per_million_tokens", "output_usd_per_million_tokens", "max_output_tokens", "sandbox_image", "check_profile"}
    if not isinstance(values, dict) or set(values) - allowed:
        raise ValueError("Operator settings cannot change source scope or checks")
    if "check_profile" in values:
        if values["check_profile"] not in CHECK_PROFILES:
            raise ValueError("Only registered trusted check profiles can be selected")
        values["checks"] = CHECK_PROFILES[values["check_profile"]]
    values["edit_prefixes"] = checked_edit_prefixes(policy.edit_prefixes, values.get("check_profile", policy.check_profile))
    return replace(policy, **values).validate()


def load_policy(root, ref="main", config="configs/development/issue-automation.json"):
    if config != "configs/development/issue-automation.json":
        raise ValueError("Use the registered trusted policy path")
    source = Source(root, ref)
    policy = Policy.from_json(source.git("show", source.sha + ":" + config))
    return operator_override(root, policy), source


def read_json(path, max_bytes=1000000):
    source = Path(path)
    if source.is_symlink() or not source.is_file() or source.stat().st_size > max_bytes:
        raise ValueError("Input must be a bounded local JSON file")
    return json.loads(source.read_text())


def doctor(policy, source):
    blockers = []
    if not shutil.which("gh"):
        blockers.append("GitHub CLI is missing")
    if not shutil.which("docker"):
        blockers.append("Docker is missing")
    if not policy.sandbox_image:
        blockers.append("No prepared sandbox image")
    if not policy.checks:
        blockers.append("Trusted candidate checks are not configured")
    if not policy.write_enabled:
        blockers.append("GitHub publishing is disabled")
    if not policy.publisher_app_id:
        blockers.append("Independent GitHub App publisher is not registered")
    if policy.write_enabled and not os.environ.get(policy.publisher_jwt_env) and not (source.root / policy.publisher_private_key_path).is_file():
        blockers.append("Separate GitHub App publisher key or JWT is absent")
    return {"mode": "manual", "repository": policy.repository, "policy_sha": source.sha, "execution_owner": policy.execution_owner, "model_enabled": policy.model_enabled, "writes_enabled": policy.write_enabled, "model_credential_present": bool(os.environ.get(policy.api_key_env)), "model_budget_configured": policy.model_enabled and policy.task_budget_usd > 0, "automatic_tasks": False, "blockers": blockers}


def parser():
    result = argparse.ArgumentParser(description="Manual GitHub feedback and isolated repair")
    subcommands = result.add_subparsers(dest="command", required=True)
    for name in ("doctor", "scan", "show", "context", "create", "prepare-image", "triage", "begin", "record-verification", "complete", "fix", "retry", "pause", "status", "release-status", "daemon", "start", "stop"):
        command_parser = subcommands.add_parser(name)
        command_parser.add_argument("--root", type=Path, default=Path.cwd())
        command_parser.add_argument("--policy-ref", default="main")
        command_parser.add_argument("--read-only", action="store_true")
        command_parser.add_argument("--issue", type=int, default=int(os.environ["ISSUE"]) if os.environ.get("ISSUE", "").isdigit() else None)
        command_parser.add_argument("--task", default=os.environ.get("TASK_ID"))
        command_parser.add_argument("--judgment", default=os.environ.get("JUDGMENT"))
        command_parser.add_argument("--paths-file", default=os.environ.get("PATHS_FILE"))
        command_parser.add_argument("--result", default=os.environ.get("RESULT_FILE"))
        command_parser.add_argument("--use-model", action="store_true")
        command_parser.add_argument("--pr", type=int)
        command_parser.add_argument("--tag")
        command_parser.add_argument("--receipt")
        command_parser.add_argument("--title", default=os.environ.get("ISSUE_TITLE"))
        command_parser.add_argument("--body-file", default=os.environ.get("BODY_FILE"))
        command_parser.add_argument("--provenance")
        command_parser.add_argument("--download-images", action="store_true")
        command_parser.add_argument("--environment", choices=("local-dev", "local-demo", "cloud-dev", "cloud-demo"), default="cloud-demo")
    return result


def execute(args):
    if args.command in {"daemon", "start", "stop"}:
        return {"mode": "manual", "automatic_tasks": False, "message": "后台自动任务未启用。请使用明确的手动命令。"}
    root = args.root.resolve()
    policy, source = load_policy(root, args.policy_ref)
    if args.read_only:
        policy = replace(policy, model_enabled=False, write_enabled=False)
    if args.command == "doctor":
        return doctor(policy, source)
    if args.command not in {"scan", "status", "show", "context", "release-status"} and args.policy_ref != "main":
        raise ValueError("Development actions must use the trusted current main policy")
    if os.environ.get("GITHUB_ACTIONS") == "true" and (not args.read_only or args.command not in {"doctor", "scan", "status", "show", "context"}):
        raise ValueError("GitHub Actions is a read-only intake lane")
    if args.command in {"triage", "begin", "fix", "retry", "pause", "show", "context"} and not args.issue:
        raise ValueError("An Issue number is required")
    if args.command in {"record-verification", "complete"} and not args.task:
        raise ValueError("A task ID is required")
    if args.command == "triage" and not args.judgment and not args.use_model:
        raise ValueError("Supply a current-session judgment JSON file; API use must be explicit")
    if args.command == "fix" and not args.use_model:
        raise ValueError("Use begin and complete for current-session repair; optional API repair needs --use-model")
    if args.read_only and args.command not in {"scan", "status", "show", "context", "release-status"}:
        raise ValueError("Read-only mode cannot run this command")
    state = root / ".capstone-agent/issue-automation"
    store = Store(state / "queue.sqlite")
    try:
        if args.command == "prepare-image":
            import tempfile
            with tempfile.TemporaryDirectory(prefix="trusted-build-", dir=state) as directory:
                context = source.export(directory)
                dockerfile = context / "tools/issue_automation/sandbox.Dockerfile"
                if not dockerfile.is_file():
                    raise ValueError("The trusted main sandbox recipe is not available")
                image_id = state / "prepared-image.id"
                environment = {name: os.environ[name] for name in ("PATH", "HOME", "DOCKER_HOST", "LANG") if name in os.environ}
                with open(os.devnull, "wb") as sink:
                    result = subprocess.run(["docker", "build", "--build-arg", "CHECK_PROFILE=" + policy.check_profile, "--file", str(dockerfile), "--iidfile", str(image_id), str(context)], stdout=sink, stderr=sink, env=environment, timeout=3600)
                if result.returncode:
                    raise ValueError("Trusted sandbox dependency preparation failed")
                return {"source_sha": source.sha, "image_id": image_id.read_text().strip(), "mode": "trusted-dependency-preparation", "candidate_executed": False}
        github = GitHub(policy, root=root)
        if args.command == "create":
            if not args.title or not args.body_file:
                raise ValueError("A Chinese title and authorized public body file are required")
            body_path = Path(args.body_file)
            if body_path.is_symlink() or body_path.stat().st_size > 24000:
                raise ValueError("Issue body must be a bounded local text file")
            return github.create_issue(store, args.title, body_path.read_text(), read_json(args.provenance) if args.provenance else None)
        model = Model(policy, store)
        repair = Repair(policy, source, model, DockerSandbox(policy), state / "candidates")
        service = Service(policy, store, github, model, source, repair)
        if args.command == "scan":
            return {"mode": "manual", "automatic_tasks": False, "issues": service.scan()}
        if args.command in {"show", "context"}:
            task, issue, data = service.intake(args.issue)
            images = []
            if args.download_images:
                import base64
                import hashlib
                directory = state / "images"
                directory.mkdir(mode=0o700, exist_ok=True)
                for url in data["images"]:
                    image = load_image(url, policy)
                    mime, content = image.split(";base64,", 1)
                    suffix = {"data:image/png": ".png", "data:image/jpeg": ".jpg", "data:image/webp": ".webp"}[mime]
                    path = directory / (hashlib.sha256(url.encode()).hexdigest() + suffix)
                    path.write_bytes(base64.b64decode(content))
                    path.chmod(0o600)
                    images.append(str(path))
            return {"task_id": task, "issue": args.issue, "feedback": data, "image_files": images, "policy_sha": source.sha, "source_sha": source.sha, "source_index": source.index(policy), "edit_prefixes": policy.edit_prefixes, "checks": policy.checks}
        if args.command == "triage":
            return {"task_id": service.triage(args.issue, read_json(args.judgment) if args.judgment else None)}
        if args.command == "begin":
            if not args.paths_file:
                raise ValueError("A current-session source selection JSON array is required")
            return service.begin(args.issue, read_json(args.paths_file))
        if args.command == "record-verification":
            if not args.result:
                raise ValueError("A bounded replacement result JSON file is required")
            return service.record_verification(args.task, read_json(args.result))
        if args.command == "complete":
            return service.complete(args.task, read_json(args.result) if args.result else None)
        if args.command == "fix":
            return service.fix(args.issue)
        if args.command == "retry":
            return {"task_id": service.retry(args.issue)}
        if args.command == "pause":
            store.pause(args.issue)
            return {"issue": args.issue, "state": "paused"}
        if args.command == "status":
            tasks = [{k: row[k] for k in ("task_id", "issue", "input_hash", "policy_sha", "source_sha", "state", "lease_until", "attempts")} for row in store.list(args.issue)]
            return {"mode": "manual", "automatic_tasks": False, "tasks": tasks}
        if args.command == "release-status":
            if not args.pr:
                raise ValueError("A pull request number is required")
            pr = github.api("GET", github.base + f"/pulls/{args.pr}")
            receipt = read_json(args.receipt) if args.receipt else None
            tag = github.acceptance_tag(args.tag) if args.tag else None
            contains = bool(tag and pr.get("merged") and github.contains_commit(tag.get("source_sha"), pr.get("merge_commit_sha")))
            result = release_status(pr, tag, receipt, args.environment, contains_merge=contains)
            result["ci"] = github.checks(pr["head"]["sha"])
            return result
        raise ValueError("Unsupported command")
    finally:
        store.close()


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        output = execute(args)
        print(json.dumps(output, ensure_ascii=False))
        return 0
    except (ValueError, RuntimeError, OSError, TimeoutError, KeyError, TypeError, json.JSONDecodeError) as error:
        # Error bodies can include API or candidate secrets. Print only controlled errors.
        message = str(error) if isinstance(error, ValueError) and not isinstance(error, json.JSONDecodeError) else type(error).__name__
        print(json.dumps({"error": message, "automatic_tasks": False}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
