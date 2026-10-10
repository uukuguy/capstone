"""Manual command orchestration; issue events do not grant execution authority."""
import json
import re
import time
import uuid

from .policy import command, feedback, is_bot, public_text
from .model import validate_triage


def triage_reply(result):
    result = validate_triage(result)
    if result["state"] != "needs-info":
        raise ValueError("Triage alone does not justify a public progress reply")
    return "\n\n".join(result["questions"])


def release_status(pr, tag, receipt, environment, contains_merge=False):
    result = {"state": "review", "deployed": False, "user_confirmed": False, "message": "修复仍待评审。"}
    if not pr or not pr.get("merged"):
        return result
    result.update(state="release-pending", message="修复已进入主线，demo 尚未更新。")
    stage = {"cloud-demo": "demo", "cloud-dev": "cloud-dev"}.get(environment)
    if isinstance(tag, dict) and tag.get("format") in {"legacy-text", "legacy-json"}:
        result.update(tag=tag.get("name"), tag_status="legacy-report-required", tagged_source=tag.get("source_sha"), verification_report=tag.get("verification_report"), message="已识别现有验收标签；需按原标签关联的可信报告核对该修复，尚不声明本环境已生效。")
        return result
    if not stage or not isinstance(tag, dict) or not isinstance(receipt, dict):
        return result
    required = {"ready", "app", "case", "identity"} if stage == "demo" else {"ready", "app", "case", "reports", "replay", "identity"}
    if stage == "cloud-dev" and receipt.get("provider_authorized") is not False:
        required.add("provider")
    if stage == "cloud-dev" and receipt.get("provider_authorized") is False and receipt.get("provider_status") != "skipped-not-authorized":
        return result
    sha = tag.get("source_sha")
    valid = (tag.get("type") == "tag" and (sha == pr.get("merge_commit_sha") or contains_merge) and receipt.get("source_sha") == sha and receipt.get("stage") == stage and receipt.get("passed") is True and receipt.get("tag") == tag.get("name") and re.fullmatch(re.escape(stage) + r"-\d{8}-\d{4}-[a-f0-9]{7,12}", tag.get("name", "")) and receipt.get("deployment_ids") and required <= set(receipt.get("checks", {})) and all(receipt["checks"][k] is True for k in required) and tag.get("annotation") == receipt)
    if valid:
        result.update(state="verified", deployed=True, message=f"{environment} 已部署并通过技术验收；用户尚未确认。", source_sha=sha, tag=tag["name"])
    return result


class Service:
    def __init__(self, policy, store, github, model, source, repair):
        self.policy, self.store, self.github, self.model = policy, store, github, model
        self.source, self.repair = source, repair
        self.publisher_login = github.identity() if policy.write_enabled and hasattr(github, "identity") else policy.publisher_login

    def intake(self, number):
        issue = self.github.issue(number)
        data = feedback(issue, self.publisher_login)
        task = self.store.enqueue(number, data["input_hash"], self.source.sha, self.source.sha)
        return task, issue, data

    def scan(self):
        """Record intake and authenticated requests, with no model or remote writes."""
        result = []
        for item in self.github.issues():
            task, issue, data = self.intake(item["number"])
            requests = []
            for comment in issue.get("comments", []):
                if is_bot(comment, self.publisher_login):
                    continue
                body = comment.get("body", "")
                if re.fullmatch(r"/ai (triage|fix|retry|pause|status)", body.strip()):
                    request = command(body, self.github.permission(comment.get("user", {}).get("login", "")))
                    if request:
                        requests.append({"event_id": comment["id"], "command": request, "executed": False})
            row = self.store.get(task)
            payload = {**row["payload"], "requests": requests}
            self.store.update(task, payload=payload)
            result.append({"issue": item["number"], "task_id": task, "state": row["state"], "environment": data["environment"], "requests": requests})
        return result

    def triage(self, number, judgment=None):
        task, issue, data = self.intake(number)
        row = self.store.get(task)
        if row["state"] == "paused":
            raise ValueError("Issue is paused; retry must be explicit")
        if judgment is not None and row["state"] not in {"triage", "ready", "needs-info", "blocked"}:
            raise ValueError("Explicit triage cannot reclassify active or reviewed work")
        if "triage" in row["payload"] and judgment is None:
            result = row["payload"]["triage"]
        else:
            result = validate_triage(judgment) if judgment is not None else self.model.request(task, "triage", {"feedback": data, "source_sha": self.source.sha}, data["images"])
            # Explicit textual environment has precedence over a model guess.
            if data["environment_source"] == "user":
                result["environment"] = data["environment"]
            payload = {**row["payload"], "feedback": data, "triage": result}
            self.store.update(task, payload=payload, state=result["state"])
        if self.policy.write_enabled and self.store.get(task)["state"] == "needs-info":
            self.github.publish_comment(self.store, task, number, "triage", triage_reply(result))
        return task

    def fix(self, number):
        """Explicit optional API repair; not called by intake or event handling."""
        task, issue, data = self.intake(number)
        row = self.store.get(task)
        if not self.policy.model_enabled or not self.policy.write_enabled:
            raise ValueError("Optional API repair and GitHub writes must be configured")
        if "triage" not in row["payload"]:
            raise ValueError("Triage is required before repair")
        if row["state"] == "review":
            if "candidate" not in row["payload"]:
                raise ValueError("A verified candidate receipt is required for PR recovery")
            return self.publish(task, row["payload"]["candidate"])
        if not self.store.claim(task, uuid.uuid4().hex, seconds=self.policy.lease_seconds):
            raise ValueError("Repair is paused, ineligible or already leased")
        try:
            prefix = "improve" if row["payload"]["triage"]["type"] == "enhancement" else "fix"
            branch = row["payload"].get("branch") or f"{prefix}/issue-{number}-{data['input_hash'][:10]}-{row['source_sha'][:8]}"
            payload = {**row["payload"], "branch": branch}
            self.store.update(task, payload=payload)
            existing = self.github.find_pr(branch)
            if existing:
                if "candidate" not in payload:
                    raise ValueError("Existing PR has no verified candidate receipt; maintainer review required")
                result = self.publish(task, payload["candidate"])
            else:
                candidate = self.repair.run(task, data, payload["triage"], cancelled=lambda: self.store.get(task)["state"] == "paused")
                result = self.publish(task, candidate)
            self.store.update(task, state="review", lease_until=0, payload={**self.store.get(task)["payload"], "pr": result})
            return result
        except Exception as error:
            if self.store.get(task)["state"] != "paused":
                self.store.update(task, state="blocked", lease_until=0, payload={**self.store.get(task)["payload"], "blocker": type(error).__name__})
            raise

    def begin(self, number, paths):
        task, _, _ = self.intake(number)
        row = self.store.get(task)
        if "triage" not in row["payload"] or row["payload"]["triage"]["state"] != "ready":
            raise ValueError("Ready triage is required")
        if not self.store.claim(task, "current-session", seconds=self.policy.lease_seconds):
            raise ValueError("Task is paused, ineligible or already leased")
        try:
            prepared = self.repair.prepare(task, paths)
            prefix = "improve" if row["payload"]["triage"]["type"] == "enhancement" else "fix"
            self.store.update(task, payload={**row["payload"], "prepared": {k: v for k, v in prepared.items() if k != "files"}, "branch": f"{prefix}/issue-{number}-{row['input_hash'][:10]}-{row['source_sha'][:8]}"})
            return prepared
        except Exception:
            self.store.update(task, state="blocked", lease_until=0)
            raise

    def record_verification(self, task, patch):
        row = self.store.get(task)
        if row["state"] != "working" or row["lease_until"] <= time.time():
            raise ValueError("Task needs an active lease")
        _, _, current = self.intake(row["issue"])
        if current["input_hash"] != row["input_hash"] or self.source.sha != row["source_sha"]:
            raise ValueError("Issue input or trusted source changed; reassessment is required")
        try:
            result = self.repair.validate_manual(task, patch, lambda: self.store.get(task)["state"] == "paused")
            self.store.update(task, payload={**row["payload"], "candidate": result})
            return {"task_id": task, "source_sha": result["source_sha"], "baseline": result["baseline"], "validation": result["validation"]}
        except Exception:
            if self.store.get(task)["state"] != "paused":
                self.store.update(task, state="blocked", lease_until=0)
            raise

    def complete(self, task, patch=None):
        row = self.store.get(task)
        if row["state"] == "review":
            if "candidate" not in row["payload"]:
                raise ValueError("Verified candidate receipt is required for PR recovery")
            return self.publish(task, row["payload"]["candidate"])
        if patch is not None:
            self.record_verification(task, patch)
            row = self.store.get(task)
        if row["state"] != "working" or row["lease_until"] <= time.time() or "candidate" not in row["payload"]:
            raise ValueError("Current successful verification is required")
        _, _, current = self.intake(row["issue"])
        if current["input_hash"] != row["input_hash"]:
            raise ValueError("Issue input changed; reassessment is required")
        return self.publish(task, row["payload"]["candidate"])

    def publish(self, task, candidate):
        row = self.store.get(task)
        if self.store.get(task)["state"] == "paused":
            raise ValueError("Issue is paused")
        if self.source.git("rev-parse", self.source.ref).decode().strip() != row["policy_sha"]:
            raise ValueError("Trusted policy/source changed; reassessment is required")
        number = row["issue"]
        branch = row["payload"].get("branch") or f"fix/issue-{number}-{row['input_hash'][:10]}-{row['source_sha'][:8]}"
        self.store.update(task, payload={**row["payload"], "branch": branch, "candidate": candidate})
        body = (f"{self.policy.display_name} 辅助修复，关联 #{number}（保持 Issue 打开）。\n\n{candidate['summary']}\n\n"
                f"来源 main：`{row['source_sha']}`；政策提交：`{row['policy_sha']}`。\n"
                f"任务：`{task}`；输入：`{row['input_hash']}`。\n\n"
                "隔离检查：基础版本复现失败，候选版本的全部受控检查通过。\n"
                "CI：待精确候选提交检查，未运行或失败均不算通过。\n"
                "local-dev 与 local-demo 真实入口：待验证；涉及公共服务行为时须维护者重建并验证。\n"
                "main 集成、cloud-dev 与 cloud-demo 发布：待独立维护者操作。未自动合并、部署或关闭 Issue。\n")
        result = self.github.publish_candidate(self.store, task, branch, row["source_sha"], candidate["files"], f"修复：#{number} {candidate['summary']}", body)
        self.store.update(task, state="review", lease_until=0, payload={**self.store.get(task)["payload"], "pr": result})
        return result

    def retry(self, number):
        task, _, _ = self.intake(number)
        row = self.store.get(task)
        if row["state"] not in {"paused", "blocked"} or row["attempts"] >= self.policy.max_retries:
            raise ValueError("Retry is unavailable or exhausted")
        if row["lease_until"] > time.time():
            raise ValueError("Existing repair lease has not expired")
        self.store.update(task, state="ready" if "triage" in row["payload"] else "triage", attempts=row["attempts"] + 1, lease_until=0)
        return task
