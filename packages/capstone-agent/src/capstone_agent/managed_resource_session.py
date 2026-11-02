"""One isolated MCP connection per accepted task/resource version; no replay."""
import json
import os
import selectors
import subprocess
import threading
import time
import re

from .application_capacity import limits
from .managed_resource_mcp import ManagedMcpError


class ManagedResourceSession:
    def __init__(self, argv, *, cwd, environment, initial, cleanup):
        self.lock=threading.Lock()
        self.sequence=0
        self.cleanup=cleanup
        self.closed=False
        self.process=subprocess.Popen(argv,cwd=cwd,env=environment,stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=True)
        self.pending=bytearray()
        try:
            self._write(initial)
        except BaseException:
            self.close()
            raise

    def _write(self, value, deadline=None):
        encoded=json.dumps(value,ensure_ascii=False).encode()+b'\n'
        if len(encoded)>limits.control_document_bytes:
            raise ManagedMcpError('resource_arguments_too_large',stage='admission',executed=False)
        deadline=deadline if deadline is not None else time.monotonic()+limits.mcp_initialize_seconds
        descriptor=self.process.stdin.fileno()
        os.set_blocking(descriptor,False)
        with selectors.DefaultSelector() as selector:
            selector.register(descriptor,selectors.EVENT_WRITE)
            offset=0
            while offset<len(encoded):
                remaining=deadline-time.monotonic()
                if remaining<=0 or not selector.select(remaining):raise TimeoutError('MCP write deadline')
                try:offset+=os.write(descriptor,encoded[offset:])
                except BlockingIOError:continue

    def _read(self,deadline):
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout,selectors.EVENT_READ)
            while True:
                if b'\n' in self.pending:
                    line,_,tail=self.pending.partition(b'\n')
                    self.pending=bytearray(tail)
                    return json.loads(line)
                remaining=deadline-time.monotonic()
                if remaining<=0 or not selector.select(remaining):
                    raise TimeoutError('MCP response deadline')
                chunk=os.read(self.process.stdout.fileno(),65536)
                if not chunk:raise OSError('MCP connection ended')
                self.pending.extend(chunk)
                if len(self.pending)>limits.control_document_bytes:
                    raise ValueError('MCP response exceeds accepted frame')

    def exchange(self,call,*,deadline):
        if not self.lock.acquire(timeout=max(0,deadline-time.monotonic())):
            raise ManagedMcpError('resource_task_deadline',stage='admission',executed=False)
        dispatched=False
        try:
            if self.closed or self.process.poll() is not None:
                raise ManagedMcpError('resource_session_closed',stage='admission',executed=False)
            self.sequence+=1
            dispatched=True
            self._write({'id':self.sequence,'call':call,'timeout_seconds':max(.001,deadline-time.monotonic())},deadline)
            receipt=self._read(deadline)
            if not isinstance(receipt,dict) or receipt.get('id')!=self.sequence:raise ValueError('MCP response identity changed')
            if receipt.get('ok') is True:return receipt['result']
            error=receipt.get('error')
            if (not isinstance(error,dict) or not isinstance(error.get('code'),str)
                    or not re.fullmatch(r'resource_[a-z_]{1,80}',error['code'])
                    or error.get('stage') not in {'admission','discovery','launch','execution'}
                    or error.get('executed') is not None and type(error['executed']) is not bool):
                raise ValueError('MCP error receipt is invalid')
            raise ManagedMcpError(error['code'],stage=error['stage'],executed=error['executed'])
        except ManagedMcpError:
            raise
        except (OSError,ValueError,TimeoutError) as error:
            self.close()
            raise ManagedMcpError('resource_call_outcome_unknown' if call is not None and dispatched else 'resource_discovery_unavailable',
                stage='execution' if call is not None and dispatched else 'discovery',
                executed=None if call is not None and dispatched else False) from error
        finally:
            self.lock.release()

    def close(self):
        if self.closed:return
        self.closed=True
        try:
            if self.process.poll() is None:
                import signal
                os.killpg(self.process.pid,signal.SIGTERM)
                try:self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(self.process.pid,signal.SIGKILL)
                    self.process.wait(timeout=2)
        finally:
            self.process.stdin.close()
            self.process.stdout.close()
            self.cleanup()
