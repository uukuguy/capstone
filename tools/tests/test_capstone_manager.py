"""Execute the POSIX manager with isolated packages and a fake Docker daemon."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

MANAGER = Path(__file__).resolve().parents[2] / 'deploy/dev-trial/capstone.sh'
A = 'abcdef0123456789' + '1' * 24
B = 'abcdef0999999999' + '2' * 24
C = 'c' * 40


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'installation'
        self.root.mkdir()
        self.state = self.root / '.capstone-management'
        self.state.mkdir()
        self.bin = Path(self.tmp.name) / 'bin'
        self.bin.mkdir()
        self.db = Path(self.tmp.name) / 'docker.json'
        self.db.write_text(json.dumps({'images': {}, 'running': ['capstone', 'local-demo', 'capstone-user-other-install']}))
        self.env = dict(os.environ, PATH=f'{self.bin}:{os.environ["PATH"]}', HOME=str(Path(self.tmp.name)), FAKE_DB=str(self.db), SECRET_KEY='credential-canary')
        (self.bin / 'docker').write_text('''#!/usr/bin/env python3
import json, os, sys
p=os.environ['FAKE_DB']; d=json.load(open(p)); a=sys.argv[1:]
with open(p+'.args','a') as f: f.write(json.dumps(a)+'\\n')
if a[:2]==['compose','version']: print('fake compose')
elif a[:2]==['image','ls']: print('\\n'.join(sorted(set(i['id'] for i in d['images'].values()))))
elif a[:2]==['image','inspect']:
 i=d['images'].get(a[-1]) or next((i for i in d['images'].values() if i['id']==a[-1]),None)
 if not i: sys.exit(1)
 fmt=a[a.index('--format')+1]
 print(i['source'] if 'revision' in fmt else i['date'] if 'Created' in fmt else 'amd64' if 'Architecture' in fmt else i['id'])
elif a[0]=='run':
 from pathlib import Path
 state=Path(next(v[:-7] for v in a if v.endswith(':/state')))
 manifest=Path(next(v[:-25] for v in a if v.endswith(':/bundle/manifest.json:ro')))
 state.mkdir(parents=True,exist_ok=True)
 if a[-1]=='init' and not (state/'internal.env').exists():
  (state/'internal.env').write_text(''.join(k+'='+'a'*64+'\\n' for k in ('POSTGRES_PASSWORD','S3_ACCESS_KEY','S3_SECRET_KEY','CAPSTONE_OPERATOR_TOKEN')))
 if a[-1]=='record':
  document=json.loads(manifest.read_text()); instance=next(v.split('=',1)[1] for v in a if v.startswith('CAPSTONE_INSTANCE='))
  receipt=dict(source_revision=document['source_revision'],images=document['images'],instance=instance)
  if (state/'installation.json').exists():
   if json.loads((state/'installation.json').read_text())!=receipt: sys.exit(1)
  else: (state/'installation.json').write_text(json.dumps(receipt))
elif a[0]=='compose':
 project=a[a.index('--project-name')+1]; op=a[a.index('-f')+2:]
 if op[0]=='run' and os.environ.get('FAIL_PREFLIGHT'): sys.exit(1)
 if op[0]=='run' and os.environ.get('REQUIRE_PROVIDER_KEY'):
  from pathlib import Path
  public=Path(a[a.index('--env-file')+1]).read_text()
  if 'OPENAI_API_KEY=credential-canary' not in public: sys.exit(1)
 if op[0]=='up':
  if project not in d['running']: d['running'].append(project)
 elif op[0]=='stop': d['running']=[r for r in d['running'] if r!=project]
 elif op[0]=='ps': print('fixture-container' if '-q' in op else 'fixture status')
 elif op[0]=='logs': print('fixture logs')
 json.dump(d,open(p,'w'))
elif a[0]=='inspect': print(next(i['id'] for ref,i in d['images'].items() if '/backend@' in ref))
elif a[:2]==['volume','ls']: print('')
elif a[0]=='ps':
 project=next((v.split('=',2)[-1] for v in a if v.startswith('label=com.docker.compose.project=')), '')
 print('container' if project in d['running'] else '')
else: sys.exit('unsupported fake Docker command: '+str(a))
''')
        (self.bin / 'docker').chmod(0o700)
        (self.root / '.env').write_text('CAPSTONE_APP_PORT=8765\nTOKEN=credential-canary\n')
        self.records = []

    def package(self, sha, date='2026-10-01T00:00:00Z', cached=True):
        p = self.root / 'versions' / sha
        p.mkdir(parents=True)
        images = {k: f'ghcr.io/uukuguy/{k}@sha256:{sha}{"0" * 24}' for k in ('backend', 'app', 'postgres', 'objects')}
        (p / 'manifest.json').write_text(json.dumps({'source_revision': sha, 'images': images}))
        (p / 'release.env').write_text(''.join(f'CAPSTONE_{k.upper()}_IMAGE={v}\n' for k,v in images.items()))
        (p / 'data-contract.env').write_text(f'CAPSTONE_DATA_CONTRACT_VERSION=1\nCAPSTONE_DATA_SOURCE_REVISION={sha}\nCAPSTONE_DATA_FORMAT_SHA256={"f"*64}\n')
        for name in ('compose.yaml', '.env.example', 'README.txt'):
            (p / name).write_text('fixture\n')
        (p / 'start.sh').write_text('''#!/bin/sh
exec docker-runner "$@"
''')
        runner = self.bin / 'docker-runner'
        runner.write_text('''#!/usr/bin/env python3
import json, os, sys
p=os.environ['FAKE_DB']; d=json.load(open(p)); project=os.environ['CAPSTONE_INSTANCE']; op=sys.argv[1]
from pathlib import Path
revision=os.environ['RUNNER_REVISION']
with open(p+'.ops','a') as f: f.write(project+' '+revision[:7]+' '+op+'\\n')
if op=='up':
 if project not in d['running']: d['running'].append(project)
 json.dump(d,open(p,'w'))
 if os.environ.get('HOLD_UP'):
  import time
  from pathlib import Path
  marker=Path(os.environ['HOLD_UP']); marker.write_text('waiting')
  while not marker.with_suffix('.release').exists(): time.sleep(0.02)
 if os.environ.get('FAIL_SHA','') and revision.startswith(os.environ['FAIL_SHA']):
  print('credential-canary'); sys.exit(1)
elif op=='stop':
 if os.environ.get('FAIL_STOP','') and revision.startswith(os.environ['FAIL_STOP']): sys.exit(1)
 d['running']=[r for r in d['running'] if r!=project]; json.dump(d,open(p,'w'))
print('runner '+op)
''')
        runner.chmod(0o700)
        (p/'start.sh').write_text(f'#!/bin/sh\nRUNNER_REVISION={sha} exec docker-runner "$@"\n')
        self.records.append(f'{sha}\tuser-local-{sha[:8]}\thttps://github.com/uukuguy/capstone/releases/download/user-local-{sha[:8]}/install.sh\t'+ '0'*64 +'\t2026-10-01\n')
        (self.state / 'versions.tsv').write_text(''.join(self.records))
        if cached:
            d=json.loads(self.db.read_text())
            for n,ref in images.items(): d['images'][ref]={'id':f'sha256:{sha}-{n}', 'source':sha, 'date':date}
            self.db.write_text(json.dumps(d))
        return p

    def run_manager(self, *args, **env):
        target=self.root / 'capstone.sh'
        if MANAGER.exists(): shutil.copyfile(MANAGER,target)
        return subprocess.run(['sh',str(target),*args],env=dict(self.env,**env),text=True,capture_output=True)

    def running(self): return json.loads(self.db.read_text())['running']
    def test_shared_project_credentials_and_single_active_runner(self):
        a=self.package(A); c=self.package(C)
        self.assertEqual(self.run_manager('start',A).returncode,0)
        project=(self.state/'registered'/A/'project').read_text().strip()
        self.assertEqual(self.run_manager('use',C).returncode,0)
        self.assertEqual((self.state/'registered'/C/'project').read_text().strip(),project)
        self.assertEqual((a/f'.capstone-trial/{project}/internal.env').read_bytes(),
                         (c/f'.capstone-trial/{project}/internal.env').read_bytes())
        for command in ('status','logs'):
            before=self.ops()
            self.assertEqual(self.run_manager(command).returncode,0)
            self.assertEqual(self.ops()[len(before):].splitlines(),[project+' '+C[:7]+' '+command])
        before=self.ops()
        self.assertEqual(self.run_manager('stop').returncode,0)
        self.assertEqual(len(self.ops()[len(before):].splitlines()),1)

    def test_incompatible_or_missing_contract_never_stops_current(self):
        self.package(A); c=self.package(C)
        (c/'data-contract.env').write_text((c/'data-contract.env').read_text().replace('f'*64,'e'*64))
        self.assertEqual(self.run_manager('start',A).returncode,0)
        before=self.ops()
        refused=self.run_manager('use',C)
        self.assertNotEqual(refused.returncode,0)
        self.assertIn('data format differs',refused.stderr)
        self.assertEqual(self.ops(),before)

    def test_preflight_failure_keeps_active_and_receipt(self):
        self.package(A); self.package(C)
        self.assertEqual(self.run_manager('start',A).returncode,0)
        before=self.ops(); marker=(self.state/'data-contract.env').read_bytes()
        r=self.run_manager('use',C,FAIL_PREFLIGHT='1')
        self.assertNotEqual(r.returncode,0)
        self.assertEqual(self.ops(),before)
        self.assertEqual((self.state/'active').read_text().strip(),A)
        self.assertEqual((self.state/'data-contract.env').read_bytes(),marker)
        (self.state/'data-contract.env').unlink(missing_ok=True)
        self.assertNotEqual(self.run_manager('use',A).returncode,0)
        self.assertEqual(self.ops(),before)

    def test_contract_validation_and_binding(self):
        p=self.package(A)
        declaration=(p/'data-contract.env').read_text()
        for invalid in (declaration.replace(A,C),declaration+'EXTRA=1\n',
                        declaration.replace('VERSION=1','VERSION=2'),
                        declaration.replace('f'*64,'f'*63), declaration+declaration):
            (p/'data-contract.env').write_text(invalid)
            self.assertNotEqual(self.run_manager().returncode,0)
            self.assertEqual(self.ops(),'')
        (p/'data-contract.env').write_text(declaration)
        self.assertEqual(self.run_manager().returncode,0)
        (p/'data-contract.env').write_text(declaration.replace('f'*64,'e'*64))
        before=self.ops()
        self.assertNotEqual(self.run_manager('stop').returncode,0)
        self.assertEqual(self.ops(),before)

    def test_missing_provider_key_does_not_stop_current(self):
        self.package(A); self.package(C)
        (self.root/'.env').write_text('OPENAI_API_KEY=credential-canary\n')
        self.assertEqual(self.run_manager('start',A,REQUIRE_PROVIDER_KEY='1').returncode,0)
        before=self.ops()
        (self.root/'.env').write_text('CAPSTONE_PUBLIC_PROVIDER=openai\n')
        self.assertNotEqual(self.run_manager('use',C,REQUIRE_PROVIDER_KEY='1').returncode,0)
        self.assertEqual(self.ops(),before)

    def test_legacy_without_trusted_descriptor_refuses(self):
        p=self.package(A)
        for n in ('compose.yaml','start.sh','.env.example','release.env','manifest.json','README.txt'):
            shutil.copyfile(p/n,self.root/n)
        legacy=self.root/'.capstone-trial/capstone-user-old'
        legacy.mkdir(parents=True)
        (legacy/'installation.json').write_text(json.dumps(dict(source_revision=A,instance='capstone-user-old',images=json.loads((p/'manifest.json').read_text())['images'])))
        (legacy/'internal.env').write_text('PRIVATE=unchanged\n')
        self.assertNotEqual(self.run_manager().returncode,0)
        self.assertEqual(self.ops(),'')
        self.assertEqual((legacy/'internal.env').read_text(),'PRIVATE=unchanged\n')

    def test_legacy_failed_preflight_does_not_publish_markers(self):
        p=self.package(A)
        for n in ('compose.yaml','start.sh','.env.example','release.env','manifest.json','README.txt'):
            shutil.copyfile(p/n,self.root/n)
        (self.state/'legacy-data-contract.env').write_bytes((p/'data-contract.env').read_bytes())
        legacy=self.root/'.capstone-trial/capstone-user-old'
        legacy.mkdir(parents=True)
        (legacy/'installation.json').write_text(json.dumps(dict(source_revision=A,instance='capstone-user-old',images=json.loads((p/'manifest.json').read_text())['images'])))
        (legacy/'internal.env').write_text('PRIVATE=unchanged\n')
        self.assertNotEqual(self.run_manager(FAIL_PREFLIGHT='1').returncode,0)
        self.assertFalse((self.state/'active').exists())
        self.assertFalse((self.state/'data-contract.env').exists())

    def test_original_runner_switch_seeds_receipt_before_existing_data_guard(self):
        a=self.package(A); c=self.package(C)
        for p in (a,c): shutil.copyfile(MANAGER.parent/'start.sh',p/'start.sh')
        self.assertEqual(self.run_manager('start',A).returncode,0)
        project=(self.state/'project').read_text().strip()
        old=(a/f'.capstone-trial/{project}/installation.json').read_bytes()
        r=self.run_manager('use',C)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual((a/f'.capstone-trial/{project}/installation.json').read_bytes(),old)
        self.assertEqual(json.loads((c/f'.capstone-trial/{project}/installation.json').read_text())['source_revision'],C)
        commands=[json.loads(line) for line in Path(str(self.db)+'.args').read_text().splitlines()]
        stop=next(i for i,cmd in enumerate(commands) if cmd[0]=='compose' and cmd[-1]=='stop')
        self.assertTrue(any(cmd[0]=='run' and cmd[-1]=='record' and str((c/'manifest.json').resolve())+':/bundle/manifest.json:ro' in cmd for cmd in commands[:stop]))
    def ops(self):
        p=Path(str(self.db)+'.ops')
        return p.read_text() if p.exists() else ''

    def test_default_starts_newest_cached_not_catalog_first(self):
        self.package(A); self.package(C, '2026-10-12T00:00:00Z'); self.package(B,cached=False)
        r=self.run_manager(); self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn(C[:7],r.stdout); self.assertIn('http://127.0.0.1:8765/',r.stdout)
        self.assertNotIn('<port>',r.stdout); self.assertNotIn('credential-canary',r.stdout+r.stderr)
        self.assertEqual(len([x for x in self.running() if x.startswith('capstone-user-') and x!='capstone-user-other-install']),1)

    def test_explicit_switch_and_unrelated_projects(self):
        self.package(A); self.package(C)
        self.assertEqual(self.run_manager('start',A[:8]).returncode,0)
        r=self.run_manager('switch',C); self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn(A[:7]+' stop',self.ops()); self.assertIn('capstone',self.running()); self.assertIn('local-demo',self.running())
        self.assertIn('capstone-user-other-install',self.running())
        self.assertEqual(self.run_manager('stop').returncode,0)
        self.assertEqual(len(self.running()),3)

    def test_ambiguous_and_unknown_list_choices(self):
        self.package(A); self.package(B)
        for arg in ('abcdef0','../bad','deadbee'):
            r=self.run_manager('start',arg); self.assertNotEqual(r.returncode,0); self.assertIn(A,r.stdout+r.stderr); self.assertIn(B,r.stdout+r.stderr)
        self.assertEqual(self.ops(),'')

    def test_unregistered_and_wrong_revision_are_excluded(self):
        self.package(A); self.package(C,'2026-10-15T00:00:00Z')
        d=json.loads(self.db.read_text())
        for ref,i in d['images'].items():
            if i['source']==C: i['source']='d'*40
        d['images']['capstone-trial-backend:dev']={'id':'dev','source':'e'*40,'date':'2099-01-01'}
        self.db.write_text(json.dumps(d))
        r=self.run_manager(); self.assertEqual(r.returncode,0,r.stderr); self.assertIn(A[:7],r.stdout)

    def test_failure_rolls_back_and_removes_partial_start(self):
        self.package(A); self.package(C)
        self.assertEqual(self.run_manager('start',A).returncode,0)
        r=self.run_manager('use',C,FAIL_SHA=C[:7]); self.assertNotEqual(r.returncode,0)
        self.assertIn(A[:7]+' up',self.ops()); self.assertIn(C[:7]+' stop',self.ops())
        self.assertIn((self.state/'registered'/A/'project').read_text().strip(),self.running())
        self.assertEqual((self.state/'active').read_text().strip(),A)
        self.assertNotIn('credential-canary',r.stdout+r.stderr)

    def test_lock_and_symlinks_refuse(self):
        self.package(A)
        (self.state/'lock').mkdir()
        self.assertNotEqual(self.run_manager().returncode,0); self.assertEqual(self.ops(),'')
        (self.state/'lock').rmdir()
        (self.root/'versions'/A/'.env').symlink_to(self.root/'.env')
        self.assertNotEqual(self.run_manager().returncode,0); self.assertEqual(self.ops(),'')

    def test_registered_legacy_can_stop_after_catalog_retirement(self):
        p=self.package(A)
        for n in ('compose.yaml','start.sh','.env.example','release.env','manifest.json','README.txt'):
            shutil.copyfile(p/n,self.root/n)
        legacy=self.root/'.capstone-trial'/'capstone-user-old'
        legacy.mkdir(parents=True)
        receipt={'source_revision':A,'instance':'capstone-user-old',
                 'images':json.loads((p/'manifest.json').read_text())['images']}
        (legacy/'installation.json').write_text(json.dumps(receipt))
        (legacy/'internal.env').write_text('PRIVATE=old\n')
        (self.state/'legacy-data-contract.env').write_bytes((p/'data-contract.env').read_bytes())
        self.assertEqual(self.run_manager().returncode,0)
        self.package(C)
        (self.state/'versions.tsv').write_text(self.records[-1])
        result=self.run_manager('stop')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn('capstone-user-old',self.running())

    def test_legacy_copy_preserves_bytes_and_mapping(self):
        p=self.package(A)
        for n in ('compose.yaml','start.sh','.env.example','release.env','manifest.json','README.txt'): shutil.copyfile(p/n,self.root/n)
        shutil.rmtree(p)
        legacy=self.root/'.capstone-trial'/'capstone-user-old'
        legacy.mkdir(parents=True)
        manifest=json.loads((self.root/'manifest.json').read_text())
        receipt=json.dumps({'source_revision':A,'instance':'capstone-user-old','images':manifest['images']})+'\n'
        (self.state/'legacy-data-contract.env').write_text(f'CAPSTONE_DATA_CONTRACT_VERSION=1\nCAPSTONE_DATA_SOURCE_REVISION={A}\nCAPSTONE_DATA_FORMAT_SHA256={"f"*64}\n')
        (legacy/'installation.json').write_text(receipt); (legacy/'internal.env').write_text('PRIVATE=original\n')
        original={str(x.relative_to(self.root)):x.read_bytes() for x in self.root.rglob('*') if x.is_file()}
        r=self.run_manager(); self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('capstone-user-old '+A[:7]+' up',self.ops())
        for name,data in original.items(): self.assertEqual((self.root/name).read_bytes(),data)
        self.assertEqual((p/'.capstone-trial/capstone-user-old/installation.json').read_text(),receipt)

    def test_install_does_not_hold_lifecycle_lock(self):
        self.package(A)
        (self.state/'install.sh').write_text('test ! -d "$CAPSTONE_TRIAL_DIRECTORY/.capstone-management/lock"\nprintf "%s\\n" "$1"\n')
        r=self.run_manager('install',A[:8]); self.assertEqual(r.returncode,0,r.stderr); self.assertIn(A[:8],r.stdout)

    def test_metadata_binding_and_secrets(self):
        p=self.package(A)
        r=self.run_manager(); self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual((p/'.env').read_bytes(),(self.root/'.env').read_bytes())
        self.assertNotIn('credential-canary',Path(str(self.db)+'.args').read_text())
        self.assertNotIn('credential-canary',''.join(x.read_text() for x in self.state.rglob('*') if x.is_file()))
        (p/'manifest.json').write_text('{}')
        self.assertNotEqual(self.run_manager().returncode,0)

    def test_unsafe_project_mapping_cannot_stop_other_project(self):
        self.package(A)
        self.assertEqual(self.run_manager().returncode,0)
        record=self.state/'registered'/A/'project'
        record.write_text('capstone-user-other-install\n')
        before=self.ops()
        self.assertNotEqual(self.run_manager('stop').returncode,0)
        self.assertEqual(self.ops(),before)

    def test_missing_one_cached_image_excludes_version(self):
        self.package(A)
        d=json.loads(self.db.read_text())
        del d['images'][next(ref for ref in d['images'] if '/objects@' in ref)]
        self.db.write_text(json.dumps(d))
        r=self.run_manager(); self.assertNotEqual(r.returncode,0); self.assertEqual(self.ops(),'')

    def test_status_and_logs_use_registered_runner(self):
        self.package(A)
        self.assertEqual(self.run_manager().returncode,0)
        r=self.run_manager('status'); self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('runner status',r.stdout)
        self.assertIn('runner logs',self.run_manager('logs').stdout)
        self.assertIn('cached running',self.run_manager('versions').stdout)

    def test_failed_stop_does_not_start_target(self):
        self.package(A); self.package(C)
        self.assertEqual(self.run_manager('start',A).returncode,0)
        r=self.run_manager('use',C,FAIL_STOP=A[:7]); self.assertNotEqual(r.returncode,0)
        self.assertNotIn(C[:7]+' up',self.ops())
        self.assertEqual(self.ops().count(A[:7]+' up'),2)

    def test_failure_logs_redact_inherited_and_env_keys(self):
        self.package(A)
        self.assertNotEqual(self.run_manager(FAIL_SHA=A[:7]).returncode,0)
        for p in (self.state/'logs').glob('*'):
            self.assertNotIn('credential-canary',p.read_text())
            self.assertEqual(p.stat().st_mode & 0o777,0o600)

    def test_conflicting_legacy_instances_refuse(self):
        self.package(A)
        for name in ('capstone-user-one','capstone-user-two'):
            p=self.root/'.capstone-trial'/name
            p.mkdir(parents=True)
            (p/'installation.json').write_text(json.dumps({'instance':name,'source_revision':A}))
            (p/'internal.env').write_text('secret=old\n')
        r=self.run_manager(); self.assertNotEqual(r.returncode,0); self.assertEqual(self.ops(),'')

    def test_symlinked_version_and_private_state_refuse(self):
        p=self.package(A)
        private=p/'.capstone-trial'
        private.symlink_to(self.root,target_is_directory=True)
        self.assertNotEqual(self.run_manager().returncode,0)
        self.assertEqual(self.ops(),'')

    def test_registry_rejects_impossible_date(self):
        self.package(A)
        p=self.state/'versions.tsv'
        p.write_text(p.read_text().replace('2026-10-01','2026-02-30'))
        self.assertNotEqual(self.run_manager().returncode,0)
        self.assertEqual(self.ops(),'')

    def test_registered_retired_version_is_stopped_on_switch(self):
        self.package(A); self.package(C)
        self.assertEqual(self.run_manager('start',A).returncode,0)
        (self.state/'versions.tsv').write_text(self.records[-1])
        r=self.run_manager('start',C); self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual((self.state/'active').read_text().strip(),C)
        self.assertIn(A,self.run_manager('versions').stdout)

    def test_empty_env_keeps_private_diagnostics(self):
        self.package(A)
        (self.root/'.env').write_text('')
        self.assertEqual(self.run_manager().returncode,0)
        r=self.run_manager('logs'); self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('runner logs',r.stdout)

    def test_migrated_runner_may_keep_its_own_receipt_format(self):
        p=self.package(A)
        for n in ('compose.yaml','start.sh','.env.example','release.env','manifest.json','README.txt'): shutil.copyfile(p/n,self.root/n)
        legacy=self.root/'.capstone-trial'/'capstone-user-old'
        legacy.mkdir(parents=True)
        receipt={'source_revision':A,'instance':'capstone-user-old','images':json.loads((p/'manifest.json').read_text())['images']}
        (self.state/'legacy-data-contract.env').write_bytes((p/'data-contract.env').read_bytes())
        (legacy/'installation.json').write_text(json.dumps(receipt))
        (legacy/'internal.env').write_text('PRIVATE=old\n')
        self.assertEqual(self.run_manager().returncode,0)
        # An original runner may rewrite its copy after verifying the same binding.
        (p/'.capstone-trial/capstone-user-old/installation.json').write_text(json.dumps(receipt,indent=2))
        r=self.run_manager('stop'); self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual((legacy/'installation.json').read_text(),json.dumps(receipt))

    def test_original_frozen_shell_runner_with_fake_docker(self):
        p=self.package(A)
        shutil.copyfile(MANAGER.parent/'start.sh',p/'start.sh')
        r=self.run_manager(); self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('User-local ready',r.stdout)
        self.assertNotIn('fixture status',r.stdout)
        commands=[json.loads(line) for line in Path(str(self.db)+'.args').read_text().splitlines()]
        self.assertTrue(any(cmd[0]=='compose' and 'up' in cmd for cmd in commands))
        self.assertNotIn('credential-canary',json.dumps(commands))
        self.assertIn('fixture status',self.run_manager('status').stdout)
        self.assertEqual(self.run_manager('stop').returncode,0)

    def test_incomplete_and_candidate_packages_do_not_displace_cached_release(self):
        self.package(A)
        p=self.package(C,'2026-10-15T00:00:00Z')
        (p/'README.txt').unlink()
        r=self.run_manager(); self.assertEqual(r.returncode,0,r.stderr); self.assertIn(A[:7],r.stdout)
        (p/'README.txt').write_text('fixture\n')
        (p/'release.env').write_text('CAPSTONE_BACKEND_IMAGE=capstone-trial-backend:candidate\n')
        r=self.run_manager(); self.assertEqual(r.returncode,0,r.stderr); self.assertIn(A[:7],r.stdout)

    def test_empty_revision_and_missing_switch_revision_list_choices(self):
        self.package(A)
        for args in (('start',''),('switch',),('use',)):
            r=self.run_manager(*args); self.assertNotEqual(r.returncode,0)
            self.assertIn(A,r.stdout+r.stderr)
        self.assertEqual(self.ops(),'')

    def test_concurrent_start_is_rejected_under_real_shell_lock(self):
        self.package(A); self.package(C)
        shutil.copyfile(MANAGER,self.root/'capstone.sh')
        marker=Path(self.tmp.name)/'barrier'
        first=subprocess.Popen(['sh',str(self.root/'capstone.sh'),'start',A],
            env=dict(self.env,HOLD_UP=str(marker)),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            deadline=time.monotonic()+15
            while not marker.exists() and first.poll() is None and time.monotonic()<deadline: time.sleep(0.02)
            self.assertTrue(marker.exists())
            second=subprocess.run(['sh',str(self.root/'capstone.sh'),'start',C],env=self.env,capture_output=True,text=True)
            self.assertNotEqual(second.returncode,0); self.assertIn('lock',second.stderr)
            self.assertNotIn(C[:7]+' up',self.ops())
        finally:
            marker.with_suffix('.release').touch()
            out,err=first.communicate(timeout=15)
        self.assertEqual(first.returncode,0,err)

    def test_inherited_instance_cannot_target_developer_project(self):
        self.package(A)
        r=self.run_manager(CAPSTONE_INSTANCE='capstone'); self.assertEqual(r.returncode,0,r.stderr)
        self.assertNotIn('\ncapstone ',self.ops())
        self.assertIn('capstone',self.running())


if __name__ == '__main__': unittest.main()
