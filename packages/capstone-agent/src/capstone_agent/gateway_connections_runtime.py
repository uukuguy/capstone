"""Load operator-owned gateway seeds; additions live in protected host storage."""
import json
from pathlib import Path
import stat

from .data_gateway_mcp import GatewayError
from .gateway_connections import GatewayConnectionRegistry


def load_gateway_connections(connection_file, policy_path, registry_root, *,
                             private_root=Path('/run/capstone-private'), owner_uid=0,
                             transport_host=None):
    registry = None
    try:
        seeds, selected = [], None
        if connection_file:
            private = Path(private_root)
            parent = private.lstat()
            path = Path(connection_file)
            if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != owner_uid
                    or stat.S_IMODE(parent.st_mode) != 0o700
                    or path != private / 'data-gateway/connection.json'):
                raise ValueError()

            def read(source):
                if source.is_symlink() or source.stat().st_mode & 0o077 or source.stat().st_size > 1024 * 1024:
                    raise ValueError()
                return json.loads(source.read_text())

            connection = read(path)
            seed_file = path.with_name('instances.json')
            if seed_file.exists():
                document = read(seed_file)
                if (not isinstance(document, dict) or document.get('schema') != 'capstone-gateway-seeds/1'
                        or set(document) - {'schema', 'entries', 'selected_id'}
                        or not isinstance(document.get('entries'), list)):
                    raise ValueError()
                seeds = document['entries']
                selected = document.get('selected_id')
            else:
                seeds = [{'id': 'configured', 'label': connection.get('name') or '已配置网关', 'connection': connection}]
                selected = 'configured'
            if selected is not None and selected not in {entry.get('id') for entry in seeds}:
                raise ValueError()
        registry = GatewayConnectionRegistry(Path(registry_root), json.loads(Path(policy_path).read_text()),
            seeds=seeds, transport_host=transport_host)
        failure = 'not_configured'
        try:
            if registry.snapshot().get('selected_id') is not None:
                registry.prepare_selected()
            elif selected is not None:
                registry.select(selected)
        except GatewayError as error:
            failure = str(error)
        registry.start()
        access = registry.current_access
        publication = access.publication() if access is not None else {'available': False, 'reason': failure}
        return registry, access, publication
    except (OSError, ValueError, TypeError, KeyError):
        if registry is not None:
            registry.close()
        return None, None, {'available': False, 'reason': 'gateway_registry_unavailable'}
