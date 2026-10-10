"""GitHub publisher; credentials remain outside model and candidate processes."""
import json
import hashlib
import base64
from pathlib import Path
import stat
import time
import os
import subprocess
import tempfile

from .policy import public_text


class GitHub:
    def __init__(self, policy, api=None, publisher_api=None, root=None):
        self.policy = policy
        self.api = api or self._api
        self.publisher_api = publisher_api or self._publisher_api
        self.base = "repos/" + policy.repository
        self.root = Path(root or Path.cwd()).resolve()

    def _jwt(self):
        supplied = os.environ.get(self.policy.publisher_jwt_env)
        if supplied:
            return supplied
        path = self.root / self.policy.publisher_private_key_path
        if path.is_symlink() or not path.is_file():
            raise ValueError("Separate GitHub App publisher key or JWT is absent")
        metadata = path.stat()
        if stat.S_IMODE(metadata.st_mode) != 0o600 or metadata.st_uid != os.getuid():
            raise ValueError("GitHub App publisher key must be owner-only")
        ignored = subprocess.run(["git", "-C", str(self.root), "check-ignore", "--quiet", str(path)], capture_output=True, timeout=10)
        if ignored.returncode:
            raise ValueError("GitHub App publisher key must be ignored")
        def encode(value):
            return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).rstrip(b"=")
        now = int(time.time())
        unsigned = encode({"alg": "RS256", "typ": "JWT"}) + b"." + encode({"iat": now - 60, "exp": now + 540, "iss": str(self.policy.publisher_app_id)})
        result = subprocess.run(["openssl", "dgst", "-sha256", "-sign", str(path)], input=unsigned, capture_output=True, timeout=10, env={"PATH": os.environ.get("PATH", "")})
        if result.returncode:
            raise ValueError("GitHub App publisher signing failed")
        return (unsigned + b"." + base64.urlsafe_b64encode(result.stdout).rstrip(b"=")).decode()

    def _api(self, method, path, data=None, publisher=False):
        # Public input never enters a shell. Body files avoid command-line secrets.
        args = ["gh", "api", "--method", method, path]
        with tempfile.TemporaryDirectory(prefix="capstone-gh-") as directory:
            if data is not None:
                body = os.path.join(directory, "body.json")
                with open(body, "w", encoding="utf-8") as handle:
                    json.dump(data, handle, ensure_ascii=False)
                os.chmod(body, 0o600)
                args += ["--input", body]
            environment = dict(os.environ)
            for name in ("OPENAI_API_KEY", self.policy.publisher_jwt_env, "CAPSTONE_ISSUE_GITHUB_TOKEN"):
                environment.pop(name, None)
            if publisher:
                token = getattr(self, "installation_token", None) or self._jwt()
                if not token:
                    raise ValueError("Separate GitHub App publisher JWT is absent")
                environment.pop("GITHUB_TOKEN", None)
                environment["GH_TOKEN"] = token
            result = subprocess.run(args, capture_output=True, timeout=60, env=environment)
            if result.returncode:
                raise RuntimeError("GitHub request failed; reconcile before retry")
            if len(result.stdout) > 4000000:
                raise ValueError("GitHub response exceeds limit")
            return json.loads(result.stdout or "null")

    def _publisher_api(self, method, path, data=None):
        return self._api(method, path, data, publisher=True)

    def pages(self, path):
        result = []
        for page in range(1, 21):
            rows = self.api("GET", path + ("&" if "?" in path else "?") + f"per_page=100&page={page}")
            if not isinstance(rows, list):
                raise ValueError("Invalid GitHub collection")
            result.extend(rows)
            if len(rows) < 100:
                return result
        raise ValueError("GitHub collection exceeds configured intake limit")

    def issues(self):
        return [i for i in self.pages(self.base + "/issues?state=open&sort=updated&direction=desc") if "pull_request" not in i]

    def issue(self, number):
        issue = self.api("GET", self.base + f"/issues/{int(number)}")
        issue["comments"] = self.pages(self.base + f"/issues/{int(number)}/comments")
        return issue

    def permission(self, login):
        import re
        if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", login):
            return "none"
        return self.api("GET", self.base + f"/collaborators/{login}/permission").get("permission", "none")

    def require_write(self):
        if not self.policy.write_enabled:
            raise ValueError("GitHub writes are disabled")
        self.identity()

    def identity(self):
        if hasattr(self, "actor") and self.token_until <= time.time():
            del self.actor
            del self.installation_token
        if not hasattr(self, "actor"):
            import re
            if not re.fullmatch(r"[a-z0-9-]+\[bot\]", self.policy.publisher_login) or self.policy.publisher_app_id <= 0 or self.policy.publisher_installation_id <= 0:
                raise ValueError("Independent GitHub App publisher identity is required")
            app = self.publisher_api("GET", "app")
            if app.get("id") != self.policy.publisher_app_id or app.get("slug", "") + "[bot]" != self.policy.publisher_login:
                raise ValueError("Configured GitHub App publisher does not match token identity")
            installation = self.publisher_api("GET", f"app/installations/{self.policy.publisher_installation_id}")
            if installation.get("id") != self.policy.publisher_installation_id or installation.get("app_id") != self.policy.publisher_app_id or installation.get("app_slug", "") + "[bot]" != self.policy.publisher_login:
                raise ValueError("Configured publisher installation does not match App identity")
            token = self.publisher_api("POST", f"app/installations/{self.policy.publisher_installation_id}/access_tokens", {"repositories": [self.policy.repository.split("/")[1]], "permissions": {"contents": "write", "issues": "write", "pull_requests": "write", "actions": "read", "checks": "read", "metadata": "read"}})
            if not isinstance(token.get("token"), str) or not token["token"]:
                raise ValueError("GitHub App publisher token creation failed")
            self.installation_token = token["token"]
            repositories = self.publisher_api("GET", "installation/repositories?per_page=100")
            if not any(r.get("full_name") == self.policy.repository for r in repositories.get("repositories", [])):
                del self.installation_token
                raise ValueError("GitHub App publisher cannot access the configured repository")
            self.token_until = time.time() + 3300
            self.actor = self.policy.publisher_login
        return self.actor

    def create_issue(self, store, title, body, provenance=None):
        self.require_write()
        import re
        title, body = public_text(title), public_text(body)
        if not re.search(r"[\u4e00-\u9fff]", title) or not 1 <= len(title) <= 200 or not body.strip():
            raise ValueError("Issue title must be short Chinese text with a nonempty body")
        provenance = provenance or {"origin": "development-observation", "facts": [], "hypotheses": [], "source_sha": None}
        if not isinstance(provenance, dict) or set(provenance) != {"origin", "facts", "hypotheses", "source_sha"} or provenance["origin"] not in {"development-observation", "user-feedback"}:
            raise ValueError("Invalid AI Issue provenance")
        for name in ("facts", "hypotheses"):
            if not isinstance(provenance[name], list) or len(provenance[name]) > 8:
                raise ValueError("Invalid Issue facts or hypotheses")
            for text in provenance[name]:
                public_text(text)
        if provenance["source_sha"] is not None and not re.fullmatch(r"[a-f0-9]{40,64}", provenance["source_sha"]):
            raise ValueError("Invalid Issue source identity")
        key = "create:" + hashlib.sha256((self.policy.repository + "\n" + title + "\n" + body).encode()).hexdigest()
        marker = "<!-- capstone-ai:" + key + " -->"
        previous = store.action(key)
        if previous and previous["state"] == "done":
            return json.loads(previous["receipt"])["issue"]
        # Search all states: an uncertain create may already have been closed.
        for issue in self.pages(self.base + "/issues?state=all"):
            if issue.get("user", {}).get("login") == self.actor and marker in (issue.get("body") or ""):
                store.record_action(key, "intake", "done", {"issue": issue, "provenance": provenance})
                return issue
        store.record_action(key, "intake", "uncertain")
        origin = "开发观察" if provenance["origin"] == "development-observation" else "用户反馈，AI 整理"
        details = f"\n\n来源：{origin}。\n可验证事实：" + ("；".join(provenance["facts"]) or "待核对原始记录。") + "\n待确认推断：" + ("；".join(provenance["hypotheses"]) or "暂无；未确认根因。")
        result = self.publisher_api("POST", self.base + "/issues", {"title": title, "body": public_text(self.policy.display_name + " 按已授权反馈整理。\n\n" + body + details + "\n\n" + marker)})
        store.record_action(key, "intake", "done", {"issue": result, "provenance": provenance})
        return result

    def publish_comment(self, store, task, issue, kind, body):
        self.require_write()
        row = store.get(task)
        identity = f"{self.policy.repository}:{issue}:{row['input_hash']}:{kind}:{body}"
        key = hashlib.sha256(identity.encode()).hexdigest()
        marker = "<!-- capstone-ai:" + key + " -->"
        previous = store.action(key)
        if previous and previous["state"] == "done":
            return json.loads(previous["receipt"])["id"]
        # Even the first attempt reconciles remote state after local storage loss.
        actor = self.identity()
        for comment in self.pages(self.base + f"/issues/{int(issue)}/comments"):
            if marker in comment.get("body", "") and comment.get("user", {}).get("login") == actor:
                store.record_action(key, task, "done", {"id": comment["id"]})
                return comment["id"]
        store.record_action(key, task, "uncertain")
        result = self.publisher_api("POST", self.base + f"/issues/{int(issue)}/comments", {"body": public_text(body) + "\n\n" + marker})
        store.record_action(key, task, "done", {"id": result["id"]})
        return result["id"]

    def find_pr(self, branch):
        from urllib.parse import quote
        owner = self.policy.repository.split("/")[0]
        rows = self.api("GET", self.base + "/pulls?state=all&head=" + quote(owner + ":" + branch, safe=""))
        return rows[0] if rows else None

    def publish_candidate(self, store, task, branch, source_sha, files, title, body):
        self.require_write()
        key = task + ":pr"
        existing = self.find_pr(branch)
        if existing:
            store.record_action(key, task, "done", existing)
            return existing
        tree_entries = []
        for path, content in sorted(files.items()):
            blob = self.publisher_api("POST", self.base + "/git/blobs", {"content": content, "encoding": "utf-8"})
            tree_entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        base = self.api("GET", self.base + "/git/commits/" + source_sha)
        tree = self.publisher_api("POST", self.base + "/git/trees", {"base_tree": base["tree"]["sha"], "tree": tree_entries})
        commit = self.publisher_api("POST", self.base + "/git/commits", {"message": public_text(title), "tree": tree["sha"], "parents": [source_sha]})
        from urllib.parse import quote
        ref_path = self.base + "/git/matching-refs/heads/" + quote(branch, safe="/")
        refs = self.api("GET", ref_path)
        exact = next((r for r in refs if r["ref"] == "refs/heads/" + branch), None)
        if exact and exact["object"]["sha"] != commit["sha"]:
            remote_commit = self.api("GET", self.base + "/git/commits/" + exact["object"]["sha"])
            if remote_commit["tree"]["sha"] != tree["sha"] or [p["sha"] for p in remote_commit["parents"]] != [source_sha]:
                raise ValueError("Existing repair branch differs; maintainer review required")
        elif not exact:
            store.record_action(key, task, "uncertain", {"branch": branch, "commit": commit["sha"]})
            self.publisher_api("POST", self.base + "/git/refs", {"ref": "refs/heads/" + branch, "sha": commit["sha"]})
        store.record_action(key, task, "uncertain", {"branch": branch})
        result = self.publisher_api("POST", self.base + "/pulls", {"title": public_text(title), "body": public_text(body), "head": branch, "base": "main", "draft": True})
        store.record_action(key, task, "done", result)
        return result

    def acceptance_tag(self, name):
        import re
        if not re.fullmatch(r"(?:demo|cloud-dev)-\d{8}-\d{4}-[a-f0-9]{7,12}", name):
            raise ValueError("Invalid immutable acceptance tag name")
        ref = self.api("GET", self.base + "/git/ref/tags/" + name)
        if ref["object"]["type"] != "tag":
            return {"name": name, "type": ref["object"]["type"]}
        tag = self.api("GET", self.base + "/git/tags/" + ref["object"]["sha"])
        if tag["object"]["type"] != "commit":
            raise ValueError("Acceptance tag must point directly to a source commit")
        try:
            annotation = json.loads(tag["message"])
        except json.JSONDecodeError:
            annotation = None
        return {"name": name, "type": "tag", "tag_sha": ref["object"]["sha"], "source_sha": tag["object"]["sha"], "annotation": annotation, "message": tag["message"]}

    def contains_commit(self, release_sha, merge_sha):
        if release_sha == merge_sha:
            return True
        result = self.api("GET", self.base + f"/compare/{merge_sha}...{release_sha}")
        return result.get("status") in {"ahead", "identical"} and result.get("merge_base_commit", {}).get("sha") == merge_sha

    def checks(self, sha):
        import re
        if not re.fullmatch(r"[a-f0-9]{40,64}", sha):
            raise ValueError("Checks require an exact commit SHA")
        rows = []
        for page in range(1, 21):
            result = self.api("GET", self.base + f"/commits/{sha}/check-runs?per_page=100&page={page}")
            rows.extend(result["check_runs"])
            if len(result["check_runs"]) < 100:
                break
        else:
            raise ValueError("CI check collection exceeds limit")
        output = {}
        for name in self.policy.required_ci:
            matching = [r for r in rows if r["name"] == name or r["name"].startswith(name + " (")]
            output[name] = bool(matching) and all(r.get("head_sha") == sha and r["status"] == "completed" and r["conclusion"] == "success" for r in matching)
        return output
