"""Reusable research methods over the public native Domain Pack SPI."""
from importlib.resources import files


class ResearchPolicy:
    def __init__(self, version='1.0.0', *, variant='default'):
        self._prefix = _resource_prefix(version, variant)
        self._version = version

    def load(self) -> str:
        return files(__package__).joinpath(self._prefix + 'system-policy.md').read_text(encoding='utf-8')

    def progress_guidance(self) -> str:
        return files(__package__).joinpath(self._prefix + 'progress-guidance.md').read_text(encoding='utf-8')


def _resource_prefix(version, variant='default'):
    if version not in {'1.0.0', '1.1.0', '1.2.0', '1.3.0', '1.4.0', '1.5.0', '1.6.0', '1.7.0', '1.8.0', '1.9.0', '1.10.0', '1.11.0', '1.12.0', '1.13.0', '1.14.0', '1.15.0', '1.16.0', '1.17.0'}:
        raise ValueError('Research Pack version is not registered')
    if variant != 'default' and (version, variant) != ('1.2.0', 'initial-review'):
        raise ValueError('Research Pack resource variant is not registered')
    return 'resources/versions/' + version + '/' + ('' if variant == 'default' else variant + '/')


class ResearchGuides:
    _documents = {'research-method': 'Research methods and source checks'}

    def __init__(self, version='1.0.0', *, variant='default'):
        self._prefix = _resource_prefix(version, variant)

    def load(self) -> tuple:
        return tuple({'resource_id': key, 'title': title} for key, title in self._documents.items())

    def open(self, resource_id: str) -> dict:
        if resource_id not in self._documents:
            raise KeyError(resource_id)
        return {'resource_id': resource_id, 'title': self._documents[resource_id],
            'text': files(__package__).joinpath(self._prefix + resource_id + '.md').read_text(encoding='utf-8')}


class ResearchAcceptance:
    def cases(self) -> tuple:
        return ('ordinary-answer-without-graph', 'source-contradiction-revision',
                'committed-view-next-request', 'unadmitted-source-rejected',
                'cancel-and-recover-receipt', 'file-product-with-provenance')


def build_profile(version='1.0.0', *, variant='default'):
    from capability_agent.domain.manifest import PackManifest
    from capability_agent.domain.profile import NativeDomainRuntimeProfile, NativeExecutionConfig
    return NativeDomainRuntimeProfile(PackManifest('enterprise-research-methods', version,
        'Evidence-aware research methods'), NativeExecutionConfig('delegated_pi',
        'capstone-pi-task-result/1'), ResearchPolicy(version, variant=variant), ResearchGuides(version, variant=variant))
