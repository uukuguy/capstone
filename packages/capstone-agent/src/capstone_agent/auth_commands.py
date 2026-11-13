"""Project-local authentication operations for the Capstone CLI."""

from pathlib import Path

from capability_agent.runtime.locator import PiRuntimeLocator
from capability_agent.runtime.lock import PiRuntimeLock
from capstone_agent.auth_service import AuthService
from capstone_agent.auth_store import CODEX_PROVIDER, ProjectAuthStore
from capstone_agent.runtime import load_runtime_environment


def execute_auth(command: str, root: Path) -> dict[str, object]:
    root = root.resolve()
    store = ProjectAuthStore.from_pi_agent_dir(root / ".grid-agent/auth/pi")
    if command == "auth-import-pi":
        status = store.import_provider(Path.home() / ".pi/agent/auth.json", CODEX_PROVIDER)
    elif command == "auth-login":
        helper = PiRuntimeLocator(
            root / ".grid-agent/runtime/pi", load_runtime_environment(root),
            runtime_lock=PiRuntimeLock.load(root / "configs/runtime/pi-runtime.lock.json"),
            command_env_name="GRID_AGENT_PI_COMMAND",
        ).resolve_oauth_helper()
        status = AuthService(store, helper).login(CODEX_PROVIDER)
    else:
        raise ValueError("unsupported authentication operation")
    return {"provider": status.provider, "configured": status.configured}
