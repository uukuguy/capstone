"""Run the fixed source-free installer in private temporary installations."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = 'a' * 40


class FixedInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / 'home'
        self.home.mkdir()
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        self.catalog = self.base / 'catalog.tsv'
        self.catalog.write_text('fixture catalog\n')
        self.archive = self.base / 'package.tar.gz'
        files = {name: b'fixture\n' for name in
                 ['compose.yaml', 'start.sh', '.env', '.env.example', 'release.env',
                  'manifest.json', 'README.txt', 'data-contract.env', 'install.sh']}
        files['release.env'] = ''.join(
            f'CAPSTONE_{key}_IMAGE=registry.cn-beijing.aliyuncs.com/uukuguy/capstone-{key.lower()}@sha256:{"b" * 64}\n'
            for key in ['BACKEND', 'APP', 'POSTGRES', 'OBJECTS']).encode()
        files['capstone.sh'] = b'#!/bin/sh\nprintf "manager %s %s\\n" "$1" "$2"\n'
        self.files = files
        self.make_archive()
        (self.bin / 'curl').write_text('#!/bin/sh\nwhile [ "$#" -gt 0 ]; do if [ "$1" = -o ]; then cp "$FIXTURE_ARCHIVE" "$2"; exit; fi; shift; done\nexit 1\n')
        (self.bin / 'docker').write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$DOCKER_CALLS"\n')
        for file in self.bin.iterdir():
            file.chmod(0o700)
        self.env = dict(os.environ, HOME=str(self.home), PATH=f'{self.bin}:{os.environ["PATH"]}',
                        FIXTURE_ARCHIVE=str(self.archive), DOCKER_CALLS=str(self.base / 'calls'),
                        CAPSTONE_INSTALL_CATALOG=str(self.catalog))

    def make_archive(self):
        with tarfile.open(self.archive, 'w:gz') as archive:
            for name, data in self.files.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))

    def run_install(self, checksum=None):
        template = ROOT / 'deploy/dev-trial/install-version.sh'
        self.assertTrue(template.exists(), 'fixed installer template is missing')
        script = template.read_text().replace('@VERSION@', 'user-local-aaaaaaa').replace(
            '@SOURCE_REVISION@', SOURCE).replace('@ARCHIVE_URL@', 'offline' if self.env.get('CAPSTONE_OFFLINE_DIRECTORY') else 'https://github.com/uukuguy/capstone/releases/download/user-local-aaaaaaa/package.tar.gz').replace(
            '@ARCHIVE_SHA256@', checksum or hashlib.sha256(self.archive.read_bytes()).hexdigest())
        installer = self.base / 'install.sh'
        installer.write_text(script)
        return subprocess.run(['sh', str(installer)], env=self.env, text=True, capture_output=True)

    def test_portable_offline_projects_before_repeat_comparison(self):
        kinds = ['backend', 'app', 'postgres', 'objects']
        identities = [{'kind': kind, 'tag': 'capstone-offline-' + kind + ':' + SOURCE,
                       'config_digest': 'sha256:' + str(i) * 64,
                       'manifest_digest': 'sha256:' + str(i + 4) * 64,
                       'platform': 'linux/amd64'} for i, kind in enumerate(kinds)]
        document = {'schema': 'capstone-dev-trial/1', 'channel': 'dev-trial-offline',
                    'source_revision': SOURCE, 'platforms': ['linux/amd64'],
                    'images': {i['kind']: i['config_digest'] for i in identities},
                    'offline_image_identities': identities}
        self.files['manifest.json'] = json.dumps(document).encode()
        self.files['release.env'] = ''.join(f'CAPSTONE_{i["kind"].upper()}_IMAGE={i["config_digest"]}\n'
                                           for i in identities).encode()
        self.make_archive()
        import shutil
        shutil.copyfile(self.archive, self.base / 'deployment.tar.gz')
        selection = self.base / 'selection.tsv'
        selection.write_text(''.join(i['kind'] + '\t' + i['manifest_digest'] + '\n' for i in identities))
        selection.chmod(0o600)
        tag = 'user-local-' + SOURCE[:12]
        self.catalog.write_text(f'{SOURCE}\t{tag}\thttps://github.com/uukuguy/capstone/releases/download/{tag}/install.sh\t' + '0' * 64 + '\t2026-10-15\n')
        self.env.update(CAPSTONE_OFFLINE_DIRECTORY=str(self.base), CAPSTONE_OFFLINE_IMAGE_SELECTION=str(selection),
                        RUNTIME_HELPER=str(ROOT / 'deploy/dev_trial_runtime.py'), TEST_SOURCE=SOURCE)
        (self.bin / 'docker').write_text('#!' + os.sys.executable + '\n' + '''
import importlib.util, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ['DOCKER_CALLS'], 'a') as handle: handle.write(' '.join(args) + '\\n')
if args[:2] == ['image', 'inspect']:
    fmt = args[args.index('--format') + 1]
    print(args[-1] if fmt == '{{.Id}}' else 'linux/amd64' if '.Os' in fmt else os.environ['TEST_SOURCE'])
elif args[0] == 'run':
    assert '--pull' in args and args[args.index('--pull') + 1] == 'never'
    assert args[args.index('--network') + 1] == 'none'
    bundle = Path(next(a[:-8] for a in args if a.endswith(':/bundle')))
    selection = Path(next(a[:-18] for a in args if a.endswith(':/selection.tsv:ro')))
    spec = importlib.util.spec_from_file_location('projection', os.environ['RUNTIME_HELPER'])
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.materialize_offline(bundle.resolve(), selection.resolve())
''')
        for _ in range(2):
            result = self.run_install()
            self.assertEqual(result.returncode, 0, result.stderr)
            installed = self.home / 'capstone' / 'versions' / SOURCE
            self.assertEqual(json.loads((installed / 'manifest.json').read_text())['images'],
                             {i['kind']: i['manifest_digest'] for i in identities})
            self.assertEqual((installed / 'data-contract.env').read_bytes(), self.files['data-contract.env'])

    def test_default_downloads_four_images_and_starts_requested_version(self):
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        root = self.home / 'capstone'
        self.assertTrue((root / 'versions' / SOURCE / 'start.sh').is_file())
        self.assertTrue((root / 'capstone.sh').is_file())
        self.assertIn(f'manager start {SOURCE}', result.stdout)
        self.assertEqual((self.base / 'calls').read_text().count('pull '), 4)
        self.assertIn('4/4', result.stdout)

    def test_optional_markdown_guide_is_installed_at_root_and_repeats(self):
        self.files['README.md'] = b'# User guide\nShared validation cases.\n'
        self.make_archive()
        for _ in range(2):
            result = self.run_install()
            self.assertEqual(result.returncode, 0, result.stderr)
            root = self.home / 'capstone'
            self.assertEqual((root / 'README.md').read_bytes(), self.files['README.md'])
            self.assertEqual((root / 'versions' / SOURCE / 'README.md').read_bytes(), self.files['README.md'])
        (root / 'versions' / SOURCE / 'README.md').write_text('tampered')
        self.assertNotEqual(self.run_install().returncode, 0)

    def test_optional_markdown_guide_does_not_follow_root_symlink(self):
        self.files['README.md'] = b'# User guide\n'
        self.make_archive()
        root = self.home / 'capstone'
        root.mkdir()
        target = self.base / 'user-document'
        target.write_text('preserve')
        (root / 'README.md').symlink_to(target)
        self.assertNotEqual(self.run_install().returncode, 0)
        self.assertEqual(target.read_text(), 'preserve')

    def test_install_keeps_existing_user_config_and_legacy_receipt(self):
        root = self.home / 'capstone'
        state = root / '.capstone-trial' / 'capstone-user-local-dev'
        state.mkdir(parents=True)
        (state / 'installation.json').write_text('original receipt')
        (state / 'internal.env').write_text('private credentials')
        (root / '.env').write_text('CAPSTONE_APP_PORT=29173\n')
        (root / 'start.sh').write_text('old frozen runner')
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((root / '.env').read_text(), 'CAPSTONE_APP_PORT=29173\n')
        self.assertEqual((root / 'start.sh').read_text(), 'old frozen runner')
        self.assertEqual((state / 'installation.json').read_text(), 'original receipt')
        self.assertEqual((state / 'internal.env').read_text(), 'private credentials')
        self.assertNotIn('private credentials', result.stdout + result.stderr)

    def test_checksum_failure_creates_no_installation(self):
        result = self.run_install('0' * 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.home / 'capstone').exists())

    def test_unsafe_archive_is_refused(self):
        self.files['../escape'] = b'unsafe'
        self.make_archive()
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.home / 'escape').exists())

    def test_symlink_destination_is_refused(self):
        elsewhere = self.base / 'elsewhere'
        elsewhere.mkdir()
        (self.home / 'capstone').symlink_to(elsewhere, target_is_directory=True)
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_changed_frozen_package_is_not_overwritten(self):
        self.assertEqual(self.run_install().returncode, 0)
        target = self.home / 'capstone' / 'versions' / SOURCE / 'start.sh'
        target.write_text('changed')
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(target.read_text(), 'changed')

    def test_imported_legacy_version_can_install_management_files(self):
        self.assertEqual(self.run_install().returncode, 0)
        version = self.home / 'capstone' / 'versions' / SOURCE
        for name in ['capstone.sh', 'install.sh']:
            (version / name).unlink()
        runner = (version / 'start.sh').read_bytes()
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((version / 'start.sh').read_bytes(), runner)
        self.assertTrue((version / 'capstone.sh').is_file())
        self.assertTrue((version / 'install.sh').is_file())


if __name__ == '__main__':
    unittest.main()
