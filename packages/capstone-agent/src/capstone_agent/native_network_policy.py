"""Kernel-enforced egress for unprivileged native tasks, not Provider traffic.

The service owns this table in its private Linux network namespace. Task UIDs
start at 10000 and must have no network administration capability. Internal
endpoints are deployment configuration, never model-supplied addresses.
"""
from dataclasses import dataclass
import ipaddress
import subprocess
import threading
from collections.abc import Callable


def execution_policy(policy: dict, *, external_access: bool) -> dict:
    """Upgrade checked legacy context using the executor's enforced state."""
    legacy = ('External lookup is disabled. '
              'Do not use shell commands or MCP tools to bypass that application restriction. ')
    instruction = ('External Internet access is enabled by the user. Retrieve real sources when needed. '
                   if external_access else
                   'External Internet access is blocked by the host. Approved internal tools remain available. ')
    instruction += ('Respect any narrower user source restrictions. Never change or bypass network controls. '
                    'If connectivity changes during execution, report the actual failure; do not invent retrieved facts.')
    return {**policy, 'external_lookup_enabled': external_access,
            'system_policy': policy.get('system_policy', '').replace(legacy, '') + '\n' + instruction}


@dataclass(frozen=True)
class InternalEndpoint:
    address: str
    port: int
    protocol: str = 'tcp'

    def __post_init__(self):
        address = ipaddress.ip_address(self.address)
        if '%' in self.address or type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError('invalid internal endpoint')
        if self.protocol not in {'tcp', 'udp'}:
            raise ValueError('invalid internal endpoint protocol')
        object.__setattr__(self, 'address', str(address))

    def rule(self):
        family = 'ip' if ipaddress.ip_address(self.address).version == 4 else 'ip6'
        return f'{family} daddr {self.address} {self.protocol} dport {self.port} accept'


def _apply(script: str):
    subprocess.run(['nft', '-f', '-'], input=script, text=True, check=True,
                   capture_output=True, timeout=10)


class NativeNetworkPolicy:
    def __init__(self, *, internal_endpoints: tuple[InternalEndpoint, ...] = (),
                 relay_port: int = 8790, apply_rules: Callable[[str], None] = _apply):
        self._relay = InternalEndpoint('127.0.0.1', relay_port)
        self._internal = tuple(internal_endpoints)
        self._apply = apply_rules
        self._lock = threading.RLock()
        self._enforced = False
        self._external = False

    def state(self) -> dict:
        with self._lock:
            return {'external_access': self._external, 'enforced': self._enforced}

    def start(self):
        with self._lock:
            self._apply(self._script(False))
            self._enforced = True
            self._external = False

    def set_external_access(self, enabled: bool):
        if type(enabled) is not bool:
            raise ValueError('external_access must be a boolean')
        with self._lock:
            if not self._enforced:
                raise RuntimeError('network enforcement is not ready')
            if enabled != self._external:
                self._apply(self._script(enabled))
                self._external = enabled
            return self.state()

    def _script(self, enabled: bool) -> str:
        # add is idempotent; flush and rebuild share one transaction. A service
        # restart must not append rules behind an earlier terminal reject.
        lines = ['add table inet capstone_tasks', 'flush table inet capstone_tasks']
        lines += ['table inet capstone_tasks {', 'chain output {',
                  'type filter hook output priority -150; policy accept;',
                  # Preserve the service/task distinction when TCP emits ACKs
                  # or retransmissions without a socket UID. Only trusted
                  # service sockets can assign this connection mark.
                  'ct mark 0x43505354 return',
                  # Kernel-generated TCP packets need not retain a socket UID.
                  # Permit established control-service replies, not outbound
                  # task connections (which must still obey the current switch).
                  f'tcp sport {self._relay.port} ct direction reply ct state established accept',
                  'meta skuid < 10000 ct direction original ct mark set 0x43505354 return',
                  'meta skuid < 10000 return', self._relay.rule()]
        lines.extend(endpoint.rule() for endpoint in self._internal)
        if enabled:
            # Docker's resolver is reachable only while Internet is enabled.
            # Internal DNS, if needed, must be an explicit deployment endpoint
            # whose server does not forward queries to the public Internet.
            lines += ['ip daddr 127.0.0.11 udp dport 53 accept',
                      'ip daddr 127.0.0.11 tcp dport 53 accept',
                      'ip daddr { 0.0.0.0/8, 10.0.0.0/8, 100.64.0.0/10, '
                      '127.0.0.0/8, 169.254.0.0/16, 172.16.0.0/12, 192.0.0.0/24, '
                      '192.0.2.0/24, 192.168.0.0/16, 198.18.0.0/15, 198.51.100.0/24, '
                      '203.0.113.0/24, 224.0.0.0/4, 240.0.0.0/4 } reject',
                      'meta nfproto ipv4 accept',
                      # Only global unicast IPv6. Reject translation/tunnel and
                      # documentation ranges before allowing it.
                      'ip6 daddr { 2001::/32, 2001:db8::/32, 2002::/16 } reject',
                      'ip6 daddr 2000::/3 accept']
        lines += ['reject', '}', '}']
        return '\n'.join(lines) + '\n'
