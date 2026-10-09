"""Opt-in combined hosted acceptance with real images and controlled model I/O.

No Python executor, admission, catalog or HTTP route is replaced. Synthetic
Provider responses test composition and source binding, not model quality.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

import httpx
import pytest


@pytest.mark.skipif(os.environ.get("CAPSTONE_WORKSPACE_IMAGE_TESTS") != "1",
                    reason="requires fresh local backend and native images")
def test_combined_hosted_roles_use_real_resources_and_authority(tmp_path):
    backend = os.environ["CAPSTONE_WORKSPACE_BACKEND_IMAGE"]
    native = os.environ["CAPSTONE_WORKSPACE_NATIVE_IMAGE"]
    prefix = "capstone-workspace-test-" + uuid4().hex[:10]
    names: list[str] = []
    volumes = [prefix + "-resources"]
    calls: list[dict] = []
    errors: list[str] = []

    def content(value):
        return value if isinstance(value, str) else "".join(part.get("text", "") for part in value)

    class Provider(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            try:
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                assert self.headers["Authorization"] == "Bearer synthetic-workspace-key"
                calls.append(request)
                tools = {item["function"]["name"]: item["function"] for item in request.get("tools", [])}
                messages = request["messages"]
                previous = [message for message in messages if message["role"] == "tool"]
                if "capstone_context_selection" in tools or "capstone_intent_decision" in tools:
                    raw = content([m for m in messages if m["role"] == "user"][-1]["content"])
                    source = json.loads(raw)
                    selected = source.get("selected_skill", {})
                    professional = selected.get("profile_id") == "harness_engine"
                    refs = [source["objects"][0]["object_id"]] if professional else []
                    if "capstone_context_selection" in tools:
                        name = "capstone_context_selection"
                        arguments = {"schema": "capstone-context-selection-decision/1",
                            "attempt_id": source["attempt_id"], "history_cutoff": source["history_cutoff"],
                            "object_refs": [], "message_refs": [], "clarification_required": False,
                            "clarification": None}
                    else:
                        name = "capstone_intent_decision"
                        arguments = {"schema": "capstone-intent-decision/1", "attempt_id": source["attempt_id"],
                            "history_cutoff": source["history_cutoff"], "relationship": "independent",
                            "clarification": None, "clarification_required": False,
                            "goals": [{"goal_id": "resource_check", "description": source["instruction"],
                                "instruction_excerpt": source["instruction"], "operation": "business_execute" if professional else "answer",
                                "message_refs": [], "object_refs": refs,
                                "capability_refs": [source["capabilities"][0]["capability_id"]] if professional else [],
                                "missing_requirements": [], "depends_on": [], "uses_selected_skill": bool(selected)}]}
                elif "load_network" in tools:
                    user = content([m for m in messages if m["role"] == "user"][-1]["content"])
                    assert '<skill name="pandapower"' in user
                    location = re.search(r'location="([^"]+)"', user).group(1)
                    steps = [("load_network", {"file_path": str(Path(location).parent / "case39.json")}),
                             ("get_network_info", {}), ("audit_network", {}),
                             ("run_power_flow", {"algorithm": "nr", "calculate_voltage_angles": True,
                                 "max_iteration": 15, "tolerance_mva": 1e-8})]
                    for message in previous:
                        observed = json.loads(content(message["content"]))
                        assert observed["structuredContent"]["result"]["status"] == "success"
                    if len(previous) < len(steps):
                        name, arguments = steps[len(previous)]
                    else:
                        assert observed["structuredContent"]["result"]["results"]["converged"] is True
                        name, arguments = None, "Sample resource check complete; this is an external observation."
                else:
                    assert tools and not {"bash", "read", "write", "edit"} & tools.keys()
                    policy = content(messages[0]["content"])
                    assert "Selected professional skill: powerskills-pandapower" in policy
                    def tool(capability):
                        return next(key for key in tools if key.endswith(capability.replace(".", "_")))
                    results = [json.loads(content(m["content"])) for m in previous]
                    assert all(item["ok"] for item in results), results
                    step = len(previous)
                    if step == 0:
                        name = tool("context.open")
                        arguments = {"model_id": tools[name]["parameters"]["properties"]["model_id"]["enum"][0]}
                    elif step == 1:
                        name, arguments = tool("analysis.operation.describe"), {"operation": "diagnostic.structural"}
                    elif step == 2:
                        assert results[1]["result"]["availability"]["status"] == "available"
                        name, arguments = tool("analysis.run"), {"context_ref": results[0]["result"]["context_ref"],
                            "operation": "diagnostic.structural", "options": {}}
                    elif step == 3:
                        name, arguments = tool("evidence.get"), {"evidence_ref": results[2]["result"]["evidence_refs"][0]}
                    else:
                        assert step == 4
                        name, arguments = None, "Authority structural audit completed; convergence and operating security are outside its coverage."
                if name is None:
                    delta, finish = {"role": "assistant", "content": arguments}, "stop"
                else:
                    delta = {"role": "assistant", "tool_calls": [{"index": 0, "id": "call_" + str(len(calls)),
                        "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}]}
                    finish = "tool_calls"
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                for value, reason in ((delta, None), ({}, finish)):
                    chunk = {"id": "fixture", "object": "chat.completion.chunk", "created": 0,
                        "model": "deepseek-flash", "choices": [{"index": 0, "delta": value, "finish_reason": reason}]}
                    self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
                self.wfile.write(b"data: [DONE]\n\n")
            except Exception as exc:
                errors.append(str(exc))
                self.send_error(500)

    provider = ThreadingHTTPServer(("0.0.0.0", 0), Provider)
    provider_thread = threading.Thread(target=provider.serve_forever, daemon=True)
    provider_thread.start()

    def docker(*args):
        return subprocess.run(["docker", *args], check=True, capture_output=True, text=True).stdout.strip()

    def start(role, image, args=(), environment=None, extra=()):
        name = prefix + "-" + role
        names.append(name)
        env = [part for key, value in (environment or {}).items() for part in ("-e", key + "=" + value)]
        docker("run", "-d", "--name", name, "--network", prefix, *env, *extra, image, *args)
        return name

    def ready(origin, path="/health/ready", timeout=180):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                response = httpx.get(origin + path, timeout=5)
                if response.status_code == 200:
                    return response.json()
            except httpx.HTTPError:
                pass
            time.sleep(.2)
        pytest.fail("Service not ready: " + origin + path + "\n" + "\n".join(docker("logs", name) for name in names))

    try:
        docker("network", "create", prefix)
        pg = start("postgres", "postgres:17-alpine", environment={"POSTGRES_USER": "fixture",
            "POSTGRES_PASSWORD": "synthetic-db", "POSTGRES_DB": "fixture"})
        deadline = time.monotonic() + 30
        while subprocess.run(["docker", "exec", pg, "pg_isready", "-U", "fixture"], capture_output=True).returncode:
            assert time.monotonic() < deadline
            time.sleep(.2)
        providers = {"providers": {"deepseek": {"base_url": f"http://host.docker.internal:{provider.server_port}/v1",
            "auth": {"kind": "api_key_env", "default_env": "DEEPSEEK_API_KEY"}, "compatibility_profile": "pi-built-in"}}}
        provider_file = tmp_path / "providers.json"
        provider_file.write_text(json.dumps(providers))
        general = start("general", native, environment={"CAPSTONE_PUBLIC_PROVIDER": "deepseek",
            "CAPSTONE_PUBLIC_MODEL": "deepseek-flash", "DEEPSEEK_API_KEY": "synthetic-workspace-key",
            "CAPSTONE_GENERAL_CONTROL_TOKEN": "synthetic-control"}, extra=("--init", "--cap-drop=ALL",
            "--cap-add=SETUID", "--cap-add=SETGID", "--cap-add=CHOWN", "--cap-add=DAC_OVERRIDE", "--cap-add=KILL",
            "--security-opt=no-new-privileges", "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "--tmpfs", "/var/lib/general-pi/tasks:rw,nosuid,size=256m,mode=0711",
            "--tmpfs", "/var/lib/general-pi/receipts:rw,nosuid,size=64m,mode=0700",
            "--tmpfs", "/var/lib/general-pi/profiles:rw,nosuid,size=64m,mode=0700",
            "--mount", "type=volume,src=" + volumes[0] + ",dst=/opt/general/.grid-agent/runtime,volume-nocopy", "-p", "127.0.0.1::8790", "-v",
            str(provider_file) + ":/opt/general/llm-providers.json:ro"))
        ready("http://" + docker("port", general, "8790"))
        print("Native readiness passed.", flush=True)
        environment = {"DATABASE_URL": f"postgresql://fixture:synthetic-db@{pg}:5432/fixture",
            "CAPSTONE_OPERATOR_TOKEN": "synthetic-operator", "CAPSTONE_ALLOWED_HOSTS": "localhost,127.0.0.1",
            "CAPSTONE_ALLOWED_ORIGINS": "http://localhost:5173", "CAPSTONE_ARTIFACT_BACKEND": "s3",
            "CAPSTONE_ARTIFACT_BUCKET": "fixture-private", "AWS_ACCESS_KEY_ID": "synthetic-object",
            "AWS_SECRET_ACCESS_KEY": "synthetic-object-secret", "AWS_DEFAULT_REGION": "us-east-1",
            "CAPSTONE_PUBLIC_PROVIDER": "deepseek", "CAPSTONE_PUBLIC_MODEL": "deepseek-flash",
            "DEEPSEEK_API_KEY": "synthetic-workspace-key", "GRID_AGENT_LLM_BASE_URL": "http://127.0.0.1:18080/v1",
            "GRID_AGENT_LLM_MAX_RETRIES": "0", "CAPSTONE_THREAD_OPEN_ACCESS": "true",
            "CAPSTONE_GENERAL_EXECUTOR_ORIGIN": f"http://{general}:8790", "CAPSTONE_GENERAL_CONTROL_TOKEN": "synthetic-control",
            "CAPSTONE_FEDERATED_CATALOG_CONTEXT": "true", "CAPSTONE_THREAD_ATTEMPT_TIMEOUT_SECONDS": "180"}
        worker = prefix + "-pandapower"
        pypsa = prefix + "-pypsa"
        environment.update(CAPSTONE_FAMILY_HEALTH_URLS=f"pandapower=http://{worker}:8766,pypsa=http://{pypsa}:8766",
                           CAPSTONE_WORKER_WAKE_URL=f"http://{worker}:8766")
        # Kernel accepts HTTP model transport only on loopback. This fixture
        # forwards the unchanged model HTTP bytes to the controlled host server.
        # All production composition, RPC and tools still run in the image.
        proxy = f'''import threading,subprocess,httpx,json
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
config=Path('/app/.grid-agent/auth/pi');config.mkdir(parents=True,exist_ok=True,mode=0o700)
(config/'models.json').write_text(json.dumps({{'providers':{{'deepseek':{{'baseUrl':'http://127.0.0.1:18080/v1','api':'openai-completions','apiKey':'$DEEPSEEK_API_KEY','models':[{{'id':'deepseek-flash','reasoning':False}}]}}}}}}))
class Proxy(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  body=self.rfile.read(int(self.headers['Content-Length']))
  reply=httpx.post('http://host.docker.internal:{provider.server_port}'+self.path,content=body,headers={{'Authorization':self.headers['Authorization'],'Content-Type':'application/json'}},timeout=120)
  self.send_response(reply.status_code);self.send_header('Content-Type','text/event-stream');self.end_headers();self.wfile.write(reply.content)
server=ThreadingHTTPServer(('127.0.0.1',18080),Proxy)
threading.Thread(target=server.serve_forever,daemon=True).start()
raise SystemExit(subprocess.call(['/app/deploy/entrypoint.sh','worker']))
'''
        worker_entry = ("--entrypoint", "/app/packages/capstone-agent/.venv/bin/python")
        start("pandapower", backend, ("-c", proxy), {**environment, "CAPSTONE_HOSTED_APPLICATION": "pandapower"}, extra=worker_entry)
        start("pypsa", backend, ("-c", proxy), {**environment, "CAPSTONE_HOSTED_APPLICATION": "pypsa",
            "CAPSTONE_WORKER_WAKE_URL": f"http://{pypsa}:8766"}, extra=worker_entry)
        api = start("api", backend, ("api",), {**environment, "CAPSTONE_HOSTED_APPLICATION": "capstone"},
                    extra=("-p", "127.0.0.1::8766"))
        origin = "http://" + docker("port", api, "8766")
        ready(origin)
        print("Hosted API readiness passed.", flush=True)
        identities = [docker("inspect", "-f", "{{.Image}}", name) for name in (api, worker, pypsa)]
        assert len(set(identities)) == 1
        with httpx.Client(base_url=origin, timeout=120) as client:
            created = client.post("/api/v1/threads", json={"model_id": "ieee39"})
            print("Thread creation HTTP status:", created.status_code, flush=True)
            assert created.status_code == 201, created.text
            snapshot = created.json()
            thread_id = snapshot["thread_id"]
            path = "/api/v1/threads/" + thread_id
            def submit(kind, payload):
                snapshot = client.get(path).json()
                response = client.post(path + "/commands", json={"schema": "capstone-command/1",
                    "command_id": "cmd_" + uuid4().hex, "idempotency_key": "idem_" + uuid4().hex,
                    "thread_id": thread_id, "kind": kind, "expected_event_seq": snapshot["last_event_seq"], "payload": payload})
                assert response.status_code == 202, response.text
                assert response.json()["status"] == "accepted", response.text
            for mode, role in (("pi_reference", "direct_pi"), ("capstone", "delegated_pi"), ("capstone", "harness_engine")):
                print("Checking role:", role, flush=True)
                if client.get(path).json()["runtime_mode"] != mode:
                    submit("switch_runtime", {"runtime_mode": mode})
                catalog_response = client.get(path + "/input-catalog")
                assert catalog_response.status_code == 200, catalog_response.text
                catalog = catalog_response.json()
                profile = catalog["resource_profiles"][role]
                skill = next(item for item in profile["resources"] if item["id"] == "powerskills-pandapower")
                assert skill["ready"], skill
                text = "Check the selected business model structure." if role == "harness_engine" else "Check the bundled sample resource; it is not the selected business model."
                event_start = client.get(path).json()["last_event_seq"]
                submit("send_auto", {"text": text, "input": {"kind": "skill_invocation", "text": text,
                    "skill_id": skill["id"], "skill_version": skill["version"]},
                    "resource_profile": {"profile_id": role, "revision": profile["revision"]},
                    "context_selection": {"include_refs": [], "exclude_refs": []}})
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline:
                    events = client.get(path + "/events", params={"after": event_start}).json()["events"]
                    terminal = next((item for item in reversed(events) if item["event_type"] in
                        {"attempt_completed", "attempt_failed", "attempt_interrupted", "attempt_cancelled"}), None)
                    if terminal:
                        if terminal["event_type"] != "attempt_completed":
                            print("Failed terminal:", json.dumps(terminal), flush=True)
                            print("Controlled model requests before failure:", len(calls), flush=True)
                            print("Worker diagnostics:", docker("logs", worker), flush=True)
                        assert terminal["event_type"] == "attempt_completed", (terminal["payload"], errors)
                        if role == "harness_engine":
                            assert terminal["payload"]["admission"]["mode"] == "authority_backed"
                            assert terminal["payload"]["result_refs"] and terminal["payload"]["evidence_refs"]
                        else:
                            assert not terminal["payload"].get("result_refs") and not terminal["payload"].get("evidence_refs")
                        break
                    time.sleep(.25)
                else:
                    pytest.fail("Attempt did not finish: " + str(errors))
                assert not errors, errors
        print("Combined backend image:", identities[0])
        print("Native image:", docker("inspect", "-f", "{{.Image}}", general))
        print("Controlled model requests:", len(calls))
    finally:
        for name in reversed(names):
            subprocess.run(["docker", "rm", "-f", "-v", name], capture_output=True)
        for volume in volumes:
            subprocess.run(["docker", "volume", "rm", volume], capture_output=True)
        subprocess.run(["docker", "network", "rm", prefix], capture_output=True)
        provider.shutdown()
        provider_thread.join(timeout=5)
        provider.server_close()
