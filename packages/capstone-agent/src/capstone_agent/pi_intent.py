"""Application-owned Pi request recognition and native conversation loading."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import time

from capability_agent.application.workspace import ApplicationWorkspace
from capability_agent.runtime.environment import PiLaunch, RuntimeHost, RuntimePaths, build_pi_launch
from capability_agent.runtime.models import ResolvedLLM
from capability_agent.runtime.rpc import PiRpcClient
from capability_agent.runtime.trace import JsonlTraceWriter

from .harness import AdmittedAttemptAnswer, PiPromptSession
from .request_intent import IntentDecision, IntentEngineIdentity, IntentRequest, NodeControl


_RESOURCES = Path(__file__).parent / "resources"
_CONFIG_NAMES = ("SYSTEM.md", "APPEND_SYSTEM.md", "INTENT.md", "settings.json")
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,255}\Z")


class PiIntentRecognizer:
    """Require one validated structured decision; never infer from answer prose."""

    def __init__(self, prepared_session_factory: Callable[[IntentRequest, NodeControl], PiPromptSession],
                 identity: IntentEngineIdentity) -> None:
        if not callable(prepared_session_factory):
            raise TypeError("intent session factory must be callable")
        if not isinstance(identity, IntentEngineIdentity):
            raise TypeError("intent engine identity is required")
        self._factory = prepared_session_factory
        self.identity = identity

    def recognize(self, request: IntentRequest, control: NodeControl) -> IntentDecision:
        control.checkpoint()
        session = self._factory(request, control)
        decisions: list[IntentDecision] = []

        def observe(event: Mapping[str, object]) -> None:
            control.checkpoint()
            if event.get("type") != "tool_result":
                return
            if event.get("capability") != "capstone.intent.decision" or event.get("ok") is not True:
                raise ValueError("intent stage returned an unexpected tool result")
            if decisions:
                raise ValueError("Pi must return exactly one intent decision")
            document = event.get("result")
            if not isinstance(document, dict):
                raise ValueError("Pi intent decision must be an object")
            decisions.append(IntentDecision.from_document(document, request))

        try:
            control.checkpoint()
            session.start()
            control.checkpoint()
            session.prompt_and_wait(
                json.dumps(request.to_document(), ensure_ascii=False, separators=(",", ":")),
                on_semantic_event=observe, correlation_id=request.request_id,
                on_heartbeat=control.checkpoint,
            )
            control.checkpoint()
            if len(decisions) != 1:
                raise ValueError("Pi must return exactly one intent decision")
            return decisions[0]
        finally:
            session.stop()


def _attempt_directory(workspace: ApplicationWorkspace, attempt_id: str) -> Path:
    if not isinstance(attempt_id, str) or not _SAFE_ID.fullmatch(attempt_id) or attempt_id in {".", ".."}:
        raise ValueError("Pi attempt identifier is invalid")
    directory = workspace.core_path / "pi" / "attempts" / attempt_id
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    return directory


def _write_json(path: Path, document: object) -> None:
    payload = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(payload.encode("utf-8")) > 524_288:
        raise ValueError("Pi message projection exceeds its limit")
    path.write_text(payload + "\n", encoding="utf-8")
    path.chmod(0o600)


def prepare_context_launch(launch: PiLaunch, workspace: ApplicationWorkspace,
                           attempt_id: str, messages: list[dict],
                           supplemental_context: dict) -> PiLaunch:
    """Add bounded message data through a trusted native Pi context extension.

    The caller retains tool selection and system configuration. This also serves
    prepared business sessions without importing Domain Pack state.
    """
    if not isinstance(messages, list) or len(messages) > 256:
        raise ValueError("Pi shared history is invalid")
    for message in messages:
        if not isinstance(message, dict) or message.get("role") not in {"user", "assistant"}:
            raise ValueError("Pi shared history role is invalid")
        if not isinstance(message.get("content"), str) or not isinstance(message.get("status"), str):
            raise ValueError("Pi shared history content or status is invalid")
    if not isinstance(supplemental_context, dict):
        raise ValueError("Pi supplemental context must be a document")
    directory = _attempt_directory(workspace, attempt_id)
    path = directory / "conversation-context.json"
    _write_json(path, {"schema": "capstone-pi-context/1", "attempt_id": attempt_id,
                       "messages": messages, "supplemental_context": supplemental_context})
    environment = dict(launch.environment)
    environment["CAPSTONE_PI_CONTEXT_PATH"] = str(path)
    extension = str(_RESOURCES / "conversation-context.mjs")
    argv = launch.argv if extension in launch.argv else (*launch.argv, "--extension", extension)
    return PiLaunch(tuple(argv), environment)


def default_config_root() -> Path:
    """Select checked-in configuration, or the same assets included in a wheel."""
    source = Path(__file__).resolve().parents[4] / "configs" / "runtime" / "capstone-pi"
    return source if source.is_dir() else _RESOURCES / "capstone-pi"


class NativeConversationPiSessionBuilder:
    """Load application configuration with Pi's public file and message APIs."""

    def __init__(self, *, runtime_host: RuntimeHost, resolved_llm: ResolvedLLM,
                 workspace_root: Path, base_environment: Mapping[str, str] | None = None,
                 config_root: Path | None = None) -> None:
        self._host = runtime_host
        self._llm = resolved_llm
        self._workspace_root = Path(workspace_root)
        self._environment = base_environment
        self._domain_policy = runtime_host.system_policy_path.read_bytes() if (
            runtime_host.system_policy_path is not None and runtime_host.system_policy_path.is_file()
        ) else None
        # Pi reads this selected protected transport configuration directly.
        # Bind its digest for replay; never copy or display its contents.
        transport_config = runtime_host.project_pi_dir / "models.json"
        self._transport_sha256 = sha256(transport_config.read_bytes()).hexdigest() if transport_config.is_file() else None
        global_settings = runtime_host.project_pi_dir / "settings.json"
        self._global_settings_sha256 = sha256(global_settings.read_bytes()).hexdigest() if global_settings.is_file() else None
        root = default_config_root() if config_root is None else Path(config_root)
        self._config: dict[str, bytes] = {}
        for name in _CONFIG_NAMES:
            path = root / name
            if not path.is_file():
                raise ValueError(f"Pi application configuration is missing: {name}")
            content = path.read_bytes()
            if not content or len(content) > 128_000:
                raise ValueError("Pi application configuration is invalid")
            self._config[name] = content
        settings = json.loads(self._config["settings.json"])
        if not isinstance(settings, dict) or set(settings) - {"compaction", "retry", "enableSkillCommands"}:
            raise ValueError("Pi application settings contain unsupported keys")
        digest = sha256()
        for name, content in self._config.items():
            digest.update(name.encode() + b"\0" + content + b"\0")
        for name in ("conversation-context.mjs", "intent-decision.mjs"):
            digest.update(name.encode() + b"\0" + (_RESOURCES / name).read_bytes() + b"\0")
        digest.update(json.dumps({
            "provider": resolved_llm.config.provider, "model": resolved_llm.config.model,
            "base_url": resolved_llm.config.base_url, "pi_provider": resolved_llm.config.pi_provider,
            "compatibility_profile": resolved_llm.config.compatibility_profile,
            "public_headers": dict(resolved_llm.config.public_headers),
            "auth_kind": resolved_llm.config.auth_kind,
            "credential_reference": resolved_llm.config.credential_reference,
            "timeout_seconds": resolved_llm.config.timeout_seconds,
            "max_retries": resolved_llm.config.max_retries,
            "supports_tools": resolved_llm.config.supports_tools,
            "descriptor_version": resolved_llm.config.descriptor_version,
            "runtime_lock": runtime_host.command.identity.lock_sha256,
            "runtime_commit": runtime_host.command.identity.commit,
            "runtime_patches": runtime_host.command.identity.patches_sha256,
            "runtime_command": list(runtime_host.command.argv),
            "protected_transport_sha256": self._transport_sha256,
            "protected_global_settings_sha256": self._global_settings_sha256,
            "domain_policy_sha256": sha256(self._domain_policy).hexdigest() if self._domain_policy is not None else None,
        }, sort_keys=True, separators=(",", ":")).encode())
        self.config_revision = "sha256:" + digest.hexdigest()
        self.identity = IntentEngineIdentity(engine="pi", model=resolved_llm.config.model,
                                            config_revision=self.config_revision)

    def build_intent(self, request: IntentRequest, control: NodeControl) -> PiPromptSession:
        control.checkpoint()
        document = request.to_document()
        return self._build(request.request_id, document["messages"],
            {"phase": "intent", "request": {key: value for key, value in document.items() if key != "messages"}},
            intent=True, control=control)

    def build_execution(self, claim: object, decision: IntentDecision) -> PiPromptSession:
        request = getattr(claim, "intent_request", None)
        if request is None:
            request = getattr(getattr(claim, "turn_plan", None), "intent_request", None)
        if not isinstance(request, IntentRequest):
            raise ValueError("Execution requires the fixed intent request snapshot")
        document = request.to_document()
        checked = IntentDecision.from_document(decision.to_document(), request)
        goals = checked.to_document()["goals"]
        object_refs = {ref for goal in goals for ref in goal["object_refs"]}
        capability_refs = {ref for goal in goals for ref in goal["capability_refs"]}
        supplemental = {
            "phase": "execution", "history_cutoff": document["history_cutoff"],
            "history_truncated": document.get('history_truncated', False),
            "decision": checked.to_document(),
            "executable_goal_ids": [goal["goal_id"] for goal in checked.execution_goals],
            "objects": [item for item in document["objects"] if item["object_id"] in object_refs],
            "capabilities": [item for item in document["capabilities"] if item["capability_id"] in capability_refs],
        }
        if any(goal["operation"] == "catalog_lookup" for goal in goals):
            supplemental["application_catalog"] = getattr(claim, "application_catalog", None)
        return self._build(request.request_id, document["messages"], supplemental, intent=False)

    def _build(self, attempt_id: str, messages: list[dict], supplemental: dict, *,
               intent: bool, control: NodeControl | None = None) -> PiPromptSession:
        workspace = ApplicationWorkspace.create(self._workspace_root)
        directory = _attempt_directory(workspace, attempt_id)
        paths = RuntimePaths(command=self._host.command,
            project_pi_dir=self._host.project_pi_dir, session_dir=directory / "session",
            workspace=workspace.root)
        launch = build_pi_launch(self._llm, paths, base_environment=self._environment)
        launch = self.apply_configuration(launch, workspace, attempt_id, intent=intent)
        launch = prepare_context_launch(launch, workspace, attempt_id, messages, supplemental)
        secrets = {self._llm.secret.value} if self._llm.secret is not None else set()
        trace = JsonlTraceWriter(workspace.core_path / "pi-events.jsonl", secret_values=secrets)
        timeout = self._llm.config.timeout_seconds
        if control is not None and control.deadline is not None:
            control.checkpoint()
            timeout = min(timeout, max(0.001, control.deadline - time.monotonic()))
        client = PiRpcClient(launch, _RpcWorkspace(workspace.root), trace, secret_values=secrets,
                             correlation_id=attempt_id, timeout_seconds=timeout)
        return _ConversationPiPromptSession(client, trace, intent=intent)

    def apply_configuration(self, launch: PiLaunch, workspace: ApplicationWorkspace,
                            attempt_id: str, *, intent: bool = False,
                            domain_policy: Path | None = None) -> PiLaunch:
        """Select native base configuration and optional domain policy for a launch.

        The existing launch retains its prepared tools and protected provider
        configuration. The caller must run Pi from ``workspace.root``.
        """
        if intent and domain_policy is not None:
            raise ValueError("Intent preparation cannot load a domain policy")
        transport_config = self._host.project_pi_dir / "models.json"
        current_transport_sha256 = sha256(transport_config.read_bytes()).hexdigest() if transport_config.is_file() else None
        if current_transport_sha256 != self._transport_sha256:
            raise ValueError("Pi transport configuration changed since the snapshot")
        global_settings = self._host.project_pi_dir / "settings.json"
        current_global_settings_sha256 = sha256(global_settings.read_bytes()).hexdigest() if global_settings.is_file() else None
        if current_global_settings_sha256 != self._global_settings_sha256:
            raise ValueError("Pi global settings changed since the snapshot")
        directory = _attempt_directory(workspace, attempt_id)
        config_dir = directory / "config"
        config_dir.mkdir(mode=0o700, exist_ok=True)
        for name, content in self._config.items():
            path = config_dir / name
            path.write_bytes(content)
            path.chmod(0o600)
        (workspace.root / ".pi").mkdir(mode=0o700, exist_ok=True)
        settings_path = workspace.root / ".pi" / "settings.json"
        settings_path.write_bytes(self._config["settings.json"])
        settings_path.chmod(0o600)
        retained = []
        arguments = iter(launch.argv)
        for argument in arguments:
            if argument in {"--system-prompt", "--append-system-prompt"}:
                next(arguments, None)
            else:
                retained.append(argument)
        # Pi's native offline flag disables startup installs and checks, while
        # retaining the selected Provider transport for explicit model requests.
        argv = (*retained, "--approve", "--offline", "--system-prompt", str(config_dir / "SYSTEM.md"),
                "--append-system-prompt", str(config_dir / "APPEND_SYSTEM.md"))
        if intent:
            argv = (*argv, "--no-session", "--append-system-prompt", str(config_dir / "INTENT.md"),
                    "--extension", str(_RESOURCES / "intent-decision.mjs"))
        if domain_policy is not None:
            if domain_policy != self._host.system_policy_path or self._domain_policy is None:
                raise ValueError("Selected domain policy is not bound to the configuration snapshot")
            domain_snapshot = config_dir / "DOMAIN.md"
            domain_snapshot.write_bytes(self._domain_policy)
            domain_snapshot.chmod(0o600)
            argv = (*argv, "--append-system-prompt", str(domain_snapshot))
        loaded_files = [{"path": str(settings_path if name == "settings.json" else config_dir / name),
                         "sha256": sha256(self._config[name]).hexdigest()}
                        for name in ("SYSTEM.md", "APPEND_SYSTEM.md", "settings.json")]
        if intent:
            loaded_files.append({"path": str(config_dir / "INTENT.md"),
                                 "sha256": sha256(self._config["INTENT.md"]).hexdigest()})
        if domain_policy is not None:
            loaded_files.append({"path": str(config_dir / "DOMAIN.md"),
                                 "sha256": sha256(self._domain_policy or b"").hexdigest()})
        _write_json(directory / "config-manifest.json", {
            "schema": "capstone-pi-config/1", "config_revision": self.config_revision,
            "phase": "intent" if intent else "execution",
            "protected_transport_sha256": self._transport_sha256,
            "protected_global_settings_sha256": self._global_settings_sha256,
            "files": loaded_files,
        })
        return PiLaunch(tuple(argv), dict(launch.environment))


@dataclass(frozen=True)
class _RpcWorkspace:
    root_path: Path


class _ConversationPiPromptSession:
    def __init__(self, client: PiRpcClient, trace: JsonlTraceWriter, *, intent: bool) -> None:
        self._client, self._trace, self._intent = client, trace, intent

    def start(self) -> None:
        self._client.start()

    def prompt_and_wait(self, question: str, *, on_semantic_event: Callable,
                        correlation_id: str | None, on_heartbeat: Callable) -> str:
        return self._client.prompt_and_wait(question,
            on_semantic_event=lambda event, sequence: on_semantic_event(event),
            correlation_id=correlation_id, on_heartbeat=on_heartbeat,
            heartbeat_seconds=1.0, require_answer_text=not self._intent)

    def stop(self) -> None:
        try:
            self._client.stop()
        finally:
            self._trace.close()

    def admit_attempt(self, claim: object, answer: str, result_refs: tuple[str, ...],
                      evidence_refs: tuple[str, ...], tool_events: tuple[Mapping[str, object], ...]) -> AdmittedAttemptAnswer:
        if self._intent or result_refs or evidence_refs or tool_events:
            raise ValueError("ordinary session cannot admit tool activity or authority references")
        return AdmittedAttemptAnswer(answer, "offline_information", "general_knowledge")
