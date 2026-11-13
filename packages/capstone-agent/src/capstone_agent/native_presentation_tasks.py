"""Task-bound private adapter for the application's durable template service."""
from hashlib import sha256
import os
from pathlib import Path
import re
from threading import RLock
from urllib.parse import quote, urlsplit
import httpx

from .presentation_template_contract import CHUNK_BYTES, checked_template_descriptor, checked_template_reference
from .workspace_scope import workspace_name


class TemplateOutcomeUnknown(RuntimeError):
    def __init__(self, request_id):
        self.request_id = request_id
        super().__init__('template_operation_outcome_unknown')


class TemplateBackendClient:
    def __init__(self, origin, token, workspace, thread, *, client=None):
        parsed = urlsplit(origin)
        if (parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path not in {'', '/'}):
            raise ValueError('presentation_api_origin_invalid')
        if not isinstance(thread, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', thread):
            raise ValueError('presentation_thread_invalid')
        if not isinstance(token, str) or not token:
            raise ValueError('presentation_api_authentication_missing')
        self.workspace, self.thread_id = workspace_name(workspace), thread
        self.base = origin.rstrip('/') + '/api/v1/threads/' + quote(thread, safe='') + '/presentation-templates'
        self.headers = {'Authorization': 'Bearer ' + token, 'Capstone-Thread-Version': '2',
                        'Capstone-Workspace': quote(workspace_name(workspace), safe='')}
        self.owned = client is None
        self.client = client or httpx.Client(timeout=30, follow_redirects=False, trust_env=False)

    def close(self):
        if self.owned:
            self.client.close()

    def request(self, method, suffix='', *, body=None, request_id=None):
        try:
            with self.client.stream(method, self.base + suffix, json=body, headers=self.headers) as response:
                data = bytearray()
                for chunk in response.iter_bytes(8192):
                    if len(data) + len(chunk) > 128 * 1024:
                        raise ValueError('presentation_response_too_large')
                    data.extend(chunk)
                if not response.is_success:
                    if response.status_code >= 500 and method != 'GET':
                        raise TemplateOutcomeUnknown(request_id)
                    import json
                    try:
                        code = json.loads(data).get('detail')
                    except (ValueError, AttributeError):
                        code = None
                    allowed = {'template_request_conflict', 'template_revision_conflict',
                               'template_source_changed', 'template_identity_changed', 'template_not_found',
                               'template_processing_limit', 'template_cursor_invalid', 'invalid_template'}
                    raise ValueError(code if isinstance(code, str) and code in allowed else 'presentation_backend_rejected')
        except httpx.HTTPError:
            raise TemplateOutcomeUnknown(request_id) from None
        import json
        value = json.loads(data)
        if not isinstance(value, dict):
            raise ValueError('presentation_response_invalid')
        return value

    def command(self, body):
        value = self.request('POST', '/commands', body=body, request_id=body.get('request_id'))
        if value.get('ok') is not True or not isinstance(value.get('result'), dict):
            raise ValueError('presentation_response_invalid')
        return value['result']

    def download(self, template, target):
        path = '/' + quote(template['template_id'], safe='') + '/versions/' + quote(template['version'], safe='') + '/content'
        digest, size = sha256(), 0
        with self.client.stream('GET', self.base + path, headers=self.headers) as response:
            if not response.is_success:
                raise ValueError('presentation_backend_rejected')
            with target.open('xb') as output:
                for chunk in response.iter_bytes(CHUNK_BYTES):
                    size += len(chunk)
                    if size > template['size_bytes']:
                        raise ValueError('template_identity_changed')
                    digest.update(chunk)
                    output.write(chunk)
        if size != template['size_bytes'] or digest.hexdigest() != template['sha256']:
            raise ValueError('template_identity_changed')


class PresentationTaskPort:
    def __init__(self, client, *, task_id, inputs, uid, admitted_resources=()):
        self.client, self.task_id = client, task_id
        self.inputs, self.uid = Path(inputs).absolute(), uid
        self.admitted_resources = tuple(admitted_resources)
        self.lock = RLock()

    @staticmethod
    def _fields(document, required=(), optional=()):
        if (not isinstance(document, dict) or not set(required) <= set(document)
                or set(document) - set(required) - set(optional)):
            raise ValueError('presentation_request_invalid')

    def invoke(self, operation, document, *, call_id):
        if not isinstance(call_id, str) or not 0 < len(call_id) <= 256:
            raise ValueError('presentation_call_invalid')
        request_id = 'presentation_' + sha256((self.task_id + '\0' + call_id).encode()).hexdigest()
        if operation == 'catalog':
            self._fields(document, optional=('after', 'limit'))
            from urllib.parse import urlencode
            result = self.client.request('GET', '?' + urlencode(document) if document else '')
            result['admitted_uploads'] = [dict(r) for r in self.admitted_resources if
                                          r.get('file_name', '').lower().endswith('.pptx')]
            return result
        if operation == 'operation':
            self._fields(document, ('request_id',))
            if not isinstance(document['request_id'], str) or not re.fullmatch(r'presentation_[a-f0-9]{64}', document['request_id']):
                raise ValueError('presentation_request_invalid')
            return self.client.request('GET', '/operations/' + document['request_id'])
        if operation == 'materialize':
            self._fields(document, optional=('reference',))
            template = checked_template_descriptor(self.client.command({'operation': 'freeze', 'reference': document.get('reference')}))
            with self.lock:
                return self._materialize(template)
        if operation == 'add':
            self._fields(document, ('resource', 'name'))
            reference = document['resource']
            fields = ('resource_id', 'version', 'sha256')
            if (not isinstance(reference, dict) or set(reference) != set(fields)
                    or type(reference.get('version')) is not int or reference['version'] < 1
                    or not any(all(reference[k] == r[k] for k in fields) for r in self.admitted_resources)):
                raise ValueError('presentation_source_not_admitted')
        elif operation == 'select':
            self._fields(document, ('reference', 'expected_revision'))
            checked_template_reference(document['reference'])
        elif operation == 'publish':
            self._fields(document, ('reference',))
            checked_template_reference(document['reference'])
        else:
            raise ValueError('presentation_operation_unknown')
        return self.client.command({'operation': operation, 'request_id': request_id, **document})

    def _materialize(self, template):
        for parent in (self.inputs, *self.inputs.parents):
            if parent.is_symlink():
                raise ValueError('presentation_input_identity_changed')
        directory = self.inputs / 'presentation-templates' / template['template_id']
        for path in (self.inputs, directory.parent, directory):
            if path.is_symlink():
                raise ValueError('presentation_input_identity_changed')
            path.mkdir(parents=True, exist_ok=True)
            if os.geteuid() == 0:
                os.chown(path, 0, self.uid)
            path.chmod(0o750)
        target = directory / (template['sha256'] + '.pptx')
        temporary = directory / ('.pending-' + template['sha256'])
        try:
            if target.exists() or target.is_symlink():
                if target.is_symlink() or target.stat().st_size != template['size_bytes']:
                    raise ValueError('template_identity_changed')
                with target.open('rb') as incoming:
                    digest = sha256()
                    while chunk := incoming.read(CHUNK_BYTES):
                        digest.update(chunk)
                if digest.hexdigest() != template['sha256']:
                    raise ValueError('template_identity_changed')
            else:
                self.client.download(template, temporary)
                if os.geteuid() == 0:
                    os.chown(temporary, 0, self.uid)
                temporary.chmod(0o440)
                temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
            directory.chmod(0o550)
        return {'schema': 'capstone-presentation-template-input/1', 'template': template, 'path': str(target)}
