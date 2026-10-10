"""One-time loopback App enrollment; normal Issue work remains command-driven."""
import argparse
from dataclasses import replace
import html
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import time
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

from .cli import load_policy
from .github import GitHub


PERMISSIONS = {"contents": "write", "issues": "write", "pull_requests": "write", "actions": "read", "checks": "read", "metadata": "read"}


def manifest(origin, nonce):
    return {"name": "Capstone Xiaoshi", "url": "https://github.com/uukuguy/capstone", "description": "小石 · Capstone AI：按维护者命令协助处理中文 Issues 与 draft PR。", "public": False, "default_permissions": PERMISSIONS, "default_events": [], "hook_attributes": {"url": "https://example.invalid/disabled", "active": False}, "request_oauth_on_install": False, "redirect_url": origin + "/callback", "setup_url": origin + "/installed/" + nonce}


def private_json(path, value):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Configuration symlinks are not allowed")
    fd, temporary = tempfile.mkstemp(prefix="enroll-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate_app(value, owner="uukuguy"):
    if not isinstance(value, dict) or type(value.get("id")) is not int or value["id"] <= 0:
        raise ValueError("Invalid registered App identity")
    if value.get("owner", {}).get("login") != owner or not re.fullmatch(r"[a-z0-9-]+", value.get("slug", "")):
        raise ValueError("App owner or slug mismatch")
    if value.get("permissions") != PERMISSIONS or value.get("events"):
        raise ValueError("Unexpected App permissions or subscriptions")
    key = value.get("pem", "")
    if not isinstance(key, str) or not key.startswith("-----BEGIN RSA PRIVATE KEY-----\n") or not key.rstrip().endswith("-----END RSA PRIVATE KEY-----") or len(key) > 16000:
        raise ValueError("Invalid App private key response")
    return value


def exchange(code):
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,256}", code):
        raise ValueError("Invalid manifest code")
    request = Request("https://api.github.com/app-manifests/" + code + "/conversions", data=b"", method="POST", headers={"Accept": "application/vnd.github+json", "User-Agent": "Capstone-Xiaoshi-enrollment"})
    with urlopen(request, timeout=30) as response:
        raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError("App configuration response exceeds limit")
        return validate_app(json.loads(raw))


def store_app(root, value):
    value = validate_app(value)
    policy, _ = load_policy(root, "main")
    if policy.publisher_app_id not in {0, value["id"]}:
        raise ValueError("Registered App differs from protected operator identity")
    directory = root / ".capstone-agent/issue-automation"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = root / policy.publisher_private_key_path
    pending = directory / "enrollment-pending.json"
    previous = json.loads(pending.read_text()) if pending.is_file() and not pending.is_symlink() else None
    same = previous is not None and previous.get("id") == value["id"] and previous.get("pem") == value["pem"] and previous.get("slug") == value["slug"]
    if pending.is_symlink() or (previous is not None and not same):
        raise ValueError("Pending App registration must be reconciled")
    if key.is_symlink() or (key.exists() and not (same and key.read_text() == value["pem"])):
        raise ValueError("Existing publisher key must be reconciled, never overwritten")
    # The conversion code is single-use. Retain its minimal protected result
    # before later writes, so a local failure never requires another App.
    private_json(pending, {name: value[name] for name in ("id", "slug", "owner", "permissions", "events", "pem")})
    if not key.exists():
        fd = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(value["pem"])
    elif key.stat().st_mode & 0o777 != 0o600 or key.stat().st_uid != os.getuid():
        raise ValueError("Existing App key is not owner-only")
    operator = directory / "operator.json"
    values = json.loads(operator.read_text()) if operator.exists() else {}
    values.update(publisher_app_id=value["id"], publisher_login=value["slug"] + "[bot]", publisher_installation_id=0, write_enabled=False, model_enabled=False)
    private_json(operator, values)
    return value["slug"]


def resume_app(root):
    path = root / ".capstone-agent/issue-automation/enrollment-pending.json"
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o777 != 0o600 or path.stat().st_uid != os.getuid():
        raise ValueError("Owner-only pending enrollment is required")
    return store_app(root, json.loads(path.read_text()))


def accept_installation(root, installation_id):
    if not re.fullmatch(r"[1-9][0-9]{0,15}", installation_id):
        raise ValueError("Invalid installation identity")
    policy, _ = load_policy(root, "main")
    policy = replace(policy, publisher_installation_id=int(installation_id))
    github = GitHub(policy, root=root)
    installation = github._publisher_api("GET", "app/installations/" + installation_id)
    if installation.get("account", {}).get("login") != "uukuguy" or installation.get("repository_selection") != "selected" or installation.get("suspended_at"):
        raise ValueError("Install on the selected capstone repository only")
    # Metadata-only token sees the complete installation, before a write token
    # narrowed to capstone would conceal accidental extra repository grants.
    scope = github._publisher_api("POST", "app/installations/" + installation_id + "/access_tokens", {"permissions": {"metadata": "read"}})
    github.installation_token = scope["token"]
    try:
        repositories = github._publisher_api("GET", "installation/repositories?per_page=100")
        if repositories.get("total_count") != 1 or [row.get("full_name") for row in repositories.get("repositories", [])] != ["uukuguy/capstone"]:
            raise ValueError("Installation includes repositories outside capstone")
    finally:
        del github.installation_token
    actor = github.identity()
    path = root / ".capstone-agent/issue-automation/operator.json"
    values = json.loads(path.read_text())
    values.update(publisher_installation_id=int(installation_id), write_enabled=True, model_enabled=False)
    private_json(path, values)
    return actor


def serve(root, port=18790, resume=False):
    if not 1024 <= port <= 65535:
        raise ValueError("Use an unprivileged loopback port")
    policy, _ = load_policy(root, "main")
    if policy.repository != "uukuguy/capstone" or policy.write_enabled or (policy.publisher_app_id and not resume):
        raise ValueError("Existing identity requires explicit reconciliation")
    directory = root / ".capstone-agent/issue-automation"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    session_file = directory / "enrollment-session.json"
    if resume:
        slug = resume_app(root)
        session = json.loads(session_file.read_text())
        nonce = session["nonce"]
        if not re.fullmatch(r"[A-Za-z0-9_-]{40,64}", nonce) or session["port"] != port:
            raise ValueError("Resume must use the original loopback port")
    else:
        nonce = secrets.token_urlsafe(32)
        private_json(session_file, {"nonce": nonce, "port": port})
    origin = "http://127.0.0.1:" + str(port)
    deadline = time.monotonic() + 3600
    state = {"registered": resume, "installed": False, "slug": slug if resume else None}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Callback URLs contain temporary codes; never log requests.

        def respond(self, body, status=200):
            encoded = ("<!doctype html><html lang='zh-CN'><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>小石身份接入</title><body style='font:16px system-ui;max-width:680px;margin:60px auto;padding:24px;line-height:1.9'>" + body + "</body></html>").encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action https://github.com; base-uri 'none'; frame-ancestors 'none'")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            try:
                if time.monotonic() > deadline or self.headers.get("Host") != "127.0.0.1:" + str(port):
                    self.respond("接入会话已过期或来源不匹配。", 403)
                    return
                url = urlsplit(self.path)
                query = parse_qs(url.query)
                if url.path == "/start/" + nonce and state["registered"]:
                    self.respond("<h1>继续安装现有小石 App</h1><p>后台已恢复原身份；不会再次创建 App。</p><a href='https://github.com/apps/" + html.escape(state["slug"]) + "/installations/new'>只选择 capstone 仓库安装</a>")
                elif url.path == "/start/" + nonce:
                    value = html.escape(json.dumps(manifest(origin, nonce), ensure_ascii=False), quote=True)
                    self.respond("<h1>小石 · Capstone AI</h1><p>创建私有 GitHub App。预填权限仅用于中文 Issues 与 draft PR；不启用 webhook、用户 OAuth、定时任务或付费模型。</p><p>GitHub 创建确认后，再安装到 <strong>Only select repositories → capstone</strong>。后台自动保存私钥并核对身份，不需要复制秘密。</p><form method='post' action='https://github.com/settings/apps/new?state=" + nonce + "'><input type='hidden' name='manifest' value='" + value + "'><button style='padding:12px 18px'>前往 GitHub 确认创建</button></form>")
                elif url.path == "/callback" and not state["registered"] and query.get("state") == [nonce] and len(query.get("code", [])) == 1:
                    slug = store_app(root, exchange(query["code"][0]))
                    state["registered"] = True
                    state["slug"] = slug
                    self.respond("<h1>App 已创建，私钥已受保护保存</h1><p>下一步只选 capstone 仓库安装。</p><a href='https://github.com/apps/" + html.escape(slug) + "/installations/new'>安装小石到 capstone</a>")
                elif url.path == "/installed/" + nonce and state["registered"] and not state["installed"] and len(query.get("installation_id", [])) == 1:
                    actor = accept_installation(root, query["installation_id"][0])
                    state["installed"] = True
                    self.respond("<h1>小石身份接入完成</h1><p>已核对 App、安装和 capstone 仓库，发布身份：" + html.escape(actor) + "。</p><p>后台可按命令处理 Issues；没有启动自动修复、付费模型、合并或部署。</p>")
                else:
                    self.respond("无效或已使用的接入请求。", 404)
            except Exception as error:
                print(json.dumps({"enrollment_error": type(error).__name__}), flush=True)
                self.respond("接入尚未完成。配置保持受保护，请由当前会话核对失败阶段后继续。", 400)

    server = HTTPServer(("127.0.0.1", port), Handler)
    server.timeout = 1
    print(json.dumps({"registration_url": origin + "/start/" + nonce, "expires_seconds": 3600, "mode": "one-time-enrollment"}), flush=True)
    try:
        while not state["installed"] and time.monotonic() <= deadline:
            server.handle_request()
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="One-time Xiaoshi GitHub App registration")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--port", type=int, default=18790)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    serve(args.root.resolve(), args.port, args.resume)
