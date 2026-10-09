"""Discover only the explicitly configured private general executor host."""
from collections.abc import Mapping
from typing import cast
import re

from .harness import HarnessRuntimeConfigurationError
from .pi_delegation import GeneralPiExecutor, HttpGeneralPiExecutor


def _resource_profiles(profiles):
    """Check the closed public projection; private snapshots stay on the host."""
    if not isinstance(profiles, dict) or (profiles and set(profiles) != {'direct_pi', 'delegated_pi'}):
        raise ValueError('general executor resource roles are invalid')
    def digest(value):
        return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None
    for role, profile in profiles.items():
        if (set(profile) != {'schema', 'profile_id', 'revision', 'role', 'resources', 'load_receipt'}
                or profile['schema'] != 'capstone-resource-profile/1' or profile['role'] != role
                or profile['profile_id'] != role or not digest(profile['revision'])):
            raise ValueError('general executor resource profile is invalid')
        receipt = profile['load_receipt']
        if (set(receipt) != {'schema', 'status', 'role', 'adapter_id', 'source_sha256', 'published_tool_ids',
                             'skills', 'tool_schema_hashes', 'descriptor_sha256'}
                or receipt['schema'] != 'capstone-resource-adapter-check/1' or receipt['status'] != 'passed'
                or receipt['role'] != role or receipt['adapter_id'] != 'native-pi-resources/1'
                or not digest(receipt['source_sha256'])
                or receipt['descriptor_sha256'] is not None and not digest(receipt['descriptor_sha256'])):
            raise ValueError('general executor load receipt is invalid')
        tools = receipt['published_tool_ids']
        if not isinstance(tools, list) or len(tools) > 128 or len(set(tools)) != len(tools):
            raise ValueError('general executor published tools are invalid')
        for values in (receipt['skills'], receipt['tool_schema_hashes']):
            if not isinstance(values, dict) or any(not re.fullmatch('[A-Za-z0-9_.:-]{1,128}', key)
                                                  or not digest(value) for key, value in values.items()):
                raise ValueError('general executor resource hashes are invalid')
        resources = profile['resources']
        if not isinstance(resources, list) or len(resources) > 128:
            raise ValueError('general executor resource catalog is invalid')
        for resource in resources:
            required = {'id', 'kind', 'version', 'source', 'roles', 'enabled', 'installed', 'ready',
                        'reason', 'required_tools', 'loaded_identity'}
            name, description = resource.get('native_name'), resource.get('description')
            if (not required <= resource.keys() or resource.keys() - required - {'native_name', 'description'}
                    or name is not None and (not isinstance(name, str) or not re.fullmatch('[A-Za-z0-9_-]{1,128}', name))
                    or description is not None and (not isinstance(description, str) or len(description) > 512)
                    or resource['kind'] not in {'skill', 'mcp', 'plugin'} or role not in resource['roles']
                    or any(type(resource[key]) is not bool for key in ('enabled', 'installed', 'ready'))
                    or not isinstance(resource['source'], str) or resource['source'].startswith(('/', 'file:'))
                    or resource['ready'] and (not resource['enabled'] or not resource['installed']
                        or not digest(resource['loaded_identity']) or resource['reason'] is not None
                        or not set(resource['required_tools']) <= set(tools))):
                raise ValueError('general executor resource descriptor is invalid')


def configured_general_executor(environment: Mapping[str, str]) -> GeneralPiExecutor | None:
    origin = environment.get('CAPSTONE_GENERAL_EXECUTOR_ORIGIN')
    if not origin:
        return None
    try:
        probe = HttpGeneralPiExecutor(origin, identity={'state': 'discovery'}, capability={},
            control_token=environment.get('CAPSTONE_GENERAL_CONTROL_TOKEN'))
        document = probe._call('GET', '/health/ready', timeout=0.5, total_timeout=2)
        if set(document) != {'identity', 'capability'}:
            raise ValueError('general executor health fields are invalid')
        capability = document['capability']
        if (not isinstance(capability, dict) or capability.get('capability_id') != 'general-pi'
            or type(capability.get('enabled')) is not bool or type(capability.get('available')) is not bool
            or not isinstance(capability.get('operations'), list)
            or not set(capability['operations']) <= {'answer', 'rewrite', 'external_lookup'}):
            raise ValueError('general executor capability is invalid')
        schemas = capability.get('task_schemas', ['capstone-pi-task/1'])
        if (not isinstance(schemas, list) or not schemas or any(not isinstance(schema, str) for schema in schemas)
            or len(set(schemas)) != len(schemas)
            or not set(schemas) <= {'capstone-pi-task/1', 'capstone-pi-task/2'}):
            raise ValueError('general executor task schemas are invalid')
        if 'executor_identity' in capability and capability['executor_identity'] != document['identity']:
            raise ValueError('general executor capability identity is invalid')
        if 'resource_profiles' in capability:
            _resource_profiles(capability['resource_profiles'])
        return cast(GeneralPiExecutor, HttpGeneralPiExecutor(origin,
            identity=document['identity'], capability=capability,
            control_token=environment.get('CAPSTONE_GENERAL_CONTROL_TOKEN')))
    except Exception:
        # Do not print a URL, header, secret, or remote error body.
        raise HarnessRuntimeConfigurationError('configured general Pi executor is unavailable') from None
