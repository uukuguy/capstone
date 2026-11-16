"""Bounded replay of durable intents through an idempotent public Agent port."""
import logging
from typing import Protocol


class AgentPort(Protocol):
    def delegate(self, workspace: str, delegation: dict) -> dict: ...
    def observe(self, workspace: str, delegation: dict) -> dict: ...
    def control(self, workspace: str, delegation: dict, kind: str, operation_id: str) -> dict: ...


def reconcile(service, agent: AgentPort, *, workspace=None, limit=32):
    result = {'processed': 0, 'errors': 0}
    for item in service.pending(workspace, limit):
        owner, goal_id = item['workspace'], item['goal_id']
        delegation_id = item['task']['delegation']['delegation_id']
        try:
            delegation = service.delegation_request(owner, goal_id, delegation_id)
            if delegation['binding'] is None and delegation['requested_control'] is None:
                binding = agent.delegate(owner, delegation)
                service.bind(owner, goal_id, delegation_id, binding)
                delegation = service.delegation_request(owner, goal_id, delegation_id)
            if delegation['requested_control'] is not None:
                kind = delegation['requested_control']
                observation = agent.control(owner, delegation, kind,
                    delegation_id + '_' + kind + '_' + str(delegation.get('control_revision', 0)))
            else:
                observation = agent.observe(owner, delegation)
            service.observe(owner, goal_id, delegation_id, observation)
            result['processed'] += 1
        except Exception:
            # Retain the intent. No new identity or retry generation is created.
            # Do not log exception text that can contain transport credentials.
            result['errors'] += 1
            logging.getLogger(__name__).warning('Control delegation reconciliation failed; intent retained')
    return result
