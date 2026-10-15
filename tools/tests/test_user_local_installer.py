import hashlib
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / 'deploy/dev-trial/install.sh'


@pytest.fixture
def installation(tmp_path):
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    records = []
    env = {'PATH': str(bindir) + os.pathsep + os.environ['PATH'],
           'TMPDIR': str(tmp_path), 'LC_ALL': 'C'}
    for letter in ['a', 'b']:
        revision = letter * 40
        script = tmp_path / ('installer-' + letter)
        script.write_text("source='" + revision + "'\nprintf 'installed " + revision + "\\n'\n")
        env['INSTALLER_' + letter.upper()] = str(script)
        records.append('\t'.join([revision, 'user-local-' + revision[:7],
            'https://github.com/uukuguy/capstone/releases/download/user-local-' + revision[:7] + '/install.sh',
            hashlib.sha256(script.read_bytes()).hexdigest(), '2026-10-15']))
    catalog = tmp_path / 'versions.tsv'
    catalog.write_text('\n'.join(reversed(records)) + '\n')
    env['CATALOG_FIXTURE'] = str(catalog)
    curl = bindir / 'curl'
    curl.write_text('''#!/bin/sh
set -eu
url= out=
while [ "$#" -gt 0 ]; do
  case "$1" in -o) shift; out=$1 ;; https:*) url=$1 ;; esac
  shift
done
case "$url" in
  */USER-LOCAL-VERSIONS.tsv) cp "$CATALOG_FIXTURE" "$out" ;;
  */user-local-aaaaaaa/install.sh) cp "$INSTALLER_A" "$out" ;;
  */user-local-bbbbbbb/install.sh) cp "$INSTALLER_B" "$out" ;;
  *) exit 22 ;;
esac
''')
    curl.chmod(0o755)
    return env, catalog


def run(env, *args):
    return subprocess.run(['sh', str(INSTALLER), *args], env=env, capture_output=True, text=True)


def test_default_selects_latest_verified_commit(installation):
    result = run(installation[0])
    assert result.returncode == 0
    assert 'installed ' + 'b' * 40 in result.stdout


def test_manager_catalog_mode_never_executes_installer(installation):
    result = run(installation[0], '--catalog')
    assert result.returncode == 0
    assert result.stdout == installation[1].read_text()
    assert 'installed ' not in result.stdout


@pytest.mark.parametrize('revision', ['a' * 7, 'a' * 40])
def test_selects_short_or_full_git_revision(installation, revision):
    result = run(installation[0], revision)
    assert result.returncode == 0
    assert 'installed ' + 'a' * 40 in result.stdout


@pytest.mark.parametrize('args', [('invalid-version',), ('c' * 7,), ('a' * 7, 'extra')])
def test_invalid_selection_lists_available_commits_without_installing(installation, args):
    result = run(installation[0], *args)
    assert result.returncode != 0
    assert 'aaaaaaa' in result.stdout + result.stderr
    assert 'bbbbbbb' in result.stdout + result.stderr
    assert 'installed ' not in result.stdout


def test_rejects_installer_checksum_change(installation):
    env, _ = installation
    Path(env['INSTALLER_A']).write_text("source='" + 'a' * 40 + "'\necho unexpected\n")
    result = run(env, 'a' * 7)
    assert result.returncode != 0
    assert 'unexpected' not in result.stdout


def test_rejects_catalog_source_and_installer_source_mismatch(installation):
    env, catalog = installation
    original = Path(env['INSTALLER_A'])
    old_digest = hashlib.sha256(original.read_bytes()).hexdigest()
    original.write_text("source='" + 'c' * 40 + "'\necho unexpected\n")
    catalog.write_text(catalog.read_text().replace(old_digest, hashlib.sha256(original.read_bytes()).hexdigest()))
    result = run(env, 'a' * 7)
    assert result.returncode != 0
    assert 'unexpected' not in result.stdout


def test_rejects_external_catalog_installer_url(installation):
    env, catalog = installation
    catalog.write_text(catalog.read_text().replace('https://github.com/uukuguy/capstone/', 'https://example.com/'))
    result = run(env)
    assert result.returncode != 0
    assert 'installed ' not in result.stdout


def test_list_does_not_install(installation):
    result = run(installation[0], '--list')
    assert result.returncode == 0
    assert 'a' * 40 in result.stdout and 'b' * 40 in result.stdout
    assert 'installed ' not in result.stdout


@pytest.mark.parametrize('argument', ['SECRET-key-value', 'A' * 7, 'a' * 6, 'a' * 41, ''])
def test_invalid_arguments_are_not_echoed(installation, argument):
    result = run(installation[0], argument)
    assert result.returncode != 0
    if argument == 'SECRET-key-value':
        assert argument not in result.stdout + result.stderr
    assert 'installed ' not in result.stdout


@pytest.mark.parametrize('mutation', ['duplicate', 'version', 'digest', 'date', 'extra', 'empty', 'url'])
def test_rejects_malformed_catalog(installation, mutation):
    env, catalog = installation
    rows = catalog.read_text().splitlines()
    fields = rows[0].split('\t')
    if mutation == 'duplicate':
        rows.append(rows[0])
    elif mutation == 'empty':
        rows = ['# No releases']
    else:
        if mutation == 'version':
            fields[1] = 'user-local-ccccccc'
        elif mutation == 'digest':
            fields[3] = 'g' * 64
        elif mutation == 'date':
            fields[4] = '2026-02-30'
        elif mutation == 'extra':
            fields.append('extra')
        elif mutation == 'url':
            fields[2] += '?token=secret'
        rows[0] = '\t'.join(fields)
    catalog.write_text('\n'.join(rows) + '\n')
    result = run(env)
    assert result.returncode != 0
    assert 'installed ' not in result.stdout


def test_rejects_ambiguous_prefix(installation):
    env, catalog = installation
    rows = catalog.read_text().splitlines()
    fields = rows[0].split('\t')
    fields[0] = 'a' * 7 + 'b' * 33
    fields[1] = 'user-local-' + fields[0][:8]
    fields[2] = 'https://github.com/uukuguy/capstone/releases/download/' + fields[1] + '/install.sh'
    rows[0] = '\t'.join(fields)
    catalog.write_text('\n'.join(rows) + '\n')
    result = run(env, 'a' * 7)
    assert result.returncode != 0
    assert fields[0] in result.stdout + result.stderr
    assert 'installed ' not in result.stdout


def test_catalog_comments_are_allowed(installation):
    env, catalog = installation
    catalog.write_text('# Verified releases\n\n' + catalog.read_text())
    assert run(env).returncode == 0


def test_oversized_catalog_is_rejected(installation):
    env, catalog = installation
    catalog.write_text('#' + 'x' * (1024 * 1024 + 1))
    assert run(env).returncode != 0


def test_oversized_installer_is_rejected(installation):
    env, catalog = installation
    script = Path(env['INSTALLER_B'])
    old_digest = hashlib.sha256(script.read_bytes()).hexdigest()
    script.write_text("source='" + 'b' * 40 + "'\n#" + 'x' * (1024 * 1024) + '\necho unexpected\n')
    catalog.write_text(catalog.read_text().replace(old_digest, hashlib.sha256(script.read_bytes()).hexdigest()))
    result = run(env)
    assert result.returncode != 0
    assert 'unexpected' not in result.stdout


def test_failed_download_does_not_execute(installation):
    env, _ = installation
    Path(env['INSTALLER_B']).unlink()
    result = run(env)
    assert result.returncode != 0
    assert 'installed ' not in result.stdout


@pytest.mark.parametrize('args', [(), ('--list',), ('invalid',)])
def test_removes_only_private_temporary_files(installation, args):
    env, catalog = installation
    sentinel = catalog.parent / 'keep-me'
    sentinel.write_text('user file')
    run(env, *args)
    assert sentinel.read_text() == 'user file'
    assert not list(catalog.parent.glob('capstone-entry.*'))


def test_entry_can_run_from_stdin(installation):
    result = subprocess.run(['sh', '-s', '--', 'a' * 7], input=INSTALLER.read_text(),
                            env=installation[0], capture_output=True, text=True)
    assert result.returncode == 0
    assert 'installed ' + 'a' * 40 in result.stdout


def test_checksum_fallback_to_shasum(installation):
    env, _ = installation
    # Hide sha256sum from command lookup while preserving the host utilities.
    prelude = '''command() {
      if [ "$1" = -v ] && [ "$2" = sha256sum ]; then return 1; fi
      if [ "$1" = -v ] && [ "$2" = shasum ]; then return 0; fi
      return 1
    }
'''
    result = subprocess.run(['/bin/sh', '-s', '--'], input=prelude + INSTALLER.read_text(),
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0
    assert 'installed ' + 'b' * 40 in result.stdout
