"""Local installation check using the installed MCP SDK; no Provider call."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import shutil
import sys
import tempfile
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


async def smoke(install: Path) -> dict:
    started = time.monotonic()
    sample = install / "sources/PowerSkills/powerskills-tool/skills/pandapower/case39.json"
    with tempfile.TemporaryDirectory(prefix="sample-", dir=install / "private") as workspace:
        work = Path(workspace)
        staged = work / "case39.json"
        shutil.copyfile(sample, staged)
        parameters = StdioServerParameters(command=str(install / "venv/bin/python"),
            args=[str(install / "sources/PowerMCP/pandapower/panda_mcp.py")], cwd=str(work),
            env={"POWERIO_MCP_ALLOWED_ROOTS": str(work)})
        # This whole verifier was launched with a private environment. SDK default
        # environment merging therefore cannot bring host HOME or credentials back.
        async with stdio_client(parameters) as streams:
            async with ClientSession(*streams) as session:
                initialized = await session.initialize()
                listing = await session.list_tools()
                schemas = {tool.name: tool.model_dump(mode="json", by_alias=True, exclude_none=True) for tool in listing.tools}
                expected = {"audit_network", "create_empty_network", "load_network", "run_power_flow", "validate_operating_point", "run_contingency_analysis", "get_network_info", "load_network_from_any", "load_network_from_json", "export_network_to_format"}
                if set(schemas) != expected:
                    raise ValueError("selected MCP tool catalog changed")
                calls = []
                for name, arguments in [("load_network", {"file_path": str(staged)}), ("get_network_info", {}), ("audit_network", {}), ("run_power_flow", {"algorithm": "nr", "calculate_voltage_angles": True, "max_iteration": 15, "tolerance_mva": 1e-8})]:
                    result = await session.call_tool(name, arguments=arguments)
                    if result.is_error:
                        raise ValueError(f"MCP call failed: {name}")
                    value = result.structured_content
                    if value is None:
                        value = json.loads(next(item.text for item in result.content if item.type == "text"))
                    if set(value) == {"result"} and isinstance(value["result"], dict):
                        value = value["result"]
                    encoded = json.dumps(value, allow_nan=False).encode()
                    if len(encoded) > 1024 * 1024 or value.get("status") != "success":
                        raise ValueError(f"invalid bounded MCP result: {name}, keys={sorted(value)}, status={value.get('status')}")
                    summary = {"status": value["status"]}
                    if name == "load_network":
                        summary["network_info"] = value.get("network_info")
                    if name == "audit_network":
                        summary.update(audit_status=value.get("audit_status"), counts=value.get("counts"))
                    if name == "run_power_flow":
                        summary["converged"] = value.get("results", {}).get("converged")
                        if summary["converged"] is not True:
                            raise ValueError("sample power flow did not converge")
                    public_args = {**arguments}
                    if "file_path" in public_args:
                        public_args["file_path"] = "private-sample/case39.json"
                    calls.append({"tool": name, "arguments": public_args, "input_sha256": digest(public_args),
                        "actual_input_sha256": digest(arguments), "wire_result_sha256": digest(result.model_dump(mode="json", by_alias=True, exclude_none=True)),
                        "result_sha256": hashlib.sha256(encoded).hexdigest(), "result_bytes": len(encoded), "summary": summary})
                receipt = {"schema": "capstone-power-sample-smoke/1", "timestamp": datetime.now(timezone.utc).isoformat(),
                    "runtime_identity": {"python": platform.python_version(), "implementation": platform.python_implementation(), "platform": platform.system(), "machine": platform.machine(), "base_interpreter_sha256": hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest()},
                    "initialize": initialized.model_dump(mode="json", by_alias=True, exclude_none=True),
                    "tool_schemas": schemas, "tool_schema_hashes": {name: digest(schema) for name, schema in schemas.items()},
                    "sample_sha256": hashlib.sha256(staged.read_bytes()).hexdigest(), "calls": calls,
                    "evidence_class": "external_sample_observation", "elapsed_seconds": round(time.monotonic() - started, 3)}
        receipt["process_cleanup"] = "stdio context closed"
    receipt["workspace_cleanup"] = "private sample removed"
    return receipt


if __name__ == "__main__":
    install, output = map(Path, sys.argv[1:])
    result = asyncio.run(asyncio.wait_for(smoke(install.resolve()), timeout=120))
    output.write_text(json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n")
