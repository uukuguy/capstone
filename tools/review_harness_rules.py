#!/usr/bin/env python3
"""Compare private validation archives in two explicitly selected Git worktrees."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def source_revision(path: Path, ref: str) -> str:
    def git(*args):
        return subprocess.check_output(['git', '-C', str(path), *args], text=True).strip()

    head = git('rev-parse', 'HEAD')
    expected = git('rev-parse', '--verify', ref + '^{commit}')
    if head != expected or git('status', '--porcelain', '--untracked-files=no'):
        raise ValueError('Worktree must be clean and match its trusted ref')
    return head


RUNNER = r'''
import hashlib,json,sys
from pathlib import Path
from capstone_agent.answer_correction import _table_row_break_rule
from capstone_agent.harness_validation import load_rule_bundle, replay_rule_input, _processor_identity
request=json.load(sys.stdin)
with Path(request['archive']).open('rb') as stream:
    body=stream.read(4_000_001)
if len(body)>4_000_000:
    raise ValueError('Archive exceeds limit')
if hashlib.sha256(body).hexdigest()!=request['digest']:
    raise ValueError('Archive digest mismatch')
archive=json.loads(body)
if archive.get('schema')!='capstone-validation-replay/1':
    raise ValueError('Invalid archive')
source=archive['bundle'].encode() if request['role']=='baseline' else Path(request['rules']).read_bytes()
bundle=load_rule_bundle(source, {'markdown_table_row_breaks':_table_row_break_rule},target=archive['target'])
class Store:
    def get(self,key,limit):
        if len(body)>limit: raise ValueError('Archive exceeds limit')
        return body
if request['role']=='baseline':
    result=replay_rule_input(Store(),request['thread'],request['attempt'],request['digest'],bundle)
else:
    limit=archive.get('answer_limit')
    accept=None if limit is None else lambda value: isinstance(value,str) and bool(value.strip()) and len(value.encode())<=limit
    result=bundle.pipeline().run(archive['input'],observe=lambda _:None,accept_correction=accept)
print(json.dumps({'schema':'capstone-validation-runtime-receipt/1','role':request['role'],
 'revision':request['revision'],'thread_id':request['thread'],'attempt_id':request['attempt'],
 'archive_sha256':request['digest'],'target':bundle.target,'bundle_sha256':bundle.digest,
 'processors':_processor_identity(bundle),'decision':{'status':result.status,'value':result.value}},ensure_ascii=False))
'''


def run_runtime(path, request):
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join(str(path / 'packages' / name / 'src') for name in (
        'capstone-agent', 'capability-agent-kernel', 'capstone-control',
        'capstone-model-capability-spi', 'enterprise-research-domain-pack'))
    result = subprocess.run([sys.executable, '-c', RUNNER], input=json.dumps(request),
                            cwd=path, env=env, capture_output=True, text=True, check=True, timeout=30)
    return json.loads(result.stdout)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    if len(sys.argv) > 1 and sys.argv[1] in ('publish', 'rollback'):
        operation = sys.argv[1]
        p.add_argument('operation', choices=('publish', 'rollback'))
        for name in ('review', 'current', 'desired', 'output'):
            p.add_argument('--' + name, required=True)
        args = p.parse_args()
        from capstone_agent.harness_rule_review import reviewed_rule_bytes
        review = json.loads(Path(args.review).read_text())
        current = Path(args.current).read_bytes()
        desired = Path(args.desired).read_bytes()
        data = reviewed_rule_bytes(review, current=current, desired=desired,
                                   rollback=operation == 'rollback')
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        return
    for name in ('archive', 'archive-sha256', 'thread', 'attempt', 'baseline-worktree',
                 'baseline-ref', 'candidate-worktree', 'candidate-ref', 'candidate-rules', 'output'):
        p.add_argument('--' + name, required=True)
    args = p.parse_args()
    baseline = Path(args.baseline_worktree).resolve()
    candidate = Path(args.candidate_worktree).resolve()
    old_rev = source_revision(baseline, args.baseline_ref)
    new_rev = source_revision(candidate, args.candidate_ref)
    rules = Path(args.candidate_rules).resolve()
    relative = rules.relative_to(candidate)
    if relative.as_posix() != 'packages/capstone-agent/src/capstone_agent/resources/harness-rules.json':
        raise ValueError('Candidate must be the canonical tracked rule bundle')
    subprocess.run(['git', '-C', str(candidate), 'ls-files', '--error-unmatch', str(relative)],
                   check=True, stdout=subprocess.DEVNULL)
    request = {'archive': str(Path(args.archive).resolve()), 'digest': args.archive_sha256,
               'thread': args.thread, 'attempt': args.attempt,
               'rules': str(rules)}
    old = run_runtime(baseline, {**request, 'role': 'baseline', 'revision': old_rev})
    new = run_runtime(candidate, {**request, 'role': 'candidate', 'revision': new_rev})
    from capstone_agent.harness_rule_review import compare_runtime_receipts
    review = compare_runtime_receipts(old, new, trusted_revisions={old_rev, new_rev})
    output = Path(args.output)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(json.dumps(review, ensure_ascii=False, indent=2) + '\n')
    print('Review saved to', output)


if __name__ == '__main__':
    main()
