"""Stage read-only source archives from a Capstone commit and an installed gateway release."""
import argparse
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import tempfile
import zipfile


EXTENSIONS = {'.py', '.ts', '.tsx', '.js', '.mjs', '.css', '.html', '.sql', '.toml', '.sh'}


def admitted(name):
    path = PurePosixPath(name)
    return (not path.is_absolute() and '..' not in path.parts and not any(p.startswith('.') for p in path.parts)
            and (path.suffix in EXTENSIONS or path.name == 'SKILL.md'))


def write_entry(archive, name, data):
    entry = zipfile.ZipInfo(name)
    entry.external_attr = 0o100444 << 16
    archive.writestr(entry, data, compress_type=zipfile.ZIP_DEFLATED)


def stage(root, gateway_releases, destination, *, gateway_only=False, capstone_revision=None):
    revision = None if gateway_only else capstone_revision or subprocess.check_output(
        ['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    destination.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as tmp:
        tmp = Path(tmp)
        versions = []
        if revision:
            with tempfile.TemporaryFile() as source:
                subprocess.run(['git','archive',revision,'packages','configs/runtime','deploy','tools','scripts'],
                               cwd=root,stdout=source,check=True)
                source.seek(0)
                with tarfile.open(fileobj=source) as files, zipfile.ZipFile(tmp/'capstone.zip','w') as archive:
                    for entry in files:
                        if entry.isfile() and admitted(entry.name):
                            write_entry(archive,entry.name,files.extractfile(entry).read())
            versions.append(('capstone',revision,'capstone.zip'))
        for gateway_release in gateway_releases:
            manifest = json.loads((gateway_release / 'release.json').read_text())
            version = manifest['source_sha256']
            if len(version)!=64 or any(ch not in '0123456789abcdef' for ch in version):
                raise ValueError('Invalid gateway release digest')
            filename = f'data-gateway-{version}.zip'
            if (tmp/filename).exists():
                continue
            with zipfile.ZipFile(tmp/filename,'w') as archive:
                for name,digest in sorted(manifest['files_sha256'].items()):
                    if not admitted(name) or name.split('/')[0] not in {'src','providers','scripts','engines'}:
                        continue
                    file = (gateway_release/name).resolve()
                    if not file.is_relative_to(gateway_release.resolve()):
                        raise ValueError('Gateway source path outside release')
                    data = file.read_bytes()
                    if hashlib.sha256(data).hexdigest() != digest:
                        raise ValueError(f'Gateway source differs from release manifest: {name}')
                    write_entry(archive,name,data)
            versions.append(('data-gateway',version,filename))
        sources = []
        for repo,version,filename in versions:
            file = tmp/filename
            with zipfile.ZipFile(file) as archive:
                if not archive.namelist():
                    raise ValueError(f'Empty source archive: {repo}')
                sources.append({'repository':repo,'revision':version,'entries':len(archive.namelist()),
                                'archive':file.name,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
        (tmp/'manifest.json').write_text(json.dumps({'schema':'capstone-debug-sources/1','sources':sources},indent=2)+'\n')
        for name in [item['archive'] for item in sources]+['manifest.json']:
            os.replace(tmp/name,destination/name)
        for old in destination.glob('data-gateway*.zip'):
            if old.name not in {item['archive'] for item in sources}:
                old.unlink()


def install_gateway_release(root, release, library):
    """Publish a complete immutable source directory, including on concurrent imports."""
    digest = json.loads((release/'release.json').read_text())['source_sha256']
    if not isinstance(digest, str) or len(digest) != 64 or any(ch not in '0123456789abcdef' for ch in digest):
        raise ValueError('Invalid gateway release digest')
    install_source(library, digest, lambda candidate: stage(root, [release], candidate, gateway_only=True))


def install_capstone_revision(root, revision, library):
    if len(revision) != 40 or any(ch not in '0123456789abcdef' for ch in revision):
        raise ValueError('An exact Capstone Git revision is required')
    subprocess.run(['git', 'cat-file', '-e', revision + '^{commit}'], cwd=root, check=True)
    install_source(library, revision, lambda candidate: stage(root, [], candidate, capstone_revision=revision))


def install_source(library, digest, build):
    library.mkdir(parents=True, exist_ok=True)
    destination = library/digest
    with tempfile.TemporaryDirectory(dir=library) as temporary:
        candidate = Path(temporary)/'source'
        build(candidate)
        try:
            candidate.rename(destination)
        except OSError as error:
            if error.errno not in (errno.EEXIST, errno.ENOTEMPTY):
                raise
            manifest = (candidate/'manifest.json').read_bytes()
            if (destination/'manifest.json').read_bytes() != manifest:
                raise ValueError('Existing source differs for this revision') from error
            item = json.loads(manifest)['sources'][0]
            with (destination/item['archive']).open('rb') as archive:
                if hashlib.file_digest(archive, 'sha256').hexdigest() != item['sha256']:
                    raise ValueError('Existing source archive failed verification') from error


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--gateway-release',type=Path,action='append')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--install-gateway-source',action='store_true',
                        help='Add a verified release snapshot to the site source directory independently of image builds')
    parser.add_argument('--install-capstone-revision',
                        help='Add the source of an exact Capstone commit to the site source directory')
    args = parser.parse_args()
    if args.install_capstone_revision:
        if args.install_gateway_source or args.gateway_release:
            parser.error('--install-capstone-revision cannot be combined with gateway release options')
        install_capstone_revision(args.root, args.install_capstone_revision, args.output)
        raise SystemExit(0)
    release = args.gateway_release
    if release is None:
        common = subprocess.check_output(['git','rev-parse','--path-format=absolute','--git-common-dir'],
                                         cwd=args.root,text=True).strip()
        current = Path(common).parent.parent/'data-gateway/runtime/integration/service/current.json'
        active = json.loads(current.read_text())
        release = [Path(active['release_path'])]
        if active.get('previous_release_path'):
            release.append(Path(active['previous_release_path']))
    if args.install_gateway_source:
        for item in release:
            install_gateway_release(args.root, item, args.output)
    else:
        stage(args.root,release,args.output)
