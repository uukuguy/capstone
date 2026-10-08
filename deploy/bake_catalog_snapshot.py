"""Bake bounded Authority metadata for the exact installed runtime artifact."""
from __future__ import annotations

import json
import os
from pathlib import Path

from launch_host_runtime import artifact_identity
from capstone_agent.federated_catalog import build_catalog_from_documents
from capstone_agent.federated_hosted import load_federated_catalog_documents


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    documents = load_federated_catalog_documents(root)
    build_catalog_from_documents(documents, expected_families=('pandapower', 'pypsa'))
    snapshot = {'schema': 'capstone-federated-catalog-snapshot/1', 'documents': documents}
    raw = json.dumps(snapshot, sort_keys=True).encode()
    if len(raw) > 1024 * 1024:
        raise ValueError('installed catalog snapshot is too large')
    directory = root / '.capstone-agent'
    directory.mkdir(exist_ok=True)
    path = directory / 'federated-catalog.json'
    path.write_bytes(raw)
    snapshot['artifact_sha256'] = artifact_identity(root, Path(os.environ['CAPSTONE_PYPSA_MODEL_LIBRARY_DIR']))
    path.write_bytes(json.dumps(snapshot, sort_keys=True).encode())
    path.chmod(0o444)
    print('Installed Authority catalog snapshot verified')


if __name__ == '__main__':
    main()
