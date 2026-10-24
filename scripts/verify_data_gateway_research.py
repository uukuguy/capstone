"""Real enterprise task check. Keep receipts; never resubmit an uncertain command."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import uuid

import httpx


PROMPTS = {
    'series': ('通过已授权的数据网关，研究北京电网2024年1月1日00:00至00:05（北京时间）的发电有功。'
        '先探索服务、准确对象、指标和窗口来源，再读取真实采样，计算该窗口有效样本的最小值、最大值和均值。'
        '保留服务返回的单位、时间口径、缺失与质量说明，不把发电有功叫作负荷，不补零或猜测。'
        '保存原始查询结果JSON、采样CSV和一份简短中文研究报告.md，报告附真实来源与适用范围。'
        '如果有多个来源，明确选取并说明；若该窗口确实无数据，如实说明，不扩大为全年研究。'),
    'table': ('通过已授权的数据网关探索北京电网相关的业务对象表与字段，选择一个有明确来源的对象表，'
        '使用语义表查询的预检与执行能力取得不超过5条记录。沿用预检返回的验证指纹，不自行拼接SQL或猜测连接。'
        '保存原始返回JSON与简短的数据目录说明.md，列出实际表、字段、筛选条件和质量限制。'
        '只做这一个有界探索，不生成大报告或电网计算。'),
    'followup': ('继续刚才的研究，复用已保存的真实采样与研究报告，把结论改写成面向管理者的三个要点，'
        '保留时间窗口、单位及数据局限。不要重新扩大取数，也不要把发电有功改称负荷。'
        '保存为管理摘要.md，并说明使用了哪些已保存资料。'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', default='http://127.0.0.1:8767')
    parser.add_argument('--case', choices=PROMPTS, default='series')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--thread-id')
    parser.add_argument('--work-id')
    parser.add_argument('--timeout', type=int, default=900)
    parser.add_argument('--poll-only', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=args.poll_only)

    def save(name, value):
        (args.output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2))

    with httpx.Client(base_url=args.origin, headers={'Capstone-Thread-Version': '2'},
                      trust_env=False, timeout=30) as client:
        def request(method, path, value=None):
            result = client.request(method, path, **({'json': value} if value is not None else {}))
            result.raise_for_status()
            return result.json()

        if args.poll_only:
            command = json.loads((args.output / 'submission.json').read_text())
            receipt = json.loads((args.output / 'receipt.json').read_text())
        else:
            if args.case == 'followup' and (not args.thread_id or not args.work_id):
                raise ValueError('Follow-up requires the exact retained thread and work')
            snapshot = (request('GET', '/api/v1/threads/' + args.thread_id) if args.thread_id else
                        request('POST', '/api/v1/threads', {'session_type': 'enterprise-research'}))
            save('initial-snapshot.json', snapshot)
            thread = snapshot['thread_id']
            target = {'kind': 'work', 'id': 'new', 'expected_revision': 0}
            if args.work_id:
                work = next(w for w in snapshot['works'] if w['work_id'] == args.work_id)
                target = {'kind': 'work', 'id': work['work_id'], 'expected_revision': work['revision']}
            command = {'schema': 'capstone-command/2', 'thread_id': thread, 'run_id': snapshot['run']['run_id'],
                'command_id': 'cmd_' + uuid.uuid4().hex, 'idempotency_key': 'idem_' + uuid.uuid4().hex,
                'kind': 'send_message', 'target': target, 'payload': {'text': PROMPTS[args.case]}}
            save('submission.json', command)
            receipt = request('POST', '/api/v1/threads/' + thread + '/commands', command)
            save('receipt.json', receipt)
        assert receipt['status'] == 'accepted', receipt
        thread, attempt = command['thread_id'], receipt['target']['attempt_id']
        base = '/api/v1/threads/' + thread
        print(json.dumps({'thread_id': thread, 'work_id': receipt['target']['id'],
                          'attempt_id': attempt, 'case': args.case}), flush=True)
        events, cursor, started, reported = [], 0, time.monotonic(), -30
        while True:
            page = request('GET', base + '/events?after=' + str(cursor))
            cursor = page['next_event_seq']
            events.extend(page['events'])
            save('events.json', events)
            own = [e for e in events if e.get('attempt_id') == attempt]
            terminal = next((e for e in own if e['event_type'] in {
                'attempt_completed', 'attempt_failed', 'attempt_cancelled', 'attempt_interrupted'}), None)
            elapsed = time.monotonic() - started
            gateway = [e for e in own if str(e.get('payload', {}).get('tool_name', '')).startswith('data_gateway_')]
            if elapsed - reported >= 25 or terminal:
                print(json.dumps({'seconds': round(elapsed, 1), 'events': len(own),
                    'gateway_events': len(gateway), 'terminal': terminal and terminal['event_type']}), flush=True)
                reported = elapsed
            if terminal:
                break
            if elapsed > args.timeout:
                raise TimeoutError('Task remains observable; resume with --poll-only. No cancellation or resubmission sent.')
            if not page['has_more']:
                time.sleep(2)
        save('terminal.json', terminal)
        save('snapshot.json', request('GET', base))
        artifacts = {}
        for event in own:
            if event['event_type'] == 'native_artifact_published':
                item = event['payload']['artifact']
                artifacts[item['artifact_id']] = item
        products = []
        for artifact_id, item in artifacts.items():
            assert Path(item['file_name']).name == item['file_name']
            assert item['download_url'].startswith('/api/v1/')
            response = client.get(item['download_url'])
            response.raise_for_status()
            assert hashlib.sha256(response.content).hexdigest() == item['sha256']
            folder = args.output / 'products' / artifact_id
            folder.mkdir(parents=True, exist_ok=True)
            (folder / item['file_name']).write_bytes(response.content)
            products.append({'file_name': item['file_name'], 'sha256': item['sha256'], 'bytes': len(response.content)})
        summary = {'thread_id': thread, 'work_id': receipt['target']['id'], 'attempt_id': attempt,
            'terminal': terminal['event_type'], 'observed_seconds': elapsed,
            'gateway_tool_names': sorted({e['payload']['tool_name'] for e in gateway}), 'products': products}
        save('result.json', summary)
        assert terminal['event_type'] == 'attempt_completed', summary
        assert products, 'No persisted product'
        if args.case != 'followup':
            assert gateway, 'No observed production-data tool execution'
        print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
