"""Explicit operator installation; runtime resolution never downloads resources."""
from __future__ import annotations

import hashlib
import json
import os
import io
from pathlib import Path
import shutil
import subprocess
import tarfile
import uuid
from typing import NoReturn

from jsonschema import Draft202012Validator, SchemaError, ValidationError
from referencing import Registry
from referencing.exceptions import NoSuchResource, Unresolvable

from .runtime_resources import ROLES, content_hash, safe_path


def verify_source_tree(root: Path, files: dict[str, str]) -> None:
    for name, expected in files.items():
        path = safe_path(root, name)
        lexical = root / name
        if lexical.is_symlink() or any(parent.is_symlink() for parent in lexical.parents if parent != root.parent):
            raise ValueError("source path contains a link")
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"source hash mismatch: {name}")


def _write(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, sort_keys=True, indent=2) + "\n")


def _run(args: list[str], *, env: dict[str, str] | None = None, timeout: int = 600) -> str:
    result = subprocess.run(args, env=env, check=True, capture_output=True, text=True, timeout=timeout)
    return result.stdout


def private_environment(home: Path) -> dict[str, str]:
    home.mkdir(parents=True, exist_ok=True)
    cache = home / "cache"
    cache.mkdir(exist_ok=True)
    temp = home / "tmp"
    temp.mkdir(exist_ok=True)
    return {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "HOME": str(home), "TMPDIR": str(temp),
            "XDG_CACHE_HOME": str(cache), "MPLCONFIGDIR": str(cache / "matplotlib"),
            "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1", "LANG": "en_US.UTF-8"}


def install_managed_resources(config_root: Path, *, source_root: Path | None = None, fetch: bool = True) -> Path:
    config_root = config_root.resolve()
    project = config_root.parent.parent
    lock = json.loads((config_root / "power-samples.lock.json").read_text())
    if lock.get("schema") != "capstone-resource-lock/1":
        raise ValueError("unsupported resource lock")
    # Validate all paths before a fetch, installation or pointer mutation.
    for source in lock["sources"]:
        if source["id"] not in {"PowerSkills", "PowerMCP"}:
            raise ValueError("untrusted source id")
        for name in source["files"]:
            safe_path(project, name)
            if ".." in Path(name).parts:
                raise ValueError("source path contains parent traversal")
    managed = safe_path(project, ".grid-agent/runtime/agent-resources")
    if managed.is_symlink():
        raise ValueError("managed installation path contains a link")
    managed.mkdir(parents=True, exist_ok=True)
    if source_root is None:
        source_root = project / ".grid-agent/runtime/resource-sources"
    source_root = source_root.resolve()
    for source in lock["sources"]:
        tree = source_root / source["id"]
        if not tree.exists() and fetch:
            source_root.mkdir(parents=True, exist_ok=True)
            _run(["git", "clone", "--no-checkout", source["url"], str(tree)])
            _run(["git", "-C", str(tree), "checkout", "--detach", source["commit"]])
        if tree.is_symlink() or not tree.is_dir():
            raise ValueError("source path is missing or linked")
        commit = _run(["git", "-C", str(tree), "rev-parse", "HEAD"]).strip()
        if commit != source["commit"] or _run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"]).strip():
            raise ValueError("source commit or tracked bytes changed")
        verify_source_tree(tree, source["files"])
    install_id = "installs/" + uuid.uuid4().hex
    install = managed / install_id
    install.mkdir(parents=True)
    try:
        _write(install / "installation-lock.json", lock)
        shutil.copyfile(config_root / "prepared-mcp-v1.schema.json", install / "descriptor-schema.json")
        for source in lock["sources"]:
            destination = install / "sources" / source["id"]
            if source["id"] == "PowerMCP":
                # Build from committed objects; ignore local build products entirely.
                archive = subprocess.run(["git", "-C", str(source_root / source["id"]), "archive", source["commit"]], check=True, capture_output=True).stdout
                with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
                    if any(item.issym() or item.islnk() for item in tar.getmembers()):
                        raise ValueError("source archive contains a link")
                    tar.extractall(destination, filter="data")
                verify_source_tree(destination, source["files"])
                continue
            for name in source["files"]:
                file = source_root / source["id"] / name
                target = destination / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(file, target)
        interpreter = install / "venv/bin/python"
        _run(["uv", "venv", "--python", lock["python"], str(install / "venv")])
        requirements = install / "requirements.txt"
        requirements.write_text("\n".join(f"{name}=={version}" for name, version in lock["dependencies"].items() if name != "powermcp") + "\n")
        _run(["uv", "pip", "install", "--python", str(interpreter), "-r", str(requirements)])
        # Build the verified pinned tree, never the upstream personal-config installer.
        _run(["uv", "pip", "install", "--python", str(interpreter), "--no-deps", str(install / "sources/PowerMCP")])
        env = private_environment(install / "private")
        dependencies = json.loads(_run([str(interpreter), "-I", "-c", "import importlib.metadata as m,json; print(json.dumps({d.metadata['Name']: d.version for d in m.distributions()},sort_keys=True))"], env=env))
        if dependencies != lock["dependencies"]:
            raise ValueError("installed dependencies differ from lock")
        _write(install / "dependencies.json", dependencies)
        for role in sorted(ROLES):
            _write(install / "native" / role / "settings.json", {"skills": ["../../sources/PowerSkills/powerskills-tool/skills/pandapower"], "extensions": [], "packages": []})
        receipt_path = install / "smoke.json"
        _run([str(interpreter), "-I", str(project / "tools/power_sample_smoke.py"), str(install), str(receipt_path)], env=env, timeout=180)
        receipt = json.loads(receipt_path.read_text())
        if receipt["tool_schema_hashes"] != lock["tool_schema_hashes"]:
            raise ValueError("actual MCP schemas differ from lock")
        source_files = {"sources/" + source["id"] + "/" + name: digest for source in lock["sources"] for name, digest in source["files"].items()}
        descriptor = {"schema": "capstone-prepared-mcp/1", "install_id": install_id,
            "transport": "stdio", "interpreter": "venv/bin/python", "server": "sources/PowerMCP/pandapower/panda_mcp.py",
            "sources": [{"id": item["id"], "url": item["url"], "commit": item["commit"]} for item in lock["sources"]],
            "source_files": source_files, "dependencies": dependencies,
            "runtime_identity": receipt["runtime_identity"],
            "tool_schemas": receipt["tool_schemas"], "tool_schema_hashes": receipt["tool_schema_hashes"],
            "descriptor_schema_sha256": hashlib.sha256((config_root / "prepared-mcp-v1.schema.json").read_bytes()).hexdigest(),
            "smoke_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(), "lock_sha256": content_hash(lock)}
        _write(install / "prepared-mcp.json", descriptor)
        validated, reason = inspect_installation(managed, install_id=install_id)
        if validated is None:
            raise ValueError(reason)
        # Do not move the venv: its interpreter links and console shebangs remain valid.
        pointer = managed / (".current-" + uuid.uuid4().hex + ".json")
        _write(pointer, {"schema": "capstone-resource-installation/1", "install_id": install_id,
                         "descriptor_sha256": content_hash(descriptor)})
        os.replace(pointer, managed / "current.json")
        return install
    except BaseException:
        # Only this call's unpublished staging directory can be removed.
        shutil.rmtree(install)
        raise


def _deny_schema_retrieval(uri: str) -> NoReturn:
    """References can resolve inside the supplied schema, never through I/O."""
    raise NoSuchResource(ref=uri)


def inspect_installation(managed: Path, *, install_id: str | None = None, expected_descriptor_sha256: str | None = None) -> tuple[dict | None, str | None]:
    """Verify bytes, schema identities and real importability without network access."""
    try:
        if install_id is None:
            pointer = json.loads((managed / "current.json").read_text())
            selected_install_id = pointer["install_id"]
        else:
            pointer = None
            selected_install_id = install_id
        install = safe_path(managed, selected_install_id)
        descriptor = json.loads((install / "prepared-mcp.json").read_text())
        if not isinstance(descriptor, dict):
            raise ValueError("prepared MCP descriptor must be an object")
        descriptor_sha256 = content_hash(descriptor)
        if pointer and pointer["descriptor_sha256"] != descriptor_sha256:
            raise ValueError("prepared MCP descriptor changed")
        if expected_descriptor_sha256 and expected_descriptor_sha256 != descriptor_sha256:
            raise ValueError("accepted MCP descriptor changed")
        retained_schema_bytes = (install / "descriptor-schema.json").read_bytes()
        if descriptor["descriptor_schema_sha256"] != hashlib.sha256(retained_schema_bytes).hexdigest():
            raise ValueError("retained descriptor schema changed")
        config = managed.parents[2] / "configs/runtime"
        # Explicit historical identity uses its retained installation snapshot.
        # The caller must persist and supply the accepted descriptor hash.
        lock_path = install / "installation-lock.json" if install_id else config / "power-samples.lock.json"
        schema_path = install / "descriptor-schema.json" if install_id else config / "prepared-mcp-v1.schema.json"
        lock = json.loads(lock_path.read_text())
        if (descriptor["lock_sha256"] != content_hash(lock)
                or descriptor["descriptor_schema_sha256"] != hashlib.sha256(schema_path.read_bytes()).hexdigest()):
            raise ValueError("prepared MCP schema or lock identity changed")
        schema = json.loads(retained_schema_bytes)
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema, registry=Registry(retrieve=_deny_schema_retrieval)).validate(descriptor)
        if descriptor["install_id"] != selected_install_id or descriptor["server"] != "sources/PowerMCP/pandapower/panda_mcp.py":
            raise ValueError("prepared MCP installation or server identity changed")
        expected_files = {"sources/" + source["id"] + "/" + name: digest for source in lock["sources"] for name, digest in source["files"].items()}
        expected_sources = [{"id": item["id"], "url": item["url"], "commit": item["commit"]} for item in lock["sources"]]
        if (descriptor["source_files"] != expected_files
                or descriptor["sources"] != expected_sources or descriptor["dependencies"] != lock["dependencies"]
                or descriptor["tool_schema_hashes"] != lock["tool_schema_hashes"]):
            raise ValueError("prepared MCP differs from versioned lock")
        verify_source_tree(install, descriptor["source_files"])
        if descriptor["tool_schemas"].keys() != descriptor["tool_schema_hashes"].keys():
            raise ValueError("MCP tool schema catalog changed")
        for name, schema in descriptor["tool_schemas"].items():
            if descriptor["tool_schema_hashes"].get(name) != content_hash(schema):
                raise ValueError("MCP tool schema changed")
        if hashlib.sha256((install / "smoke.json").read_bytes()).hexdigest() != descriptor["smoke_sha256"]:
            raise ValueError("MCP smoke receipt changed")
        if descriptor["interpreter"] != "venv/bin/python":
            raise ValueError("MCP interpreter identity changed")
        server = safe_path(install, descriptor["server"])
        if not server.is_file():
            raise ValueError("MCP server is missing")
        # The only link exception is this fixed venv launcher. Its selected base
        # binary is pinned by the accepted descriptor before any runtime probe.
        interpreter = install / descriptor["interpreter"]
        if hashlib.sha256(interpreter.resolve(strict=True).read_bytes()).hexdigest() != descriptor["runtime_identity"]["base_interpreter_sha256"]:
            raise ValueError("MCP base interpreter bytes changed")
        code = "import pandapower,networkx,powerio,powermcp,mcp.server.mcpserver; import importlib.metadata as m,json,platform,hashlib,pathlib,sys; print(json.dumps({'dependencies':{d.metadata['Name']:d.version for d in m.distributions()},'runtime_identity':{'python':platform.python_version(),'implementation':platform.python_implementation(),'platform':platform.system(),'machine':platform.machine(),'base_interpreter_sha256':hashlib.sha256(pathlib.Path(sys.executable).resolve().read_bytes()).hexdigest()}},sort_keys=True))"
        actual = json.loads(_run([str(interpreter), "-I", "-B", "-c", code], env=private_environment(install / "private"), timeout=30))
        if actual["dependencies"] != descriptor["dependencies"] or actual["runtime_identity"] != descriptor["runtime_identity"]:
            raise ValueError("MCP dependency versions changed")
        return descriptor, None
    except (ValueError, KeyError, OSError, subprocess.SubprocessError, SchemaError, ValidationError, Unresolvable):
        # Public reason contains no exception text with local paths or secrets.
        return None, "managed source, tool schema or dependency verification failed"


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Install pinned project-managed sample resources")
    parser.add_argument("--config-root", type=Path, default=Path("configs/runtime"))
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--no-fetch", action="store_true")
    args = parser.parse_args()
    install = install_managed_resources(args.config_root, source_root=args.source_root, fetch=not args.no_fetch)
    print(json.dumps({"status": "installed", "install_id": install.relative_to(install.parent.parent).as_posix()}))


if __name__ == "__main__":
    main()
