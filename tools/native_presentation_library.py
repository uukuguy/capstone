#!/usr/bin/env python3
"""Render frozen presentation inputs as the unprivileged native task user."""
import argparse
from contextlib import contextmanager
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from zipfile import BadZipFile, ZipFile, ZIP_DEFLATED

from native_report import ReportError, Workspace, render_presentation

BUDGET = 128 * 1024 * 1024


def content_contract():
    return {'schema':'capstone-presentation-content-contract/1',
        'formats':['capstone-presentation/1','capstone-presentation/2'],
        'required_fields':['schema','title','slides'],'optional_fields':['subtitle'],
        'slide_required_fields':['title','blocks'],
        'slide_optional_fields':['role','section','source_notes','speaker_notes','argument'],
        'slide_defaults':{'role':'content'},'roles':['content','agenda','closing'],
        'rules':[
            'Version 2 content slides require argument:{explanation:<literal visible reasoning>}; version 1 omits argument.',
            'An agenda uses paragraph(text) or bullets(items) with unique exact chapter titles.',
            'When an agenda exists, each content slide section must equal one chapter title in nondecreasing agenda order; each chapter has content.',
            'Missing role means content. Closing is last and has zero blocks or one short paragraph.',
            'The library selects the template. Do not add author, date, cover or other unsupported root fields.',
            'Template composition keeps one saved record per slide. Fix overflow without silently splitting pages or shrinking fonts.'],
        'blocks':{'paragraph':{'required':['type','text']},'bullets':{'required':['type','items']},
            'table':{'required':['type','csv','max_rows'],'optional':['columns','caption']},
            'figure':{'required':['type','path','caption']}},
        'example':{'schema':'capstone-presentation/2','title':'Supported findings',
            'slides':[{'role':'agenda','title':'Contents','blocks':[{'type':'bullets','items':['Scope']}]},
                {'section':'Scope','title':'Available evidence','argument':{'explanation':'State the supported finding and its limits.'},
                 'blocks':[{'type':'paragraph','text':'Use saved source facts; retain unresolved gaps.'}]},
                {'role':'closing','title':'Thank you','blocks':[]}]}}


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def source_path(value):
    if (not isinstance(value, str) or not value or any(c in value for c in ('\\', ':', '\0'))
            or value.startswith('/') or any(p in {'', '.', '..'} for p in value.split('/'))):
        raise ReportError('presentation source path is invalid')
    return value


def write_new(workspace, name, raw):
    parent, leaf = workspace.parent(name)
    try:
        descriptor = os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(raw)
    finally:
        os.close(parent)


def register_products(workspace, outputs):
    manifest_name = '.capstone-products.json'
    try:
        os.stat(manifest_name, dir_fd=workspace.root, follow_symlinks=False)
    except FileNotFoundError:
        manifest = {'schema': 'capstone-workspace-products/1', 'products': []}
    else:
        descriptor = os.open(manifest_name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=workspace.root)
        with os.fdopen(descriptor, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ReportError('saved product manifest is invalid')
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ReportError('saved product manifest exceeds its processing budget')
        manifest = json.loads(raw)
        if (not isinstance(manifest, dict) or manifest.get('schema') != 'capstone-workspace-products/1'
                or not isinstance(manifest.get('products'), list)):
            raise ReportError('saved product manifest is invalid')
    manifest['products'] = [p for p in manifest['products'] if p.get('path') not in outputs] + [
        {'path': name, 'role': role} for name, role in outputs.items()]
    if len(manifest['products']) > 128 or len(encoded(manifest)) > 65536:
        raise ReportError('saved product manifest exceeds its processing budget')
    workspace.write(manifest_name, encoded(manifest))


@contextmanager
def working_directory(path):
    descriptor = os.open('.', os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.chdir(path)
        yield
    finally:
        os.fchdir(descriptor)
        os.close(descriptor)


def frozen_inputs(workspace, *, spec=None, bundle=None):
    if spec:
        document = json.loads(workspace.read(spec, maximum=1024 * 1024))
        if not isinstance(document, dict):
            raise ReportError('presentation content must be an object')
        # Template choice belongs to the current admitted selection, not content.
        document.pop('template', None)
        sources = {}
        for slide in document.get('slides', []):
            for block in slide.get('blocks', []):
                field = {'table': 'csv', 'figure': 'path'}.get(block.get('type'))
                if field:
                    path = source_path(block.get(field))
                    sources[path] = workspace.read(path, maximum=64 * 1024 * 1024)
                    if sum(map(len, sources.values())) > BUDGET:
                        raise ReportError('presentation dependencies exceed the processing budget')
        return document, sources
    raw = workspace.read(bundle, maximum=BUDGET)
    with ZipFile(BytesIO(raw)) as archive:
        if not {'content.json', 'manifest.json'} <= set(archive.namelist()):
            raise ReportError('The original presentation content bundle is unavailable', diagnostic={
                'code': 'presentation_content_unavailable', 'output_written': False,
                'recovery': 'Obtain the saved source bundle, or offer content recovery. An older PPTX alone cannot prove an exact rerender.'})
        items = archive.infolist()
        if (len(items) > 4096 or len({i.filename for i in items}) != len(items)
                or sum(i.file_size for i in items) > BUDGET
                or any(i.flag_bits & 1 for i in items)):
            raise ReportError('presentation bundle exceeds the processing budget')
        manifest = json.loads(archive.read('manifest.json'))
        document = json.loads(archive.read('content.json'))
        if (manifest.get('schema') != 'capstone-presentation-source/1'
                or sha256(encoded(document)).hexdigest() != manifest.get('content_sha256')
                or not isinstance(manifest.get('sources'), dict)):
            raise ReportError('presentation bundle identity changed')
        sources = {source_path(name): archive.read('sources/' + source_path(name)) for name in manifest['sources']}
        if set(archive.namelist()) != {'manifest.json', 'content.json', *('sources/' + name for name in sources)}:
            raise ReportError('presentation bundle contains unknown entries')
        if any(sha256(raw).hexdigest() != manifest['sources'][name] for name, raw in sources.items()):
            raise ReportError('presentation dependency identity changed')
        return document, sources


def render_library(*, spec=None, bundle=None, output, template, template_sha256, template_id=None, pdf=False):
    if not re.fullmatch('[a-f0-9]{64}', template_sha256):
        raise ReportError('presentation template digest is invalid')
    if template_id is not None and not re.fullmatch(r'(?:state-grid|tpl_[a-f0-9]{32})', template_id):
        raise ReportError('presentation template identity is invalid')
    workspace = Workspace()
    try:
        output = source_path(output)
        if PurePosixPath(output).suffix != '.pptx':
            raise ReportError('presentation output must be PPTX')
        stem = str(PurePosixPath(output).with_suffix(''))
        outputs = [output, stem + '.source.zip', stem + '.receipt.json', *([stem + '.pdf'] if pdf else [])]
        for name in outputs:
            parent, leaf = workspace.parent(name)
            try:
                try:
                    os.stat(leaf, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    raise ReportError('presentation output already exists; use a new version path')
            finally:
                os.close(parent)
        document, sources = frozen_inputs(workspace, spec=spec, bundle=bundle)
        descriptor = os.open(template, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, 'rb') as stream:
            template_bytes = stream.read(32 * 1024 * 1024 + 1)
        if len(template_bytes) > 32 * 1024 * 1024 or sha256(template_bytes).hexdigest() != template_sha256:
            raise ReportError('presentation template identity changed')
        content_sha = sha256(encoded(document)).hexdigest()
        manifest = {'schema': 'capstone-presentation-source/1', 'content_sha256': content_sha,
            'sources': {name: sha256(raw).hexdigest() for name, raw in sources.items()}}
        buffer = BytesIO()
        with ZipFile(buffer, 'w', ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json', encoded(manifest))
            archive.writestr('content.json', encoded(document))
            for name, raw in sources.items():
                archive.writestr('sources/' + name, raw)
        if buffer.tell() > BUDGET:
            raise ReportError('presentation bundle exceeds the processing budget')
        with tempfile.TemporaryDirectory(prefix='capstone-presentation-') as temporary:
            root = Path(temporary)
            for name, raw in sources.items():
                target = root / 'content' / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
            (root / 'content').mkdir(exist_ok=True)
            (root / 'template.pptx').write_bytes(template_bytes)
            selection = {'path': 'template.pptx'}
            if template_id == 'state-grid':
                # Preserve the built-in layout contract while using the frozen bytes.
                selection.update(content_slide=3, agenda_slide=2)
            rendered = {**document, 'template': selection}
            # Preserve content-relative source names in a separate namespace.
            rendered = json.loads(encoded(rendered))
            for slide in rendered.get('slides', []):
                for block in slide.get('blocks', []):
                    field = {'table': 'csv', 'figure': 'path'}.get(block.get('type'))
                    if field:
                        block[field] = 'content/' + block[field]
            (root / 'spec.json').write_bytes(encoded(rendered))
            with working_directory(root):
                renderer = render_presentation('spec.json', 'result.pptx')
            pdf_result, pdf_bytes = {'status': 'not_requested'}, None
            if pdf:
                converter = shutil.which('libreoffice') or shutil.which('soffice')
                pdf_result = {'status': 'unavailable', 'code': 'pdf_converter_unavailable'}
                if converter:
                    try:
                        result = subprocess.run([converter, '-env:UserInstallation=' + (root / 'profile').as_uri(),
                            '--headless', '--convert-to', 'pdf', '--outdir', str(root), str(root / 'result.pptx')],
                            capture_output=True, timeout=90, check=False)
                        candidate = root / 'result.pdf'
                        if result.returncode == 0 and candidate.is_file() and candidate.stat().st_size <= 64 * 1024 * 1024:
                            pdf_bytes = candidate.read_bytes()
                            if not pdf_bytes.startswith(b'%PDF-'):
                                pdf_bytes = None
                        pdf_result = {'status': 'ready', 'path': stem + '.pdf'} if pdf_bytes else {
                            'status': 'failed', 'code': 'pdf_conversion_failed'}
                    except (OSError, subprocess.TimeoutExpired):
                        pdf_result = {'status': 'failed', 'code': 'pdf_conversion_failed'}
            pptx = (root / 'result.pptx').read_bytes()
            receipt = {'schema': 'capstone-presentation-library-render/1', 'output': output,
                'library_source_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
                'output_sha256': sha256(pptx).hexdigest(), 'content_sha256': content_sha,
                'template_sha256': template_sha256, 'bundle': stem + '.source.zip',
                'template_id': template_id,
                'bundle_sha256': sha256(buffer.getvalue()).hexdigest(), 'pdf': pdf_result, 'renderer': renderer}
            write_new(workspace, output, pptx)
            write_new(workspace, stem + '.source.zip', buffer.getvalue())
            products = {output: 'primary', stem + '.source.zip': 'reproduction', stem + '.receipt.json': 'support'}
            if pdf_bytes is not None:
                write_new(workspace, stem + '.pdf', pdf_bytes)
                products[stem + '.pdf'] = 'primary'
                receipt['pdf']['sha256'] = sha256(pdf_bytes).hexdigest()
            write_new(workspace, stem + '.receipt.json', encoded(receipt))
            register_products(workspace, products)
            return receipt
    finally:
        os.close(workspace.root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version='capstone-presentation 1.0.0')
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--contract',action='store_true')
    source.add_argument('--spec')
    source.add_argument('--bundle')
    parser.add_argument('--output')
    parser.add_argument('--template')
    parser.add_argument('--template-sha256')
    parser.add_argument('--template-id')
    parser.add_argument('--pdf', action='store_true')
    arguments=vars(parser.parse_args())
    if arguments.pop('contract'):
        print(json.dumps(content_contract(),ensure_ascii=False))
        return
    if any(not arguments[key] for key in ('output','template','template_sha256')):
        parser.error('render requires --output, --template and --template-sha256; use agent_presentations render for the admitted session template, or --contract to read content fields')
    try:
        print(json.dumps(render_library(**arguments), ensure_ascii=False))
    except ReportError as error:
        failure = {'schema': 'capstone-presentation-render-error/1',
            'code': 'presentation_render_rejected', 'message': str(error)[:600],
            'diagnostic': error.diagnostic, 'delivery_confirmed': False}
        if len(encoded(failure)) > 16384:
            failure['diagnostic'] = {'code': 'diagnostic_exceeds_display_budget'}
        print(json.dumps(failure, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, BadZipFile):
        print('Presentation rendering failed; no new delivery is confirmed.', file=sys.stderr)
        raise SystemExit(2)


if __name__ == '__main__':
    main()
