from __future__ import annotations

import json
import os
import subprocess
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4


# Keep this allowlist deliberately small.  These names are runtime inputs for
# executable lookup, locale/time handling, temporary files, Python stream
# encoding/buffering, or Windows process startup; provider, domain, and
# business variables are never ambient inputs to the simulator.
_RUNTIME_ENVIRONMENT_NAMES = frozenset(
    {
        "COMSPEC",
        "__CF_USER_TEXT_ENCODING",
        "LANG",
        "LANGUAGE",
        "PATH",
        "PATHEXT",
        "PYTHONHASHSEED",
        "PYTHONIOENCODING",
        "PYTHONUNBUFFERED",
        "PYTHONUTF8",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "TMPDIR",
        "TZ",
        "WINDIR",
    }
)
# These are the POSIX locale categories consumed by the C/Python runtime.  Do
# not use an ``LC_`` prefix wildcard: an unknown variable must not become an
# ambient channel just because it resembles a locale setting.
_LOCALE_ENVIRONMENT_NAMES = frozenset(
    {
        "LC_ALL",
        "LC_COLLATE",
        "LC_CTYPE",
        "LC_MESSAGES",
        "LC_MONETARY",
        "LC_NUMERIC",
        "LC_TIME",
    }
)


def _is_runtime_environment_name(name: str) -> bool:
    """Return whether an environment name is needed by the simulator runtime."""

    normalized = name.upper()
    return normalized in _RUNTIME_ENVIRONMENT_NAMES or normalized in _LOCALE_ENVIRONMENT_NAMES


def sanitize_environment(
    environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Allow only portable runtime inputs before starting the simulator process."""

    source = dict(os.environ if environment is None else environment)
    return {
        name: value
        for name, value in source.items()
        if _is_runtime_environment_name(name)
    }


class GridctlClientError(RuntimeError):
    """The simulator transport could not produce a valid response."""


class SimulatorOperationError(GridctlClientError):
    """The simulator reported an untyped operation failure."""


class SimulatorCapabilityError(GridctlClientError):
    """The simulator returned a typed capability error envelope."""

    def __init__(self, error: dict[str, object]) -> None:
        super().__init__(str(error.get("message", "Grid capability failed")))
        self.error = error


DEFAULT_MAX_OUTPUT_BYTES = 2 * 1024 * 1024


class GridctlExecutor:
    """Invoke the fixed gridctl capability protocol."""

    def __init__(
        self,
        *,
        executable: Path,
        workspace: Path,
        timeout_seconds: float = 60,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
        environ: Mapping[str, str] | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        if environ is not None and environment is not None:
            raise TypeError("provide only one of environ or environment")
        if max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be positive")
        base_environment = environment if environment is not None else environ
        self.executable = Path(executable)
        self.workspace = Path(workspace)
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = int(max_output_bytes)
        self._environment = sanitize_environment(
            os.environ if base_environment is None else base_environment
        )
        self.last_diagnostics = ""

    def invoke(self, capability: str, arguments: dict[str, object]) -> dict[str, object]:
        request_id = f"sim-{uuid4().hex}"
        request = {
            "protocol": "grid-capability",
            "protocol_version": "1.0",
            "request_id": request_id,
            "capability": capability,
            "arguments": arguments,
        }
        request_bytes = (json.dumps(request, separators=(",", ":")) + "\n").encode("utf-8")
        self.last_diagnostics = ""
        returncode, stdout, stderr, exceeded = self._run_bounded(request_bytes)
        self.last_diagnostics = stderr[:4096].decode("utf-8", errors="ignore")
        if exceeded:
            raise GridctlClientError("Grid simulator process output limit exceeded")
        try:
            lines = stdout.decode("utf-8").splitlines()
        except UnicodeDecodeError as exc:
            raise GridctlClientError("Grid simulator returned invalid UTF-8 stdout") from exc
        if len(lines) != 1:
            raise GridctlClientError("Grid simulator returned an invalid stdout protocol")
        try:
            response = json.loads(lines[0])
        except json.JSONDecodeError as exc:
            raise GridctlClientError("Grid simulator returned non-JSON stdout") from exc
        if not isinstance(response, dict):
            raise GridctlClientError("Grid simulator response does not match its request")
        if (
            response.get("protocol") != "grid-capability"
            or response.get("protocol_version") != "1.0"
            or response.get("request_id") != request_id
        ):
            raise GridctlClientError("Grid simulator response does not match its request")
        if response.get("ok") is not True:
            error = response.get("error") or {}
            if isinstance(error, dict):
                raise SimulatorCapabilityError(error)
            raise SimulatorOperationError("Grid simulator operation failed")
        if returncode != 0:
            raise GridctlClientError("Grid simulator process exited unsuccessfully")
        result = response.get("result")
        if not isinstance(result, dict):
            raise GridctlClientError("Grid simulator response has no result object")
        return result

    def _run_bounded(self, request_bytes: bytes) -> tuple[int, bytes, bytes, bool]:
        try:
            process = subprocess.Popen(
                [str(self.executable), "request", "--workspace", str(self.workspace)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                env=self._environment,
            )
        except OSError as exc:
            raise GridctlClientError("Grid simulator process could not complete") from exc

        stdout_chunks: list[bytes] = []
        stderr_chunks: list[bytes] = []
        output_lock = threading.Lock()
        output_bytes = 0
        exceeded = threading.Event()

        def read_stream(stream: BinaryIO, chunks: list[bytes]) -> None:
            nonlocal output_bytes
            while data := stream.read(8192):
                with output_lock:
                    remaining = self.max_output_bytes - output_bytes
                    if remaining > 0:
                        accepted = data[:remaining]
                        chunks.append(accepted)
                        output_bytes += len(accepted)
                    if len(data) > remaining:
                        exceeded.set()
                        try:
                            process.kill()
                        except OSError:
                            pass
                        break

        def write_request() -> None:
            assert process.stdin is not None
            try:
                process.stdin.write(request_bytes)
                process.stdin.flush()
            except OSError:
                pass
            finally:
                process.stdin.close()

        assert process.stdout is not None and process.stderr is not None
        threads = [
            threading.Thread(target=read_stream, args=(process.stdout, stdout_chunks)),
            threading.Thread(target=read_stream, args=(process.stderr, stderr_chunks)),
            threading.Thread(target=write_request),
        ]
        for thread in threads:
            thread.start()
        try:
            returncode = process.wait(timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.wait()
            raise GridctlClientError("Grid simulator process could not complete") from exc
        finally:
            for thread in threads:
                thread.join()
            process.stdout.close()
            process.stderr.close()
        return returncode, b"".join(stdout_chunks), b"".join(stderr_chunks), exceeded.is_set()

    def call(self, capability: str, arguments: dict[str, object]) -> dict[str, object]:
        return self.invoke(capability, arguments)
