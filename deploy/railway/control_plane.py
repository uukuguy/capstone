"""Use the existing Railway CLI login and retry only known read operations."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from urllib.request import getproxies, proxy_bypass


MESSAGES = {
    'network_unavailable': 'Railway network request failed. Check the configured proxy or network route.',
    'authentication_failed': 'Railway rejected its current login state. Reuse the existing account login.',
    'permission_denied': 'The current Railway account cannot access this operation.',
    'certificate_rejected': 'Railway TLS certificate verification failed. Check the local certificate chain.',
    'write_outcome_unknown': 'Railway write response was lost. Read deployment state before another write.',
    'cli_unavailable': 'The Railway CLI is not available.',
    'operation_failed': 'Railway rejected the operation.',
    'project_mismatch': 'Railway returned a different project. Check the selected project.',
}


class ControlPlaneError(RuntimeError):
    def __init__(self, code: str, attempts: int):
        self.code = code
        self.attempts = attempts
        super().__init__(MESSAGES[code])


def _failure_code(stderr: str) -> str:
    text = stderr.lower()
    if '401' in text:
        return 'authentication_failed'
    if any(value in text for value in ('403', 'forbidden', 'not authorized', 'notauthorized', 'permission denied')):
        return 'permission_denied'
    if any(value in text for value in ('unauthorized', 'invalid token', 'not logged in', 'authentication failed')):
        return 'authentication_failed'
    if any(value in text for value in ('certificate', 'unknown issuer', 'invalid peer')):
        return 'certificate_rejected'
    if any(value in text for value in ('tls handshake', 'ssl_connect', 'ssl_error', 'unexpected eof',
                                      'connection reset', 'connection refused', 'client error (connect)',
                                      'error sending request', 'timed out', 'timeout', 'dns error',
                                      'failed to lookup', 'network is unreachable')):
        return 'network_unavailable'
    return 'operation_failed'


def _known_read(args: list[str]) -> bool:
    if args[:2] in (['deployment', 'list'], ['variable', 'list']):
        return True
    if len(args) >= 2 and args[0] == 'api':
        query = args[1].lstrip()
        return bool(re.match(r'(query\b|\{)', query)) and not re.search(r'\b(mutation|subscription)\b', query)
    return False


def _run(args, *, read_only, runner, sleep, input, timeout):
    for attempt in range(1, (3 if read_only else 1) + 1):
        try:
            result = runner(['railway', *args], capture_output=True, text=True, input=input, timeout=timeout)
            if result.returncode == 0:
                return result.stdout
            code = _failure_code(result.stderr or '')
        except subprocess.TimeoutExpired:
            code = 'network_unavailable'
        except FileNotFoundError:
            code = 'cli_unavailable'
        if code == 'network_unavailable':
            if not read_only:
                raise ControlPlaneError('write_outcome_unknown', attempt)
            if attempt < 3:
                sleep(attempt)
                continue
        raise ControlPlaneError(code, attempt)
    raise AssertionError('unreachable')


def run_read(args: list[str], *, input: str | None = None, timeout: float = 15,
             runner=None, sleep=time.sleep) -> str:
    """Retry a query/list at most three times; let the CLI manage its login."""
    if not _known_read(args):
        raise ValueError('Only explicit Railway queries and lists may use read retries')
    return _run(args, read_only=True, runner=runner or subprocess.run, sleep=sleep, input=input, timeout=timeout)


def run_write(args: list[str], *, input: str | None = None, timeout: float = 180,
              runner=None) -> str:
    """Submit once. A lost response requires state reconciliation, not resubmit."""
    return _run(args, read_only=False, runner=runner or subprocess.run, sleep=None, input=input, timeout=timeout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-id', required=True, help='Existing Railway project ID; this is not a credential')
    parser.add_argument('--expected-project', required=True, help='Expected project name')
    args = parser.parse_args()
    route = 'proxy' if getproxies().get('https') and not proxy_bypass('backboard.railway.com') else 'direct'
    receipt = {'schema': 'capstone-railway-check/1', 'route': route}
    try:
        raw = run_read(['api', 'query($id:String!){project(id:$id){name}}', '--variables', '@-', '--compact'],
                       input=json.dumps({'id': args.project_id}))
        doc = json.loads(raw)
        name = doc.get('data', doc)['project']['name']
        if name != args.expected_project:
            raise ControlPlaneError('project_mismatch', 1)
    except ControlPlaneError as error:
        print(json.dumps({**receipt, 'status': 'failed', 'code': error.code,
                          'attempts': error.attempts, 'message': str(error)}))
        return 1
    except (KeyError, TypeError, ValueError):
        print(json.dumps({**receipt, 'status': 'failed', 'code': 'operation_failed',
                          'message': MESSAGES['operation_failed']}))
        return 1
    print(json.dumps({**receipt, 'status': 'ready', 'project': name}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
