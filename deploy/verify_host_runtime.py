"""Compare secret-free local and cloud runtime receipts before acceptance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


def verify(local: dict, cloud: dict, contract: dict, expected_contract_hash: str) -> None:
    roles = set(contract["roles"])
    if set(local) != roles or set(cloud) != roles:
        raise ValueError("runtime roles differ")
    contract_hashes = set()
    sources = set()
    stage_artifacts = []
    architectures = []
    for expected_stage, receipts in [("local", local), ("cloud-development", cloud)]:
        artifacts = set()
        stage_architectures = set()
        for role, receipt in receipts.items():
            expected = {"schema": "capstone-host-runtime-receipt/1",
                        "profile": contract["profile"], "stage": expected_stage,
                        "role": role, "application": contract["roles"][role]["application"],
                        "dependencies_ready": True, "provider_configured": role != "api"}
            if any(receipt.get(key) != value for key, value in expected.items()):
                raise ValueError("runtime receipt differs: " + role)
            contract_hashes.add(receipt.get("contract_sha256"))
            artifacts.add(receipt.get("artifact_sha256"))
            sources.add(receipt.get('source_artifact_sha256'))
            stage_architectures.add(receipt.get('architecture'))
        if len(artifacts) != 1 or not all(artifacts):
            raise ValueError("runtime artifact hashes differ")
        if len(stage_architectures) != 1 or not all(stage_architectures):
            raise ValueError('runtime architectures differ')
        stage_artifacts.append(next(iter(artifacts)))
        architectures.append(next(iter(stage_architectures)))
    if contract_hashes != {expected_contract_hash}:
        raise ValueError("runtime contract hashes differ")
    if len(sources) != 1 or not all(sources):
        raise ValueError('source artifact hashes differ')
    if architectures[0] == architectures[1] and stage_artifacts[0] != stage_artifacts[1]:
        raise ValueError("runtime artifact hashes differ")


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: verify_host_runtime.py local-receipts.json cloud-receipts.json", file=sys.stderr)
        return 2
    root = Path(__file__).resolve().parents[1]
    try:
        contract_bytes = (root / "configs/runtime/host-runtime-v1.json").read_bytes()
        contract = json.loads(contract_bytes)
        verify(*(json.loads(Path(path).read_text()) for path in sys.argv[1:]), contract,
               hashlib.sha256(contract_bytes).hexdigest())
    except (OSError, ValueError, KeyError):
        print("Host runtime alignment rejected", file=sys.stderr)
        return 1
    print("Host runtime sources match local acceptance; installed artifacts agree within each stage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
