"""Compare the public event order of two downloaded Capstone debug timelines."""
import argparse
import json
from itertools import zip_longest


def events(stream, state=None):
    first = next(stream, 'null')
    try:
        header = json.loads(first)
    except json.JSONDecodeError:
        header = json.loads(first + stream.read())
    if isinstance(header, dict) and header.get('schema') == 'capstone-debug-evidence/1':
        from check_debug_evidence import verify
        verify(header)
        if stream.read().strip():
            raise ValueError('Unexpected content after the investigation')
        if header['capstone'].get('truncated'):
            raise ValueError('A truncated investigation cannot verify the full execution order')
        if state is not None:
            observation = header.get('observation') or {}
            failure = observation.get('first_failure')
            if 'first_failure' in observation:
                state['first_failure'] = None if failure is None else {
                    'type': failure['type'],
                    'position': next((index for index, event in enumerate(header['capstone']['events'], 1)
                                      if event['seq'] == failure['seq']), None),
                }
        yield from header['capstone']['events']
        return
    if not isinstance(header, dict) or header.get('schema') != 'capstone-debug-timeline/1':
        raise ValueError('Unsupported timeline format')
    if not all(isinstance(header.get(key), str) and header[key] for key in ('attempt_id', 'thread_id')):
        raise ValueError('Missing execution identity')
    last = 0
    for number, line in enumerate(stream, 2):
        event = json.loads(line)
        if (not isinstance(event, dict) or type(event.get('seq')) is not int or event['seq'] <= last
                or not isinstance(event.get('type'), str) or not event['type']):
            raise ValueError(f'Invalid event at line {number}')
        last = event['seq']
        yield event


def compare(first, second):
    difference = None
    count = 0
    original_state, candidate_state = {}, {}
    for index, (original, candidate) in enumerate(zip_longest(events(first, original_state),
                                                              events(second, candidate_state)), 1):
        count = index
        if difference is None and (original or {}).get('type') != (candidate or {}).get('type'):
            difference = {'position': index, 'original': original, 'candidate': candidate}
    failure_comparable = all('first_failure' in state for state in (original_state, candidate_state))
    failure_comparison = {'comparable': failure_comparable, 'changed': None}
    if failure_comparable:
        failure_comparison.update(original=original_state['first_failure'], candidate=candidate_state['first_failure'],
                                  changed=original_state['first_failure'] != candidate_state['first_failure'])
    return {'compared_positions': count, 'first_difference': difference,
            'first_failure_comparison': failure_comparison}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original', type=argparse.FileType('r', encoding='utf-8'))
    parser.add_argument('candidate', type=argparse.FileType('r', encoding='utf-8'))
    args = parser.parse_args()
    try:
        comparison = compare(args.original, args.candidate)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(comparison, ensure_ascii=False))
    return int(comparison['first_difference'] is not None or comparison['first_failure_comparison']['changed'] is True)


if __name__ == '__main__':
    raise SystemExit(main())
