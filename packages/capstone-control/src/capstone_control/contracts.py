"""Strict public contracts for durable Control requests."""
from copy import deepcopy
from datetime import datetime, timedelta
import re


class ContractError(ValueError):
    """A request does not meet its versioned contract."""


def object_fields(value, required):
    if not isinstance(value, dict) or set(value) != set(required):
        raise ContractError('object fields do not match contract')


def text(value, *, limit=16384):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ContractError('nonempty bounded text required')
    return value


def identity(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', value):
        raise ContractError('invalid identity')
    return value


def authority_source(value):
    """Identify one authoritative terminal receipt without granting access."""
    object_fields(value, {'thread_id', 'work_id', 'attempt_id', 'answer_ref'})
    for item in value.values():
        identity(item)
    return value


def validate_delivery(value, binding):
    fields = {'answer_ref', 'products', 'status'}
    source_fields = {'authority_source', 'gateway_source'}
    if isinstance(value, dict):
        fields.update(source_fields.intersection(value))
    object_fields(value, fields)
    identity(value['answer_ref'])
    if value['status'] != 'completed' or not isinstance(value['products'], list):
        raise ContractError('completed persisted delivery required')
    for field in source_fields.intersection(value):
        source = authority_source(value[field])
        if (binding is None or any(source[key] != binding[key] for key in ('thread_id', 'work_id'))
                or source['answer_ref'] != value['answer_ref']):
            raise ContractError('authority source does not match the delivery binding')


def positive_integer(value):
    if type(value) is not int or value < 1:
        raise ContractError('positive integer required')
    return value


def utc_deadline(value):
    text(value, limit=64)
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ContractError('invalid deadline') from None
    if parsed.utcoffset() != timedelta(0):
        raise ContractError('explicit UTC deadline required')
    return parsed


def text_list(value):
    if not isinstance(value, list) or not value or len(value) > 64:
        raise ContractError('nonempty bounded list required')
    for item in value:
        text(item)


def validate_goal_request(value):
    object_fields(value, {'schema', 'operation_id', 'objective', 'acceptance_criteria',
                          'max_delegations', 'deadline_at', 'tasks'})
    if value['schema'] != 'capstone-control-goal-create/1':
        raise ContractError('unsupported Goal creation schema')
    identity(value['operation_id'])
    text(value['objective'])
    text_list(value['acceptance_criteria'])
    positive_integer(value['max_delegations'])
    utc_deadline(value['deadline_at'])
    tasks = value['tasks']
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 64:
        raise ContractError('one to64 ordered Tasks required')
    admitted = set()
    for task in tasks:
        fields = {'task_id', 'objective', 'delivery_requirements',
                  'depends_on', 'agent_id', 'mode', 'max_attempts'}
        if not isinstance(task, dict) or not fields <= task.keys() or set(task) - fields - {'required_products'}:
            raise ContractError('Task fields do not match contract')
        task_id = identity(task['task_id'])
        if task_id in admitted:
            raise ContractError('duplicate Task identity')
        dependencies = task['depends_on']
        if (not isinstance(dependencies, list) or
                any(not isinstance(item, str) for item in dependencies) or
                len(dependencies) != len(set(dependencies)) or
                not set(dependencies) <= admitted):
            raise ContractError('dependencies must name distinct preceding Tasks')
        text(task['objective'])
        text_list(task['delivery_requirements'])
        products = task.get('required_products', [])
        if (not isinstance(products, list) or len(products) > 64 or
                any(not isinstance(name, str) or not name or len(name.encode()) > 255
                    or name in {'.', '..'} or '/' in name or '\\' in name
                    or any(ord(c) < 32 or ord(c) == 127 for c in name) for name in products)
                or len(set(products)) != len(products)):
            raise ContractError('required products must name distinct plain file names')
        identity(task['agent_id'])
        positive_integer(task['max_attempts'])
        if not isinstance(task['mode'], str) or task['mode'] not in {'single', 'goal'}:
            raise ContractError('unsupported execution mode')
        if task['mode'] == 'single' and task['max_attempts'] != 1:
            raise ContractError('single execution requires one Attempt')
        admitted.add(task_id)
    return deepcopy(value)
