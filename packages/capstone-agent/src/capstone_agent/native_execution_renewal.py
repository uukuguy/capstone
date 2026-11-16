"""Renew remote execution independently from output and product delivery."""
from hashlib import sha256
import secrets
from threading import Event, Thread

from . import native_execution_authority as policy


class ExecutionRenewal:
    def __init__(self, client, request, control):
        self.grant = {'schema': policy.SCHEMA,
            'generation': sha256((request.parent_attempt_id + '\0' + request.task_id).encode()).hexdigest(),
            'capability': secrets.token_hex(32)}
        self._client, self._task_id, self._control = client, request.task_id, control
        self._stop, self._failed = Event(), Event()
        self._thread = Thread(target=self._renew, daemon=True, name='capstone-native-authority')

    def start(self):
        self._thread.start()

    def check(self):
        if self._failed.is_set():
            raise RuntimeError('native execution authority unavailable')

    def _renew(self):
        from .pi_delegation import PiTransportTimeout, PiTransportUnavailable, PiHTTPFailure
        sequence = 1
        while not self._stop.wait(policy.RENEW_SECONDS):
            try:
                self._control.checkpoint()
                receipt = self._client._call('POST', '/tasks/' + self._task_id + '/authority',
                    document={**self.grant, 'sequence': sequence},
                    timeout=policy.EXCHANGE_SECONDS, total_timeout=policy.EXCHANGE_SECONDS,
                    checkpoint=self._control.checkpoint)
                if receipt != {'renewed': True}:
                    raise ValueError('invalid execution renewal receipt')
                sequence += 1
            except (PiTransportTimeout, PiTransportUnavailable):
                # Retry this exact sequence. A lost acknowledgement must not
                # grant additional time; executor expiry remains authoritative.
                continue
            except PiHTTPFailure as error:
                if error.diagnostic['http_status'] == 409:
                    # Terminal completion can race its final status read. Stop
                    # renewing and let the main channel read the actual result.
                    return
                self._failed.set()
                return
            except Exception:
                self._failed.set()
                return

    def close(self):
        self._stop.set()
        if self._thread.ident is not None:
            self._thread.join(timeout=policy.EXCHANGE_SECONDS + .2)
