#!/usr/bin/env python3
"""Maintain only proven Capstone Docker objects. Dry-run unless --apply is given."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


PROJECT = "capstone"
CACHE_ID = re.compile(r"[a-z0-9]{12,64}\Z")
IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
# Generic WORKDIR, apt, base layers and local-source records are not evidence.
STRONG_COMMAND = re.compile(
    r"(?:packages/(?:capstone-agent|capability-agent-kernel|enterprise-research-domain-pack|"
    r"pandapower-domain-pack|pypsa-domain-pack|pypsa-agent|grid-agent|grid-simulator)(?:/|\s|$)"
    r"|\bcapstone_agent(?:/|\.|\s|$)|\bcapstone-report\b)"
)


def json_records(output: str) -> list[dict]:
    """Buildx emits JSON lines; Docker inspect can emit an array."""
    if not output.strip():
        return []
    try:
        value = json.loads(output)
        records = value if isinstance(value, list) else [value]
    except json.JSONDecodeError:
        records = [json.loads(line) for line in output.splitlines() if line.strip()]
    if not all(isinstance(item, dict) for item in records):
        raise ValueError("Docker inventory must contain JSON objects")
    return records


def select_images(images: list[dict], containers: list[dict]) -> list[str]:
    referenced = {item.get("Image") for item in containers}
    selected = set()
    for item in images:
        identifier = item.get("Id", "")
        labels = (item.get("Config") or {}).get("Labels") or {}
        if (IMAGE_ID.fullmatch(identifier) and identifier not in referenced
                and labels.get("com.docker.compose.project") == PROJECT
                and not item.get("RepoTags") and not item.get("RepoDigests")):
            selected.add(identifier)
    return sorted(selected)


def select_cache(records: list[dict]) -> list[str]:
    indexed = {}
    for item in records:
        identifier = item.get("ID", "")
        if not isinstance(identifier, str) or not CACHE_ID.fullmatch(identifier):
            raise ValueError("invalid cache ID; refusing cleanup")
        if identifier in indexed:
            raise ValueError("duplicate cache ID; refusing ambiguous inventory")
        indexed[identifier] = item
    # Shared builders may contain other projects inheriting a Capstone layer.
    # Neither ancestors nor descendants inherit project ownership here.
    owned = {key for key, item in indexed.items()
             if STRONG_COMMAND.search(item.get("Description", ""))}
    return sorted(key for key in owned
                  if indexed[key].get("Reclaimable") is True
                  and indexed[key].get("Shared") is False)


def cache_filter(identifiers: list[str]) -> str:
    if not identifiers or any(not CACHE_ID.fullmatch(key) for key in identifiers):
        raise ValueError("refusing empty or unsafe cache filter")
    # Buildx multiple filters are AND, so one anchored regex supplies the OR.
    return "id~=^(" + "|".join(sorted(set(identifiers))) + ")$"


def verify_filter_result(selected: list[str], matched: list[dict]) -> None:
    if any(item.get("ID") not in set(selected) for item in matched):
        raise ValueError("cache filter returned an unselected ID; refusing prune")


def space_bytes(value: str) -> int:
    match = re.fullmatch(r"([1-9][0-9]*)(B|KB|MB|GB|TB|KiB|MiB|GiB|TiB)", value)
    if not match:
        raise ValueError("cache budgets must be positive sizes, for example 40GB")
    unit = match[2]
    exponent = {"B": 0, "KB": 1, "MB": 2, "GB": 3, "TB": 4,
                "KiB": 1, "MiB": 2, "GiB": 3, "TiB": 4}[unit]
    return int(match[1]) * (1024 if "i" in unit else 1000) ** exponent


def check_budgets(max_used: str, reserved: str) -> None:
    if space_bytes(reserved) > space_bytes(max_used):
        raise ValueError("cache reserved space must not exceed max-used space")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="perform the scoped plan")
    parser.add_argument("--builder", default=os.environ.get("CAPSTONE_LOCAL_CACHE_BUILDER"))
    parser.add_argument("--max-used-space", default=os.environ.get(
        "CAPSTONE_LOCAL_CACHE_MAX_USED_SPACE", "40GB"))
    parser.add_argument("--reserved-space", default=os.environ.get(
        "CAPSTONE_LOCAL_CACHE_RESERVED_SPACE", "20GB"))
    return parser.parse_args(argv)


def run(arguments: list[str]) -> str:
    result = subprocess.run(arguments, text=True, capture_output=True, check=False)
    if result.returncode:
        # Raw CLI errors can include daemon details; retain a safe command identity.
        raise RuntimeError(f"{' '.join(arguments[:3])} failed (exit {result.returncode})")
    return result.stdout


def inspect_images(identifiers: list[str]) -> list[dict]:
    # Only safe fields; never load image/container environment or credentials.
    template = ('{"Id":{{json .Id}},"RepoTags":{{json .RepoTags}},'
                '"RepoDigests":{{json .RepoDigests}},"Config":{"Labels":'
                '{"com.docker.compose.project":'
                '{{json (index .Config.Labels "com.docker.compose.project")}}}}}')
    records = []
    for start in range(0, len(identifiers), 64):
        records.extend(json_records(run(["docker", "image", "inspect", "--format",
                                         template, *identifiers[start:start + 64]])))
    return records


def image_inventory() -> tuple[list[dict], list[dict]]:
    ids = sorted(set(run(["docker", "image", "ls", "--all", "--quiet", "--no-trunc",
                          "--filter", f"label=com.docker.compose.project={PROJECT}"]).split()))
    containers = run(["docker", "container", "ls", "--all", "--quiet"]).split()
    referenced = []
    for start in range(0, len(containers), 64):
        values = run(["docker", "container", "inspect", "--format", "{{.Image}}",
                      *containers[start:start + 64]]).split()
        referenced.extend({"Image": value} for value in values)
    return inspect_images(ids), referenced


def cache_inventory(builder: str, selector: str | None = None) -> list[dict]:
    command = ["docker", "buildx", "du", "--builder", builder, "--format", "json"]
    if selector:
        command.extend(["--filter", selector])
    return json_records(run(command))


def maintain(args: argparse.Namespace) -> dict:
    check_budgets(args.max_used_space, args.reserved_space)
    builder = args.builder
    if not builder:
        current = [item.get("Name") for item in json_records(
            run(["docker", "buildx", "ls", "--format=json"]))
            if item.get("Current") is True and not item.get("Err")]
        if len(current) != 1 or not isinstance(current[0], str):
            raise ValueError("cannot identify one current builder; refusing cleanup")
        builder = current[0]
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+", builder):
        raise ValueError("invalid builder identity")
    images, containers = image_inventory()
    image_ids = select_images(images, containers)
    cache_ids = select_cache(cache_inventory(builder))
    result = {"mode": "apply" if args.apply else "dry-run", "project": PROJECT,
              "builder": builder, "image_ids": image_ids, "cache_ids": cache_ids,
              "max_used_space": args.max_used_space, "reserved_space": args.reserved_space}
    # Print the exact plan first, including in a failed apply. No secrets/descriptions.
    print(json.dumps(result, sort_keys=True), flush=True)
    if not args.apply:
        return result
    # Recheck all container refs/tags before image removal. Never use image rm --force.
    fresh_images, fresh_containers = image_inventory()
    eligible = set(select_images(fresh_images, fresh_containers))
    for identifier in image_ids:
        if identifier in eligible:
            run(["docker", "image", "rm", "--no-prune", identifier])
    # Ownership may change concurrently. Use the intersection, not fresh new IDs.
    current = set(select_cache(cache_inventory(builder)))
    selected = sorted(current.intersection(cache_ids))
    if selected:
        selector = cache_filter(selected)
        matched = cache_inventory(builder, selector)
        verify_filter_result(selected, matched)
        if matched:
            run(["docker", "buildx", "prune", "--builder", builder, "--force",
                 "--filter", selector, "--filter", "inuse=false", "--filter", "shared=false",
                 "--max-used-space", args.max_used_space, "--reserved-space", args.reserved_space])
    return result


@contextmanager
def maintenance_lock(path: Path | None = None):
    """One helper across this user's worktrees; never wait behind another prune."""
    path = path or Path(tempfile.gettempdir()) / f"capstone-cache-maintenance-{os.getuid()}.lock"
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
        else:
            try:
                yield True
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def main() -> int:
    try:
        args = parse_args()
        if args.apply:
            with maintenance_lock() as acquired:
                if not acquired:
                    print("Capstone cache maintenance skipped: another helper holds the lock")
                    return 0
                maintain(args)
        else:
            maintain(args)
    except (ValueError, RuntimeError, OSError) as error:
        print(f"Capstone cache maintenance failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
