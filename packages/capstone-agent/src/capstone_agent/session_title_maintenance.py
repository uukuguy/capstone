"""Explicit, resumable operator title maintenance; never called by list/read APIs.

Run in a separate process with DATABASE_URL and backend profile credentials.
Only the explicitly selected profile may receive requests. Other profiles defer.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
from types import SimpleNamespace
from time import monotonic

from .session_title import SessionTitle
from .session_title_summary import request_summary, summary_input, _persist, TitleSummaryFailure
from .workbench_llm_profiles import ProfileRegistry


def maintenance_selection(submission, registry, allowed_profile):
    selected = (submission or {}).get('llm_selection')
    if selected is None:
        selected = registry.freeze(allowed_profile)
    if selected.get('profile_id') != allowed_profile:
        raise ValueError('profile_not_authorized_for_maintenance')
    profile = registry.resolve(selected)
    if profile['network'] == 'direct':
        raise ValueError('intranet_deferred')
    if profile.get('title_request_options') != {'thinking': {'type': 'disabled'}}:
        raise ValueError('nonthinking_options_unavailable')
    return selected


def maintain_one(service, row, registry, allowed_profile, *, request=request_summary):
    title = SessionTitle.from_document(row['session_title'])
    if title.source != 'automatic':
        return {'status': 'skipped', 'reason_code': 'not_automatic'}
    try:
        selection = maintenance_selection(row.get('submission_snapshot'), registry, allowed_profile)
    except ValueError:
        return {'status': 'deferred', 'reason_code': 'profile_unavailable_or_not_authorized'}
    claim = SimpleNamespace(thread_id=row['thread_id'], attempt=SimpleNamespace(attempt_id=row['attempt_id']))
    context = summary_input(service, claim)
    if context is None:
        return {'status': 'deferred', 'reason_code': 'session_changed_or_busy'}
    started = monotonic()
    try:
        text, usage, revision = request(context, selection)
        metadata = {'purpose': 'session_title', 'status': 'completed', 'usage': usage,
            'profile_id': selection['profile_id'], 'title_request_revision': revision,
            'duration_ms': round((monotonic()-started)*1000), 'trigger': 'operator_maintenance'}
        retained = _persist(service, claim, text, metadata, expected_title=title)
        return {**metadata, 'status': 'completed' if retained else 'deferred',
                'reason_code': 'saved' if retained else 'session_changed'}
    except TitleSummaryFailure as error:
        return {'status': 'failed', 'reason_code': error.code, 'usage': error.usage,
                'title_request_revision': error.revision, 'duration_ms': round((monotonic()-started)*1000)}
    except Exception:
        # Failure is recorded by the operator journal; the old name is untouched.
        return {'status': 'failed', 'reason_code': 'title_request_failed',
                'duration_ms': round((monotonic()-started)*1000)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile-id', required=True, help='Explicit profile allowed for maintenance and legacy fallback')
    parser.add_argument('--state-file', type=Path, required=True, help='Private resumable cursor; use a new path for an explicit new pass')
    parser.add_argument('--batch-size', type=int, default=10)
    args = parser.parse_args(argv)
    if not 1 <= args.batch_size <= 50:
        parser.error('batch-size must be 1..50')
    from .thread_service import PostgresThreadService
    registry = ProfileRegistry()
    # Validate authorization/configuration before opening the batch; no request.
    maintenance_selection(None, registry, args.profile_id)
    service = PostgresThreadService(os.environ['DATABASE_URL'])
    state_path = args.state_file
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(state_path)+'.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = json.loads(state_path.read_text()) if state_path.exists() else {'cursor': ''}
        if state.get('profile_id', args.profile_id) != args.profile_id:
            parser.error('state profile differs; use a new state file')
        with service._connect() as connection:
            rows = connection.execute("""SELECT t.thread_id,t.session_title,a.attempt_id,a.submission_snapshot
                FROM capstone_threads t JOIN LATERAL (
                    SELECT e.attempt_id FROM capstone_thread_events e WHERE e.thread_id=t.thread_id
                    AND e.event_type='command_accepted' ORDER BY e.event_seq DESC LIMIT 1
                ) latest ON true JOIN capstone_thread_attempts a ON a.attempt_id=latest.attempt_id
                WHERE t.thread_id>%s AND t.current_attempt IS NULL AND t.session_title->>'source'='automatic'
                AND length(trim(a.instruction))>0 ORDER BY t.thread_id LIMIT %s""",
                (state['cursor'], args.batch_size)).fetchall()
        def record(row, result):
            value = {'schema': 'capstone-title-maintenance/1', 'profile_id': args.profile_id,
                     'cursor': row['thread_id'], 'attempt_id': row['attempt_id'], **result}
            with open(str(state_path)+'.jsonl', 'a') as journal:
                os.chmod(journal.name, 0o600)
                journal.write(json.dumps(value)+'\n'); journal.flush(); os.fsync(journal.fileno())
            temporary = Path(str(state_path)+'.tmp')
            with open(temporary, 'w') as output:
                os.chmod(temporary, 0o600)
                json.dump(value, output); output.flush(); os.fsync(output.fileno())
            temporary.replace(state_path)
        counts = {}
        for row in rows:
            # Advance before request: a process crash never silently replays a call.
            record(row, {'status': 'started'})
            result = maintain_one(service, row, registry, args.profile_id)
            record(row, result)
            counts[result['status']] = counts.get(result['status'], 0)+1
        print(json.dumps({'processed': len(rows), 'statuses': counts, 'more_possible': len(rows) == args.batch_size}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
