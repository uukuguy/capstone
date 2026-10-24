"""Public, bounded native context; no credentials, paths, or query endpoints."""
import json
import base64
from hashlib import sha256
import re
from pathlib import PurePosixPath
from collections.abc import Mapping
from typing import cast
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from .native_document_types import TEXT_DOCUMENT_TYPES

POLICY_TEXT = ('Answer the current user message using its conversation context. '
    'General knowledge is not an Authority result. Do not claim model calculations '
    'or external retrieval without an admitted source. External lookup is disabled. '
    'Do not use shell commands or MCP tools to bypass that application restriction. '
    'When a staged material identifies a prior process artifact, its read-only input file '
    'contains the verified original saved bytes, not text reconstructed from conversation history. '
    'Read that supplied source path when revising the artifact; create a writable output copy '
    'and preserve the requested original content. Absence from the current writable working '
    'directory does not mean the original file is unavailable. If a material notice says '
    'the original could not be staged, state that limit and do not claim a byte-preserving edit. '
    'In reader-facing answers refer to public artifact file names and available download links; '
    'do not expose private host or task workspace paths.')
GENERAL_CHAT_POLICY_TEXT = ('Provide a direct conversational answer to the current user message. '
    + POLICY_TEXT)
MATERIAL_POLICY_TEXT, MATERIAL_GENERAL_CHAT_POLICY_TEXT = POLICY_TEXT, GENERAL_CHAT_POLICY_TEXT
POLICY_TEXT += (' A selected product with excerpt.truncated=true contains only the declared leading excerpt, '
    'not the complete original file. Do not claim full-file review or a byte-preserving full-file edit from that excerpt.')
GENERAL_CHAT_POLICY_TEXT = 'Provide a direct conversational answer to the current user message. ' + POLICY_TEXT
# Exact accepted text remains readable after the source-file clarification.
LEGACY_POLICY_TEXT = POLICY_TEXT.split('When a staged material identifies')[0].rstrip()
LEGACY_GENERAL_CHAT_POLICY_TEXT = ('Provide a direct conversational answer to the current user message. '
    + LEGACY_POLICY_TEXT)

@dataclass(frozen=True)
class ResearchPolicyRegistration:
    application_version: str
    pack_version: str
    variant: str
    system_policy: str
    policy_sha256: str
    guides_sha256: str

    @property
    def delivery_review(self) -> bool:
        return self.application_version in {'1.3.0', '1.4.0', '1.5.0', '1.6.0', '1.7.0', '1.8.0', '1.9.0'}

    @property
    def graceful_execution_closure(self) -> bool:
        return self.application_version in {'1.5.0', '1.6.0', '1.7.0', '1.8.0', '1.9.0'}

    @property
    def explicit_subtask_planning(self) -> bool:
        return self.application_version in {'1.8.0', '1.9.0'}

    @property
    def batch_ready_investigations(self) -> bool:
        return self.application_version == '1.9.0'

    @property
    def graph_schema(self) -> str | None:
        return 'capstone-enterprise-graph/2' if self.application_version in {'1.10.0', '1.11.0', '1.12.0', '1.13.0', '1.14.0', '1.15.0', '1.16.0', '1.17.0', '1.18.0'} else None

    @property
    def isolated_task_execution(self) -> bool:
        return self.application_version in {'1.14.0', '1.15.0', '1.16.0', '1.17.0', '1.18.0'}

    @property
    def goal_driven_execution(self) -> bool:
        return self.application_version in {'1.16.0', '1.17.0', '1.18.0'}

    @property
    def lightweight_task_nodes(self) -> bool:
        return self.application_version in {'1.17.0', '1.18.0'}

    @property
    def work_edition(self) -> str | None:
        return 'capstone-graph-work/1' if self.application_version in {'1.12.0', '1.13.0', '1.14.0', '1.15.0', '1.16.0', '1.17.0', '1.18.0'} else None

    def work_policy(self) -> dict:
        if not self.work_edition:
            raise ValueError('research work policy is not selected')
        resource = '1.16' if self.goal_driven_execution else '1.12'
        return json.loads(files(__package__).joinpath(f'resources/graph-work-policy-{resource}.json').read_text())

    def capability(self) -> dict:
        return {'profile_id': 'enterprise-research', 'profile_version': self.application_version,
            'pack_id': 'enterprise-research-methods', 'pack_version': self.pack_version,
            'system_policy_sha256': sha256(self.system_policy.encode()).hexdigest(),
            'policy_sha256': self.policy_sha256, 'guides_sha256': self.guides_sha256,
            **({'graph_work_edition': self.work_edition, 'graph_work_policy_sha256': sha256(json.dumps(self.work_policy(), sort_keys=True, separators=(',', ':')).encode()).hexdigest()} if self.work_edition else {})}


@lru_cache(maxsize=1)
def registered_research_policies() -> tuple[ResearchPolicyRegistration, ...]:
    """Host-owned exact publications, checked against their immutable Pack assets."""
    from enterprise_research import ResearchPolicy, ResearchGuides
    catalog = json.loads(files(__package__).joinpath('resources/research-policy-catalog.json').read_text())
    if catalog.get('schema') != 'capstone-research-policy-catalog/1':
        raise ValueError('research policy catalog is invalid')
    versions = {'1.1.0': '1.0.0', '1.2.0': '1.1.0', '1.3.0': '1.2.0', '1.4.0': '1.3.0', '1.5.0': '1.4.0', '1.6.0': '1.5.0', '1.7.0': '1.6.0', '1.8.0': '1.7.0', '1.9.0': '1.7.0', '1.10.0': '1.8.0', '1.11.0': '1.9.0', '1.12.0': '1.10.0', '1.13.0': '1.11.0', '1.14.0': '1.12.0', '1.15.0': '1.12.0', '1.16.0': '1.13.0', '1.17.0': '1.14.0', '1.18.0': '1.15.0'}
    entries = []
    for item in catalog['policies']:
        entry = ResearchPolicyRegistration(**{key: item[key] for key in ResearchPolicyRegistration.__dataclass_fields__})
        policy = ResearchPolicy(entry.pack_version, variant=entry.variant).load()
        provider = ResearchGuides(entry.pack_version, variant=entry.variant)
        guides = [dict(provider.open(guide['resource_id'])) for guide in provider.load()]
        if entry.application_version in {'1.13.0', '1.14.0', '1.15.0', '1.16.0', '1.17.0', '1.18.0'}:
            from .task_planning_policy import task_planning_policy
            shared = task_planning_policy({'1.13.0': '1.0.0', '1.14.0': '1.1.0', '1.15.0': '1.2.0', '1.16.0': '1.3.0', '1.17.0': '1.4.0', '1.18.0': '1.5.0'}[entry.application_version])
            if entry.system_policy != POLICY_TEXT + '\n\n' + shared.text + '\n\n' + policy:
                raise ValueError('research adapter does not select the exact shared planning policy')
        if (versions.get(entry.application_version) != entry.pack_version
                or sha256(policy.encode()).hexdigest() != entry.policy_sha256
                or sha256(json.dumps(guides, ensure_ascii=False, sort_keys=True).encode()).hexdigest() != entry.guides_sha256
                or not entry.system_policy or any(previous.system_policy == entry.system_policy for previous in entries)):
            raise ValueError('research policy publication does not match registered Pack resources')
        entries.append(entry)
    return tuple(entries)


def registered_research_policy(version: str, variant: str = 'default') -> ResearchPolicyRegistration:
    return next((entry for entry in registered_research_policies()
                 if entry.application_version == version and entry.variant == variant), None) or _unknown_research_policy()


def _unknown_research_policy():
    raise ValueError('research policy publication is not registered')


def resolve_research_policy(text: object) -> ResearchPolicyRegistration | None:
    return next((entry for entry in registered_research_policies() if entry.system_policy == text), None)


def research_policy_capabilities() -> list[dict]:
    return [entry.capability() for entry in registered_research_policies() if entry.variant == 'default']


def research_policy_for_binding(binding: Mapping) -> ResearchPolicyRegistration:
    profile = binding.get('application_profile', {})
    packs = binding.get('pack_bindings')
    if not isinstance(packs, (tuple, list)) or len(packs) != 1 or not isinstance(packs[0], Mapping):
        raise ValueError('research binding has no registered Pack publication')
    pack = packs[0]
    for entry in registered_research_policies():
        if (profile == {'profile_id': 'enterprise-research', 'profile_version': entry.application_version}
                and pack.get('pack_id') == 'enterprise-research-methods'
                and pack.get('pack_version') == entry.pack_version
                and pack.get('policy_sha256') == entry.policy_sha256
                and pack.get('guides_sha256') == entry.guides_sha256):
            return entry
    raise ValueError('research binding Pack hashes are not a registered publication')


RESEARCH_POLICY_TEXT = registered_research_policy('1.1.0').system_policy
SPLIT_RESEARCH_POLICY_TEXT = registered_research_policy('1.2.0').system_policy
REVIEWED_RESEARCH_POLICY_TEXT = registered_research_policy('1.3.0').system_policy
CURRENT_RESEARCH_POLICY_TEXT = registered_research_policy('1.9.0').system_policy

from .application_capacity import limits


def public_document(value):
    if isinstance(value, Mapping):
        return {key: public_document(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [public_document(item) for item in value]
    return value


def checked_native_context(value):
    value = public_document(value)
    fields = {'policy', 'selected_task_records', 'selected_task_source', 'records_truncated'}
    if (not isinstance(value, dict) or not fields <= set(value) or set(value) - fields - {'materials', 'material_notices', 'resource_manifests', 'resource_origins', 'graph_work'}
            or type(value['records_truncated']) is not bool
            or not isinstance(value['selected_task_records'], list) or len(value['selected_task_records']) > 64):
        raise ValueError('native task context is invalid')
    materials = value.get('materials', [])
    from .resource_manifest import checked_resource
    resources = value.get('resource_manifests', [])
    if not isinstance(resources, list):
        raise ValueError('resource manifest exceeds context bounds')
    for resource in resources:
        if checked_resource(resource) != resource:
            raise ValueError('resource manifest is not canonical')
    from .continuation_resources import checked_origin
    origins = value.get('resource_origins', [])
    # Each entry has already passed checked_resource and canonical equality.
    by_id = {item['resource_id']: item for item in cast(list[dict], resources)}
    if (not isinstance(origins, list) or len(by_id) != len(resources)
            or len({item['resource_id'] for item in origins
                    if isinstance(item, dict) and isinstance(item.get('resource_id'), str)}) != len(origins)):
        raise ValueError('invalid continuation resource origins')
    for origin in origins:
        resource = by_id.get(origin.get('resource_id')) if isinstance(origin, dict) and isinstance(origin.get('resource_id'), str) else None
        if resource is None or checked_origin(origin, resource['thread_id']) != origin:
            raise ValueError('continuation origin is not resource-bound')
    notices = value.get('material_notices', [])
    if not isinstance(notices, list) or len(notices) > 64 or any(not isinstance(note, str) or len(note) > 400 for note in notices):
        raise ValueError('native material notices are invalid')
    if not isinstance(materials, list) or len(materials) > limits.inline_material_count:
        raise ValueError('native materials exceed count bounds')
    total = 0
    for material in materials:
        if not isinstance(material, dict):
            raise ValueError('native material is invalid')
        try:
            data = base64.b64decode(material['content_base64'], validate=True)
            data.decode('utf-8')
            name = material['file_name']
            if (material['schema'] != 'capstone-thread-material/1'
                    or not re.fullmatch(r'material_[a-f0-9]{32}', material['material_id'])
                    or not isinstance(name, str) or not name or len(name.encode()) > 255
                    or PurePosixPath(name).name != name or '\\' in name or any(ord(c) < 32 or ord(c) == 127 for c in name)
                    or PurePosixPath(name).suffix.lower() not in TEXT_DOCUMENT_TYPES
                    or '\0' in data.decode('utf-8')
                    or len(data) != material['size_bytes'] or sha256(data).hexdigest() != material['sha256']):
                raise ValueError('native material identity changed')
            total += len(data)
        except (KeyError, TypeError, UnicodeDecodeError, ValueError):
            raise ValueError('native material is invalid') from None
    if total > limits.inline_material_bytes:
        raise ValueError('native materials exceed byte bounds')
    declared = value['selected_task_source']
    if declared is not None and (not isinstance(declared, dict) or set(declared) != {'thread_id', 'attempt_id'}
            or any(not isinstance(item, str) or not item for item in declared.values())):
        raise ValueError('native selected task source is invalid')
    policy = value['policy']
    if (not isinstance(policy, dict) or set(policy) != {'schema', 'system_policy', 'allowed_tools', 'external_lookup_enabled'}
            or policy['schema'] != 'capstone-conversation-policy/1'
            or policy['system_policy'] not in (POLICY_TEXT, GENERAL_CHAT_POLICY_TEXT,
                LEGACY_POLICY_TEXT, LEGACY_GENERAL_CHAT_POLICY_TEXT, MATERIAL_POLICY_TEXT,
                MATERIAL_GENERAL_CHAT_POLICY_TEXT)
                and resolve_research_policy(policy['system_policy']) is None
            or policy['external_lookup_enabled'] is not False
            or not isinstance(policy['allowed_tools'], list) or len(policy['allowed_tools']) > 256
            or any(not isinstance(item, str) or not item or len(item) > 256 for item in policy['allowed_tools'])
            or len(set(policy['allowed_tools'])) != len(policy['allowed_tools'])):
        raise ValueError('native application policy is invalid')
    publication = resolve_research_policy(policy['system_policy'])
    work = value.get('graph_work')
    if publication and publication.work_edition:
        if (not isinstance(work, dict) or set(work) != {'edition', 'started_at_ms'}
                or work['edition'] != publication.work_edition or type(work['started_at_ms']) is not int
                or not 0 < work['started_at_ms'] < 2**53):
            raise ValueError('native graph work needs its trusted attempt origin')
    elif work is not None:
        raise ValueError('native graph work edition is not selected')
    source = None
    cursor = 0
    for page in value['selected_task_records']:
        if (not isinstance(page, dict) or page.get('schema') != 'capstone-selected-task-records/1'
                or page.get('historical_only') is not True or type(page.get('has_more')) is not bool
                or not isinstance(page.get('events'), list) or type(page.get('next_after')) is not int
                or page['next_after'] < cursor):
            raise ValueError('native selected task records are invalid')
        identity = (page.get('thread_id'), page.get('attempt_id'))
        if any(not isinstance(item, str) or not item for item in identity) or source is not None and source != identity:
            raise ValueError('native selected task source changed')
        source, cursor = identity, page['next_after']
    if source is not None and declared != {'thread_id': source[0], 'attempt_id': source[1]}:
        raise ValueError('native selected task identity changed')
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    if len(encoded.encode()) > limits.native_context_bytes:
        raise ValueError('native context exceeds bounds')
    return json.loads(encoded)


def native_context_for(claim, binding):
    from datetime import datetime
    from .enterprise_application import resolve_native_profile
    governed = binding['application_profile']['profile_id'] == 'enterprise-research' and binding['application_profile']['profile_version'] != '1.0.0'
    entry = research_policy_for_binding(binding) if governed else None
    profile = resolve_native_profile(binding['application_profile']['profile_id'],
                                     binding['application_profile']['profile_version'],
                                     policy_variant=entry.variant if entry else 'default')
    tools = set(binding['capability'].get('native_builtin_tools', ()))
    from .native_research_bridge import research_tools_for_profile
    tools.update(research_tools_for_profile(binding['application_profile']['profile_id'],
                                           binding['application_profile']['profile_version']))
    submission = claim.submission or {}
    if submission.get('input', {}).get('kind') == 'skill_invocation':
        selected = next((item for item in binding['capability']['resource_profiles']['delegated_pi']['resources']
                         if item['id'] == submission['input']['skill_id'] and item['kind'] == 'skill'), None)
        if selected is None or not selected['ready']:
            raise ValueError('selected native skill is unavailable')
        tools.update(selected['required_tools'])
    pages, cursor, truncated, source = [], 0, False, None
    materials = public_document(submission.get('_materials', []))
    material_bytes = len(json.dumps(materials).encode())
    reader = claim.selected_task_reader
    while reader is not None:
        page = reader.read(after=cursor, limit=4)
        source = {'thread_id': page['thread_id'], 'attempt_id': page['attempt_id']}
        if len(json.dumps([*pages, page], ensure_ascii=False).encode()) > limits.native_context_bytes - 32768 - material_bytes or len(pages) >= 64:
            truncated = True
            break
        pages.append(page)
        if not page['has_more']:
            break
        if page['next_after'] <= cursor:
            raise ValueError('native history cursor did not advance')
        cursor = page['next_after']
    if pages:
        tools.add('agent_task_records_read')
    from .continuation_resources import artifact_origin
    origins = [artifact_origin(public_document(item)) for item in submission.get('_continuation_artifacts', [])]
    work = {}
    if entry and entry.work_edition:
        if not isinstance(getattr(claim, 'started_at', None), str):
            raise ValueError('graph work requires the trusted attempt start')
        started = datetime.fromisoformat(claim.started_at.replace('Z', '+00:00'))
        if started.tzinfo is None:
            raise ValueError('graph work attempt start needs timezone')
        work = {'graph_work': {'edition': entry.work_edition, 'started_at_ms': int(started.timestamp() * 1000)}}
    return checked_native_context({'policy': {'schema': 'capstone-conversation-policy/1',
        'system_policy': profile.application_policy.load(), 'allowed_tools': sorted(tools),
        'external_lookup_enabled': False}, 'selected_task_records': pages,
        'selected_task_source': source, 'records_truncated': truncated, **work,
        **({'materials': materials} if materials else {}),
        **({'resource_manifests': public_document(submission['_resource_manifests'])} if submission.get('_resource_manifests') else {}),
        **({'resource_origins': origins} if origins else {}),
        **({'material_notices': public_document(submission['_material_notices'])} if submission.get('_material_notices') else {})})
