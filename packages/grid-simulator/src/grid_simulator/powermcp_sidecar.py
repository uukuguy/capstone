"""Private MCP client entry point; run only with the pinned sidecar interpreter.

This process owns no Capstone model or authority contract. Its parent supplies
one private serialized snapshot and validates the bounded response.
"""
from __future__ import annotations

import asyncio
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import platform
import sys

# Record the SDK's separate kill scope before importing any upstream library.
# The fixed Authority client supplies both paths; no semantic input sets them.
if __name__ == "__main__" and sys.argv[1:2] == ["--server"]:
    import os
    import runpy
    server, marker = map(Path, sys.argv[2:])
    marker.write_text(str(os.getpid()))
    sys.path.insert(0, str(server.parent))
    try:
        runpy.run_path(str(server), run_name="__main__")
    finally:
        marker.unlink(missing_ok=True)
    sys.exit(0)

import pandapower as pp
from pandapower.topology import create_nxgraph, unsupplied_buses
# These modules belong only to the separately pinned sidecar environment.
from mcp import ClientSession, StdioServerParameters  # pyright: ignore[reportMissingImports]
from mcp.client.stdio import stdio_client  # pyright: ignore[reportMissingImports]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def inspect_runtime():
    # Upstream silently drops topology when these imports fail. Test actual
    # graph construction and unsupplied detection, not just package presence.
    net = pp.create_empty_network()
    bus = pp.create_bus(net, vn_kv=110)
    graph = create_nxgraph(net, include_dclines=False)
    graph.add_node(bus)
    if bus not in unsupplied_buses(net, mg=graph):
        raise ValueError("topology prerequisite did not execute")
    return {"dependencies": {d.metadata["Name"]: d.version for d in metadata.distributions()},
            "runtime_identity": {"python": platform.python_version(), "implementation": platform.python_implementation(),
                "platform": platform.system(), "machine": platform.machine(),
                "base_interpreter_sha256": hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest()},
            "topology": "checked"}


def value_of(result):
    if result.is_error:
        raise ValueError("PowerMCP tool failed")
    value = result.structured_content
    if value is None:
        value = json.loads(next(item.text for item in result.content if item.type == "text"))
    if isinstance(value, dict) and set(value) == {"result"} and isinstance(value["result"], dict):
        value = value["result"]
    if len(json.dumps(value, allow_nan=False).encode()) > 1024 * 1024 or value.get("status") != "success":
        raise ValueError("invalid bounded PowerMCP result")
    return value


async def audit(install, snapshot, descriptor):
    actual = inspect_runtime()
    if actual["dependencies"] != descriptor["dependencies"] or actual["runtime_identity"] != descriptor["runtime_identity"]:
        raise ValueError("runtime identity mismatch")
    net = pp.from_json(str(snapshot), convert=False)
    # Force the same topology prerequisites against the current snapshot before
    # trusting the upstream implementation's ImportError catch.
    graph = create_nxgraph(net, include_dclines=False)
    graph.add_nodes_from(net["bus"].index[net["bus"]["in_service"]])
    unsupplied_buses(net, mg=graph)
    parameters = StdioServerParameters(command=str(install / "venv/bin/python"),
        args=["-I", "-B", str(Path(__file__).resolve()), "--server", str(install / descriptor["server"]), str(snapshot.parent / "mcp-server.pid")], cwd=str(snapshot.parent),
        env={"POWERIO_MCP_ALLOWED_ROOTS": str(snapshot.parent)})
    calls = []
    report = None
    async with stdio_client(parameters) as streams:
        async with ClientSession(*streams) as session:
            initialized = await session.initialize()
            listing = await session.list_tools()
            hashes = {t.name: digest(t.model_dump(mode="json", by_alias=True, exclude_none=True)) for t in listing.tools}
            if hashes != descriptor["tool_schema_hashes"]:
                raise ValueError("live tool schemas changed")
            for name, arguments in [("load_network", {"file_path": str(snapshot)}), ("audit_network", {})]:
                result = await session.call_tool(name, arguments=arguments)
                value = value_of(result)
                if name == "load_network":
                    info = value["network_info"]
                    for key, table in [("buses", "bus"), ("lines", "line"), ("trafos", "trafo")]:
                        if info[key] != len(net[table]):
                            raise ValueError("loaded snapshot count mismatch")
                calls.append({"tool": name, "wire_result_sha256": digest(result.model_dump(mode="json", by_alias=True, exclude_none=True)),
                              "result_sha256": digest(value)})
                if name == "audit_network":
                    report = value
    if report is None:
        raise ValueError("PowerMCP audit report is missing")
    return {"report": report,
            "coverage": {"bus_service_and_voltage_limits": "checked", "line_parameters_and_ratings": "checked",
                "transformer_ratings_and_impedance": "checked", "topology": "checked",
                "powerflow_convergence": "not_checked", "operating_security": "not_checked", "all_pandapower_input_defects": "not_checked"},
            "provenance": {"backend": "PowerMCP", "adapter_version": "grid-structural-audit/1",
                "upstream_commit": next(s["commit"] for s in descriptor["sources"] if s["id"] == "PowerMCP"),
                "server_sha256": descriptor["source_files"][descriptor["server"]],
                "adapter_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "descriptor_sha256": digest(descriptor), "input_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
                "runtime_identity": actual["runtime_identity"], "runtime_versions": actual["dependencies"],
                "tool_schema_hashes": {n: hashes[n] for n in ("load_network", "audit_network")},
                "mcp_protocol_version": initialized.protocol_version, "calls": calls,
                "process_cleanup": "stdio context closed"}}


if __name__ == "__main__":
    if sys.argv[1:] == ["--inspect"]:
        response = inspect_runtime()
    else:
        install, snapshot, descriptor_path = map(Path, sys.argv[1:])
        response = asyncio.run(asyncio.wait_for(audit(install, snapshot, json.loads(descriptor_path.read_text())), timeout=35))
    print(json.dumps(response, sort_keys=True, separators=(",", ":"), allow_nan=False))
