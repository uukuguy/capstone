#!/usr/bin/env python3
"""Render saved report text, CSV strings and figures without interpreting facts."""
import argparse
import base64
import csv
import hashlib
from html import escape
import io
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
from xml.etree import ElementTree


VERSION = '1.0.0'
CSS = '''
:root{color-scheme:light;font-family:system-ui,-apple-system,"Noto Sans CJK SC",sans-serif;color:#172b3b;background:#edf2f5}
*{box-sizing:border-box}body{margin:0;line-height:1.75}main{max-width:1100px;margin:32px auto;background:white;padding:48px 56px;border:1px solid #d8e2e8;border-radius:12px}
header{border-bottom:3px solid #217778;padding-bottom:24px;margin-bottom:28px}h1{font-size:2rem;line-height:1.35;margin:0 0 12px}h2{font-size:1.35rem;color:#175e61;margin:36px 0 16px}header p{color:#526774}
nav{background:#f3f7f8;border:1px solid #d8e2e8;padding:16px 24px}nav a{color:#175e61;text-decoration:none}section{scroll-margin-top:24px}p{white-space:pre-wrap;overflow-wrap:anywhere}li{margin:6px 0}
.table-wrap{overflow-x:auto;margin:24px 0}table{width:100%;border-collapse:collapse;font-size:.9rem}caption{text-align:left;font-weight:600;padding:0 0 10px}th,td{border:1px solid #d8e2e8;text-align:left;vertical-align:top;padding:9px 12px;white-space:pre-wrap;overflow-wrap:anywhere}th{background:#eaf2f3}tbody tr:nth-child(even){background:#f8fafb}
figure{margin:28px 0;break-inside:avoid}figure img{display:block;max-width:100%;height:auto;margin:auto}figcaption{text-align:center;color:#526774;font-size:.92rem;margin-top:12px}footer{border-top:1px solid #d8e2e8;color:#526774;font-size:.8rem;margin-top:40px;padding-top:16px}
@media(max-width:700px){main{margin:0;padding:24px 18px;border:0;border-radius:0}h1{font-size:1.7rem}}
@media print{@page{size:A4;margin:18mm}body{background:white}main{max-width:none;margin:0;padding:0;border:0}nav{break-inside:avoid}h2,caption{break-after:avoid}thead{display:table-header-group}tr{break-inside:avoid}.table-wrap{overflow:visible}a{color:inherit;text-decoration:none}}
'''


class ReportError(ValueError):
    def __init__(self, message, *, diagnostic=None):
        super().__init__(message)
        self.diagnostic = diagnostic


def text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ReportError(field + ' must be nonempty text')
    return value


def fields(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= value.keys() or set(value) - set(required) - set(optional):
        raise ReportError('missing or unknown report fields')


class Workspace:
    """Use directory descriptors so path checks and actual IO share a boundary."""
    def __init__(self):
        self.root = os.open('.', os.O_RDONLY | os.O_DIRECTORY)
        self.sources = {}
        self.identities = set()

    def parent(self, value):
        text(value, 'file path')
        parts = value.split('/')
        if any(part in {'', '.', '..'} for part in parts) or any(c in value for c in ('\\', ':', '\0')):
            raise ReportError('file paths must stay within the current workspace')
        current = os.dup(self.root)
        try:
            for part in parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
                os.close(current)
                current = child
            return current, parts[-1]
        except BaseException:
            os.close(current)
            raise

    def read(self, value, *, location='spec'):
        parent = None
        try:
            parent, name = self.parent(value)
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            with os.fdopen(descriptor, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode):
                    raise ReportError('report sources must be regular files')
                data = stream.read()
                self.identities.add((info.st_dev, info.st_ino))
        except OSError as error:
            code = 'source_missing' if isinstance(error, FileNotFoundError) else 'source_unavailable'
            raise ReportError('Cannot read report source at ' + location + ': ' + json.dumps(value, ensure_ascii=False),
                diagnostic={'code': code, 'path': value, 'location': location}) from None
        finally:
            if parent is not None:
                os.close(parent)
        digest = hashlib.sha256(data).hexdigest()
        if value in self.sources and self.sources[value] != digest:
            raise ReportError('a report source changed during rendering')
        self.sources[value] = digest
        return data

    def write(self, value, data):
        parent, name = self.parent(value)
        temporary = '.capstone-report-' + secrets.token_hex(16)
        try:
            if value in self.sources:
                raise ReportError('output must not overwrite the spec or any source')
            try:
                info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                info = None
            if info is not None and (not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) in self.identities):
                raise ReportError('output must not overwrite a source or symbolic link')
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(data)
            os.replace(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
        finally:
            try:
                os.unlink(temporary, dir_fd=parent)
            except FileNotFoundError:
                pass
            os.close(parent)


def figure_data(path, data):
    suffix = Path(path).suffix.lower()
    if suffix == '.svg':
        if b'<!ENTITY' in data.upper():
            raise ReportError('SVG entities are not supported')
        try:
            root = ElementTree.fromstring(data)
        except ElementTree.ParseError:
            raise ReportError('invalid SVG figure') from None
        if root.tag.rsplit('}', 1)[-1] != 'svg':
            raise ReportError('figure is not an SVG document')
        for node in root.iter():
            if node.tag.rsplit('}', 1)[-1].lower() in {'script', 'foreignobject', 'animate', 'animatemotion', 'animatetransform', 'set', 'discard'}:
                raise ReportError('active SVG content is not supported')
            for key, value in node.attrib.items():
                attribute = key.rsplit('}', 1)[-1].lower()
                if attribute.startswith('on'):
                    raise ReportError('active SVG attributes are not supported')
                if attribute in {'href', 'src'} and not (value.startswith('#') or re.fullmatch(r'data:image/(?:png|jpeg);base64,[A-Za-z0-9+/=\s]+', value)):
                    raise ReportError('SVG external references are not supported')
            styles = ' '.join([*node.attrib.values(), node.text or ''])
            if '@import' in styles.lower() or any(not url.strip(' \t\r\n\"\x27').startswith('#') for url in re.findall(r'url\s*\((.*?)\)', styles, re.I | re.S)):
                raise ReportError('SVG external styles are not supported')
        media = 'image/svg+xml'
    elif suffix == '.png' and data.startswith(b'\x89PNG\r\n\x1a\n'):
        media = 'image/png'
    elif suffix in {'.jpg', '.jpeg'} and data.startswith(b'\xff\xd8\xff'):
        media = 'image/jpeg'
    else:
        raise ReportError('figures must be saved PNG, JPEG or safe SVG files')
    return 'data:' + media + ';base64,' + base64.b64encode(data).decode('ascii')


def render(spec_path, output):
    workspace = Workspace()
    try:
        spec = json.loads(workspace.read(spec_path))
        fields(spec, ('title', 'sections'), ('subtitle', 'schema'))
        if spec.get('schema', 'capstone-report/1') != 'capstone-report/1':
            raise ReportError('unsupported report schema')
        title = escape(text(spec['title'], 'title'))
        subtitle = '<p>' + escape(text(spec['subtitle'], 'subtitle')) + '</p>' if 'subtitle' in spec else ''
        if not isinstance(spec['sections'], list) or not spec['sections']:
            raise ReportError('sections must be a nonempty list')
        identities, navigation, sections, figures = set(), [], [], 0
        for number, section in enumerate(spec['sections'], 1):
            fields(section, ('id', 'title', 'blocks'))
            identity = text(section['id'], 'section id')
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', identity) or identity in identities:
                raise ReportError('section ids must be unique letters, digits, hyphens or underscores')
            identities.add(identity)
            heading = escape(text(section['title'], 'section title'))
            anchor = 'section-' + identity
            navigation.append(f'<li><a href="#{anchor}">{number}. {heading}</a></li>')
            if not isinstance(section['blocks'], list):
                raise ReportError('blocks must be a list')
            blocks = []
            for block_index, block in enumerate(section['blocks']):
                location = f'sections[{number - 1}].blocks[{block_index}]'
                if not isinstance(block, dict):
                    raise ReportError('each block must be an object')
                kind = block.get('type')
                if kind == 'paragraph':
                    fields(block, ('type', 'text'))
                    blocks.append('<p>' + escape(text(block['text'], 'paragraph')) + '</p>')
                elif kind == 'bullets':
                    fields(block, ('type', 'items'))
                    if not isinstance(block['items'], list) or not block['items']:
                        raise ReportError('bullet items must be a nonempty list')
                    blocks.append('<ul>' + ''.join('<li>' + escape(text(item, 'bullet')) + '</li>' for item in block['items']) + '</ul>')
                elif kind == 'table':
                    fields(block, ('type', 'csv'), ('columns', 'caption'))
                    csv.field_size_limit(sys.maxsize)
                    reader = csv.reader(io.StringIO(workspace.read(block['csv'], location=location + '.csv').decode('utf-8-sig'), newline=''), strict=True)
                    header = next(reader, [])
                    if not header or len(set(header)) != len(header):
                        raise ReportError('CSV must have a nonempty unique header')
                    columns = block.get('columns', header)
                    if not isinstance(columns, list) or not columns or any(not isinstance(column, str) for column in columns) or len(set(columns)) != len(columns) or any(column not in header for column in columns):
                        raise ReportError('table columns must be unique existing CSV headers')
                    indices = [header.index(column) for column in columns]
                    rows = []
                    for row in reader:
                        if len(row) != len(header):
                            raise ReportError('CSV row length does not match its header')
                        rows.append('<tr>' + ''.join('<td>' + escape(row[index]) + '</td>' for index in indices) + '</tr>')
                    caption = '<caption>' + escape(text(block['caption'], 'table caption')) + '</caption>' if 'caption' in block else ''
                    blocks.append('<div class="table-wrap"><table>' + caption + '<thead><tr>' + ''.join('<th scope="col">' + escape(column) + '</th>' for column in columns) + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>')
                elif kind == 'figure':
                    fields(block, ('type', 'path', 'caption'))
                    caption = escape(text(block['caption'], 'figure caption'))
                    source = figure_data(block['path'], workspace.read(block['path'], location=location + '.path'))
                    figures += 1
                    blocks.append(f'<figure id="figure-{figures}"><img src="{source}" alt="{caption}"><figcaption>图 {figures} · {caption}</figcaption></figure>')
                else:
                    raise ReportError('unknown report block type')
            sections.append(f'<section id="{anchor}"><h2>{number}. {heading}</h2>' + ''.join(blocks) + '</section>')
        html = ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
            '<title>' + title + '</title><style>' + CSS + '</style></head><body><main><header><h1>' + title + '</h1>' + subtitle + '</header>'
            '<nav aria-label="目录"><strong>目录</strong><ol>' + ''.join(navigation) + '</ol></nav>' + ''.join(sections)
            + '<footer>本文由保存的文字、CSV 与图片排版生成。排版及源文件绑定不表示已验证数值口径、图注或结论。</footer></main></body></html>')
        workspace.write(output, html.encode('utf-8'))
        return {'schema': 'capstone-report-receipt/1', 'output': output, 'sections': len(sections),
            'figures': figures, 'source_sha256': workspace.sources}
    finally:
        os.close(workspace.root)


def main():
    parser = argparse.ArgumentParser(description='Render report JSON with escaped text, exact CSV values and embedded PNG/JPEG/SVG figures. Paths are relative to the current workspace; no raw HTML or network resources.')
    parser.add_argument('--version', action='version', version='capstone-report ' + VERSION)
    parser.add_argument('--spec', required=True, help='Saved UTF-8 report JSON: title, subtitle?, sections[{id,title,blocks}]. Blocks: paragraph(text), bullets(items), table(csv,columns?,caption?), figure(path,caption).')
    parser.add_argument('--output', required=True, help='HTML output within the current workspace; parent directory must exist.')
    args = parser.parse_args()
    try:
        receipt = render(args.spec, args.output)
    except ReportError as error:
        print('capstone-report: ' + str(error), file=sys.stderr)
        if error.diagnostic:
            print(json.dumps(error.diagnostic, ensure_ascii=False), file=sys.stderr)
        return 2
    except (OSError, ValueError, csv.Error):
        print('capstone-report: cannot read or write a workspace file, or invalid UTF-8/JSON/CSV; check saved sources and paths', file=sys.stderr)
        return 2
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
