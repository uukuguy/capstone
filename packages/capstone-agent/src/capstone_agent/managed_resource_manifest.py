"""Strict, secret-free resource identities shared by installer and manifests."""

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import PurePosixPath
import re
from urllib.parse import unquote, urlsplit


def identifier(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', value) or value in {'.', '..'}:
        raise ValueError('invalid_resource_identifier')
    return value


def relative_path(value: str, *, empty: bool = False) -> str:
    if empty and value == '':
        return value
    if (not isinstance(value, str) or not value or '\\' in value
            or any(ord(c) < 32 for c in value) or PurePosixPath(value).is_absolute()
            or any(p in {'', '.', '..'} for p in value.split('/'))):
        raise ValueError('invalid_resource_path')
    return value


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def content_digest(value: object) -> str:
    return 'sha256:' + hashlib.sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class SourceIdentity:
    locator: str
    revision: str

    def __post_init__(self):
        if not isinstance(self.locator, str) or not self.locator:
            raise ValueError('invalid_resource_source')
        parsed = urlsplit(self.locator)
        decoded_path = unquote(parsed.path)
        if parsed.scheme:
            if (parsed.scheme not in {'https', 'http'} or not parsed.hostname or parsed.username
                    or parsed.password or parsed.query or parsed.fragment
                    or any(ord(c) < 33 for c in self.locator + decoded_path)
                    or '\\' in decoded_path or '..' in decoded_path.split('/')):
                raise ValueError('invalid_resource_source')
        else:
            relative_path(self.locator)
        # A revision is a pin, not a shell fragment, URL, or credential container.
        if not isinstance(self.revision, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:+-]{0,255}', self.revision):
            raise ValueError('invalid_resource_revision')


@dataclass(frozen=True)
class RuntimeSpec:
    entrypoint: str = ''
    arguments: tuple[str, ...] = ()
    secret_refs: tuple[str, ...] = ()
    compatibility: str = ''

    def __post_init__(self):
        relative_path(self.entrypoint, empty=True)
        # Arguments are deliberately bounded identifiers or relative paths. Values
        # and environment mappings must be bound by the protected runtime adapter.
        if not isinstance(self.arguments, tuple) or len(self.arguments) > 32:
            raise ValueError('invalid_runtime_arguments')
        for argument in self.arguments:
            if not isinstance(argument, str) or not re.fullmatch(r'[-A-Za-z0-9_./]{1,256}', argument):
                raise ValueError('invalid_runtime_arguments')
            if re.search(r'(token|password|secret|credential|api[-_]?key|authorization)', argument, re.IGNORECASE):
                raise ValueError('secret_runtime_argument_requires_reference')
            relative_path(argument)
        if not isinstance(self.secret_refs, tuple) or len(self.secret_refs) > 32:
            raise ValueError('invalid_secret_references')
        for reference in self.secret_refs:
            if not isinstance(reference, str) or not re.fullmatch(r'secret:[A-Za-z0-9_.-]{1,128}', reference):
                raise ValueError('invalid_secret_reference')
        if not isinstance(self.compatibility, str) or not re.fullmatch(r'[A-Za-z0-9_.:+-]{0,128}', self.compatibility):
            raise ValueError('invalid_runtime_compatibility')


@dataclass(frozen=True)
class VerifiedResource:
    """Internal installer receipt after actual load/connection verification.

    This type is not an HTTP input contract. Public requests cannot supply it.
    Diagnostics are codes, never captured process output.
    """

    kind: str
    source: SourceIdentity
    digest: str
    package_ref: str
    runtime: RuntimeSpec
    available: bool = True
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self):
        if not isinstance(self.kind, str) or self.kind not in {'skill', 'mcp_local', 'mcp_remote'}:
            raise ValueError('invalid_resource_kind')
        if not isinstance(self.source, SourceIdentity) or not isinstance(self.runtime, RuntimeSpec):
            raise ValueError('invalid_resource_metadata')
        if not isinstance(self.digest, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', self.digest):
            raise ValueError('invalid_resource_digest')
        relative_path(self.package_ref, empty=self.kind == 'mcp_remote')
        if type(self.available) is not bool or not isinstance(self.diagnostics, tuple):
            raise ValueError('invalid_resource_availability')
        for code in self.diagnostics:
            identifier(code)

    def to_dict(self) -> dict:
        return json.loads(canonical(asdict(self)))


def parse_verified(value: dict) -> VerifiedResource:
    """Validate stored/exported metadata; does not establish verification."""
    if not isinstance(value, dict) or set(value) != {'kind', 'source', 'digest', 'package_ref', 'runtime', 'available', 'diagnostics'}:
        raise ValueError('invalid_resource_metadata')
    if not isinstance(value['source'], dict) or set(value['source']) != {'locator', 'revision'}:
        raise ValueError('invalid_resource_source')
    runtime = value['runtime']
    if not isinstance(runtime, dict) or set(runtime) != {'entrypoint', 'arguments', 'secret_refs', 'compatibility'}:
        raise ValueError('invalid_resource_runtime')
    if not isinstance(runtime['arguments'], list) or not isinstance(runtime['secret_refs'], list) or not isinstance(value['diagnostics'], list):
        raise ValueError('invalid_resource_metadata')
    return VerifiedResource(value['kind'], SourceIdentity(**value['source']), value['digest'], value['package_ref'], RuntimeSpec(runtime['entrypoint'], tuple(runtime['arguments']), tuple(runtime['secret_refs']), runtime['compatibility']), value['available'], tuple(value['diagnostics']))


def validate_manifest(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) != {'schema', 'profile', 'version', 'entries'} or value['schema'] != 'capstone-preinstall/1':
        raise ValueError('invalid_preinstall_manifest')
    identifier(value['profile'])
    entries = value['entries']
    if not isinstance(entries, list) or len(entries) > 1000:
        raise ValueError('invalid_preinstall_entries')
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'resource_id', 'version', 'enabled', 'resource'}:
            raise ValueError('invalid_preinstall_entry')
        identifier(entry['resource_id'])
        if entry['resource_id'] in seen or type(entry['enabled']) is not bool:
            raise ValueError('invalid_preinstall_entry')
        seen.add(entry['resource_id'])
        resource = parse_verified(entry['resource'])
        if entry['version'] != content_digest(resource.to_dict()):
            raise ValueError('preinstall_version_mismatch')
    body = {key: value[key] for key in ('schema', 'profile', 'entries')}
    if value['version'] != content_digest(body):
        raise ValueError('preinstall_manifest_digest_mismatch')
    return json.loads(canonical(value))
