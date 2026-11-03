"""Resolve exact resource-scoped secret references from backend-owned files.

No plaintext values, environment lookups, or model-selected file paths are
accepted. The application supplies the scope from its admitted resource record.
Read on each operation so file rotation and revocation need no image rebuild.
"""
import json
import os
from pathlib import Path
import re
import stat


SCHEMA = 'capstone-managed-resource-bindings/1'
MAX_FILE_BYTES = 65536
_REFERENCE = re.compile(r'secret:[A-Za-z0-9_.-]{1,128}')
_ENVIRONMENT = re.compile(r'[A-Z][A-Z0-9_]{0,127}')
_HEADER = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]{1,128}")
_CONTROL_ENV = {'PATH', 'HOME', 'TMPDIR', 'TMP', 'TEMP', 'NODE_OPTIONS', 'NODE_PATH',
                'BASH_ENV', 'ENV', 'SHELLOPTS', 'BASHOPTS', 'IFS', 'CDPATH',
                'GIT_CONFIG', 'GIT_CONFIG_GLOBAL', 'GIT_CONFIG_SYSTEM', 'GIT_SSH',
                'GIT_SSH_COMMAND', 'PIP_CONFIG_FILE'}
_CONTROL_HEADERS = {'host', 'content-length', 'transfer-encoding', 'connection',
                    'upgrade', 'trailer', 'te', 'proxy-authorization', 'proxy-connection'}


class ResourceBindingError(ValueError):
    """Safe typed diagnostic; contains neither file names nor secret values."""
    def __init__(self, code='resource_secret_binding_unavailable'):
        self.code = code
        super().__init__(code)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate binding field')
        result[key] = value
    return result


def _read_protected(path):
    """Walk without following symlinks, then validate the opened regular file."""
    descriptor = None
    try:
        path = Path(path)
        if not path.is_absolute() or '..' in path.parts:
            raise ValueError()
        descriptor = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
        for component in path.parts[1:-1]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        child = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                        dir_fd=descriptor)
        os.close(descriptor)
        descriptor = child
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_mode & 0o077 or info.st_size > MAX_FILE_BYTES):
            raise ValueError()
        data = bytearray()
        while len(data) <= MAX_FILE_BYTES:
            chunk = os.read(descriptor, MAX_FILE_BYTES + 1 - len(data))
            if not chunk:
                break
            data.extend(chunk)
        if len(data) > MAX_FILE_BYTES:
            raise ValueError()
        return data.decode('utf-8')
    except (OSError, ValueError, TypeError):
        raise ResourceBindingError('resource_secret_file_unavailable') from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


class ProtectedResourceBindings:
    def __init__(self, path=None):
        self.path = path

    def resolve(self, refs, *, workspace, resource_id, source_locator, kind):
        result = {'environment': {}, 'headers': {}}
        if not isinstance(refs, (tuple, list)) or any(not isinstance(ref, str) or not _REFERENCE.fullmatch(ref) for ref in refs):
            raise ResourceBindingError('resource_secret_reference_invalid')
        if not refs:
            return result
        if self.path is None:
            raise ResourceBindingError()
        try:
            document = json.loads(_read_protected(self.path), object_pairs_hook=_unique_object)
        except ResourceBindingError:
            raise
        except (ValueError, TypeError, RecursionError):
            raise ResourceBindingError('resource_secret_config_invalid') from None
        if (not isinstance(document, dict) or set(document) != {'schema', 'bindings'}
                or document['schema'] != SCHEMA or not isinstance(document['bindings'], dict)):
            raise ResourceBindingError('resource_secret_config_invalid')
        expected = dict(workspace=workspace, resource_id=resource_id, source_locator=source_locator, kind=kind)
        if kind not in {'mcp_remote', 'mcp_local', 'skill'} or any(not isinstance(value, str) or not value for value in expected.values()):
            raise ResourceBindingError('resource_secret_scope_denied')
        for ref in dict.fromkeys(refs):
            binding = document['bindings'].get(ref)
            if (not isinstance(binding, dict)
                    or set(binding) != {'workspace', 'resource_id', 'source_locator', 'kind', 'headers', 'environment'}
                    or not isinstance(binding['headers'], dict) or not isinstance(binding['environment'], dict)):
                raise ResourceBindingError()
            if any(binding[field] != value for field, value in expected.items()):
                raise ResourceBindingError('resource_secret_scope_denied')
            forbidden = binding['environment'] if kind == 'mcp_remote' else binding['headers']
            if forbidden:
                raise ResourceBindingError('resource_secret_target_invalid')
            target = 'headers' if kind == 'mcp_remote' else 'environment'
            for name, file in binding[target].items():
                if target == 'headers':
                    valid = bool(_HEADER.fullmatch(name)) and name.lower() not in _CONTROL_HEADERS
                else:
                    valid = (bool(_ENVIRONMENT.fullmatch(name)) and name not in _CONTROL_ENV
                             and not name.startswith(('LD', 'DYLD', 'PYTHON')))
                if not valid or not isinstance(file, str):
                    raise ResourceBindingError('resource_secret_target_invalid')
                value = _read_protected(file)
                if '\0' in value or target == 'headers' and ('\r' in value or '\n' in value):
                    raise ResourceBindingError('resource_secret_value_invalid')
                identity = name.lower() if target == 'headers' else name
                if any((existing.lower() if target == 'headers' else existing) == identity for existing in result[target]):
                    raise ResourceBindingError('resource_secret_target_conflict')
                result[target][name] = value
        return result
