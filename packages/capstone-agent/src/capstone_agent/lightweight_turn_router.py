"""Tool-free route selection in front of the existing execution chains."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile

from capability_agent.runtime.environment import PiLaunch, RuntimePaths, build_pi_launch
from capability_agent.runtime.rpc import PiRpcClient
from capability_agent.runtime.trace import JsonlTraceWriter

from .turn_router import DecisionUnavailable, RoutingInput, TurnPlan


_POLICY = '''Classify the user's request. You have no tools.
Return exactly {"schema":"capstone-intent-route/1","route":"general|professional"}.
Choose professional for the selected business model or its domain, including
questions about that model and its capabilities. Choose general for independent
conversation or general work. Mixed business work takes the professional route.
Do not answer, plan, compile parameters, check capabilities or ask for inputs.
Task complexity and current ability to complete it do not change its route.
'''


class LightweightTurnRouter:
    requires_decision = True

    def __init__(self, classify):
        self._classify = classify

    def plan(self, request: RoutingInput) -> TurnPlan:
        route = self._classify(request)
        if route not in {"ordinary", "professional"}:
            raise DecisionUnavailable("llm_route_invalid")
        return TurnPlan(request.turn_id, request.attempt_id, route, "llm",
                        "turn-plan-v1", None, request.context_snapshot)


def build_lightweight_router(*, runtime_host, resolved_llm, environment, timeout_seconds=15):
    def classify(request):
        with tempfile.TemporaryDirectory(prefix="capstone-route-") as directory:
            root = Path(directory).resolve()
            policy = root / "policy.md"
            policy.write_text(_POLICY, encoding="utf-8")
            policy.chmod(0o600)
            paths = RuntimePaths(command=runtime_host.command, project_pi_dir=runtime_host.project_pi_dir,
                session_dir=root / "session", workspace=root, system_policy_path=policy)
            original = build_pi_launch(resolved_llm, paths, base_environment=environment)
            launch = PiLaunch((*original.argv, "--thinking", "off"), original.environment)
            secrets = {resolved_llm.secret.value} if resolved_llm.secret is not None else set()
            client = PiRpcClient(launch, _Workspace(root),
                JsonlTraceWriter(root / "events.jsonl", secret_values=secrets),
                secret_values=secrets, timeout_seconds=timeout_seconds)
            try:
                client.start()
                output = client.prompt_and_wait(json.dumps({"instruction": request.instruction,
                    "selected_model": dict(request.context_snapshot)}, ensure_ascii=False))
                document = json.loads(output)
                if (not isinstance(document, dict) or set(document) != {"schema", "route"}
                        or document["schema"] != "capstone-intent-route/1"
                        or document["route"] not in {"general", "professional"}):
                    raise DecisionUnavailable("llm_route_invalid")
                return "ordinary" if document["route"] == "general" else "professional"
            finally:
                client.stop()
    return LightweightTurnRouter(classify)


class _Workspace:
    def __init__(self, root):
        self.root = root
        self.root_path = root

    def set_correlation(self, *_args, **_kwargs):
        return None
