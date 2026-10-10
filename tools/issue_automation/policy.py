"""Deterministic policy, input identity and output boundaries."""
from dataclasses import dataclass, fields
import hashlib
import json
from pathlib import PurePosixPath
import re
from urllib.parse import urlsplit

CHECK_PROFILES = {
    "app": (("/usr/local/bin/python", "/opt/capstone-check.py", "app"),),
    "backend": (("/usr/local/bin/python", "/opt/capstone-check.py", "backend"),),
    "app-and-backend": (("/usr/local/bin/python", "/opt/capstone-check.py", "app"), ("/usr/local/bin/python", "/opt/capstone-check.py", "backend")),
}

CHECK_PROFILE_SCOPES = {
    "app": ("packages/capstone-app/",),
    "backend": ("packages/capstone-agent/src/", "packages/capstone-agent/tests/"),
    "app-and-backend": ("packages/capstone-app/", "packages/capstone-agent/src/", "packages/capstone-agent/tests/"),
}


def checked_edit_prefixes(prefixes, profile):
    """Intersect trusted edit scope with the selected registered checks."""
    result = []
    for prefix in prefixes:
        prefix = prefix.rstrip("/") + "/"
        for checked in CHECK_PROFILE_SCOPES[profile]:
            candidate = prefix if prefix.startswith(checked) else checked if checked.startswith(prefix) else None
            if candidate and candidate not in result:
                result.append(candidate)
    return tuple(result)


@dataclass(frozen=True)
class Policy:
    repository: str = "uukuguy/capstone"
    execution_owner: str = "local"
    write_enabled: bool = False
    model_enabled: bool = False
    endpoint: str = "https://api.openai.com/v1/chat/completions"
    model: str = ""
    api_key_env: str = "OPENAI_API_KEY"
    task_budget_usd: float = 0.0
    daily_budget_usd: float = 0.0
    request_reserve_usd: float = 0.0
    task_token_budget: int = 0
    daily_token_budget: int = 0
    max_request_input_tokens: int = 65536
    input_usd_per_million_tokens: float = 0.0
    output_usd_per_million_tokens: float = 0.0
    max_output_tokens: int = 4096
    max_rounds: int = 2
    max_retries: int = 1
    task_deadline_seconds: int = 3600
    poll_seconds: int = 120
    lease_seconds: int = 3900
    sandbox_image: str = ""
    checks: tuple = ()
    source_prefixes: tuple = ("packages/", "tools/", "validation/", "tests/", "docs/")
    edit_prefixes: tuple = ("packages/capstone-app/",)
    max_files: int = 12
    max_file_bytes: int = 100000
    max_context_bytes: int = 240000
    attachment_hosts: tuple = ("github.com", "user-images.githubusercontent.com")
    attachment_urls: tuple = ()
    required_ci: tuple = ("verify (ubuntu-latest, 3.12)", "verify (ubuntu-latest, 3.14)", "verify (macos-latest, 3.12)", "verify (macos-latest, 3.14)")
    check_profile: str = "app-and-backend"
    publisher_login: str = "capstone-xiaoshi[bot]"
    publisher_app_id: int = 0
    publisher_installation_id: int = 0
    publisher_jwt_env: str = "CAPSTONE_ISSUE_GITHUB_APP_JWT"
    publisher_private_key_path: str = ".capstone-agent/issue-automation/app-private-key.pem"
    display_name: str = "小石 · Capstone AI"

    def validate(self):
        url = urlsplit(self.endpoint)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("Model endpoint must be a trusted HTTPS URL")
        if self.api_key_env not in {"OPENAI_API_KEY", "CAPSTONE_ISSUE_MODEL_API_KEY"}:
            raise ValueError("Model must use a separate model credential variable")
        if self.execution_owner != "local" or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.repository):
            raise ValueError("Invalid repository or execution owner")
        if not 1 <= self.max_rounds <= 2 or not 0 <= self.max_retries <= 1:
            raise ValueError("Repair limits exceed policy")
        if not 1 <= self.task_deadline_seconds <= 3600 or self.lease_seconds < self.task_deadline_seconds + 60:
            raise ValueError("Invalid deadline or lease")
        if not 10 <= self.poll_seconds <= 7200 or not 1 <= self.max_files <= 30:
            raise ValueError("Invalid queue limits")
        if not 1 <= self.max_output_tokens <= 8192 or not 1 <= self.max_file_bytes <= self.max_context_bytes <= 1000000:
            raise ValueError("Invalid content limits")
        if any(not isinstance(x, (list, tuple)) or not x or any(not isinstance(a, str) or not a for a in x) for x in self.checks):
            raise ValueError("Checks must be trusted argument arrays")
        if self.check_profile not in {"app", "backend", "app-and-backend"}:
            raise ValueError("Invalid trusted check profile")
        if self.model_enabled and (not self.model or not 0 < self.request_reserve_usd <= self.task_budget_usd <= self.daily_budget_usd):
            raise ValueError("Explicit model and cost limits are required")
        if self.model_enabled and (not 0 < self.task_token_budget <= self.daily_token_budget or self.input_usd_per_million_tokens <= 0 or self.output_usd_per_million_tokens <= 0):
            raise ValueError("Explicit token budgets and trusted model prices are required")
        if not 1024 <= self.max_request_input_tokens <= 1000000:
            raise ValueError("Invalid request input limit")
        if self.write_enabled and (not re.fullmatch(r"[a-z0-9-]+\[bot\]", self.publisher_login) or self.publisher_app_id <= 0 or self.publisher_installation_id <= 0):
            raise ValueError("Independent GitHub App publisher identity is required")
        if self.publisher_jwt_env != "CAPSTONE_ISSUE_GITHUB_APP_JWT":
            raise ValueError("Publisher must use its separate protected App JWT")
        public_text(self.display_name)
        for prefixes in (self.source_prefixes, self.edit_prefixes):
            for prefix in prefixes:
                safe_path(prefix.rstrip("/"), (prefix.rstrip("/"),))
        return self

    @classmethod
    def from_json(cls, data):
        values = json.loads(data)
        if not isinstance(values, dict) or set(values) - {f.name for f in fields(cls)}:
            raise ValueError("Unknown policy fields")
        for name in ("checks", "source_prefixes", "edit_prefixes", "attachment_hosts", "attachment_urls", "required_ci"):
            if name in values:
                values[name] = tuple(values[name])
        return cls(**values).validate()


def command(body, permission):
    match = re.fullmatch(r"/ai (triage|fix|retry|pause|status)", body.strip())
    return match[1] if match and permission in {"write", "maintain", "admin"} else None


def is_bot(comment, publisher_login=""):
    user = comment.get("user", {})
    return user.get("type") == "Bot" or user.get("login", "").endswith("[bot]") or (publisher_login and user.get("login") == publisher_login and "<!-- capstone-ai:" in comment.get("body", ""))


def feedback(issue, publisher_login=""):
    comments = [{"id": c.get("id"), "body": c.get("body", "")} for c in issue.get("comments", []) if not is_bot(c, publisher_login) and not re.fullmatch(r"/ai (triage|fix|retry|pause|status)", c.get("body", "").strip())]
    data = {"title": issue.get("title", ""), "body": issue.get("body") or "", "comments": comments}
    text = "\n".join([data["title"], data["body"], *(c["body"] for c in comments)])
    environments = re.findall(r"(?<![\w-])(local-demo|local-dev|cloud-demo|cloud-dev)(?![\w-])", text)
    explicit = re.findall(r"(?:(?:目标)?环境\s*[:：]|发生在|用户在|反馈明确指|明确指|这是)\s*(local-demo|local-dev|cloud-demo|cloud-dev)", text)
    unique = set(environments)
    explicit_unique = set(explicit)
    environment = next(iter(explicit_unique)) if len(explicit_unique) == 1 else None if explicit_unique else next(iter(unique)) if len(unique) == 1 else None if unique else "cloud-demo"
    data.update(environment=environment, environment_source="ambiguous" if environment is None else "user" if explicit or len(unique) == 1 else "default-rule", environment_candidates=sorted(unique), version=None, images=re.findall(r"!\[[^\]]*\]\((https://[^\s)]+)\)|<img[^>]+src=[\"'](https://[^\"']+)", text))
    data["images"] = [a or b for a, b in data["images"]][:4]
    data["input_hash"] = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return data


def safe_path(path, prefixes):
    value = PurePosixPath(path)
    if not isinstance(path, str) or value.is_absolute() or ".." in value.parts or str(value) != path or not any(path == p.rstrip("/") or path.startswith(p.rstrip("/") + "/") for p in prefixes):
        raise ValueError("Path is outside the permitted source scope")
    if any(part.startswith(".") or part in {"var", "runs", "node_modules", "__pycache__"} for part in value.parts) or value.suffix.lower() in {".key", ".pem", ".sqlite", ".db", ".nc"}:
        raise ValueError("Private or binary path is forbidden")
    return path


def public_text(text, max_chars=24000):
    if not isinstance(text, str) or len(text) > max_chars or re.search(r"sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]+|(?:API_KEY|TOKEN|PASSWORD|SECRET)\s*[:=]\s*\S+|postgres(?:ql)?://|AKIA[A-Z0-9]{16}", text, re.I):
        raise ValueError("Public output contains sensitive or excessive content")
    return text
