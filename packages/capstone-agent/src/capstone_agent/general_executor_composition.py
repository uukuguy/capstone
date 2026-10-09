"""Discover only the explicitly configured private general executor host."""
from collections.abc import Mapping
from typing import cast

from .harness import HarnessRuntimeConfigurationError
from .pi_delegation import GeneralPiExecutor, HttpGeneralPiExecutor


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
        if 'executor_identity' in capability and capability['executor_identity'] != document['identity']:
            raise ValueError('general executor capability identity is invalid')
        return cast(GeneralPiExecutor, HttpGeneralPiExecutor(origin,
            identity=document['identity'], capability=capability,
            control_token=environment.get('CAPSTONE_GENERAL_CONTROL_TOKEN')))
    except Exception:
        # Do not print a URL, header, secret, or remote error body.
        raise HarnessRuntimeConfigurationError('configured general Pi executor is unavailable') from None
