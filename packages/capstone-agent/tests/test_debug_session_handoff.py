from hashlib import sha256
from io import BytesIO
import json
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from capstone_agent.debug_session_handoff import HandoffMember, read_conversation, write_handoff


def test_conversation_freezes_range_and_projects_only_authorized_questions_and_answers():
    def event(seq, kind, payload, visibility='public'):
        return {'thread_id': 'thr_test', 'event_seq': seq, 'event_type': kind, 'event_id': f'evt_{seq}',
                'attempt_id': 'attempt_1', 'occurred_at': '2026-11-26T00:00:00Z',
                'payload': payload, 'visibility': visibility}

    rows = [
        event(2, 'command_accepted', {'kind': 'send_auto', 'payload': {'text': '分析这份输入'},
                                       'attachment_refs': ['resource_1'], 'secret': 'exclude'}),
        event(3, 'runtime_event', {'activity': 'exclude'}),
        event(4, 'attempt_completed', {'answer': '观察结果', 'details': 'exclude'}),
        event(5, 'attempt_delivery_recovered', {'answer': '范围之外'}),
    ]
    cursors = []

    def read_history(thread_id, *, before):
        assert thread_id == 'thr_test'
        cursors.append(before)
        selected = [row for row in rows if row['event_seq'] < before][-1:]
        return {'thread_id': thread_id, 'events': selected, 'has_more': bool(selected and selected[0]['event_seq'] > 2),
                'next_before_event_seq': selected[0]['event_seq'] if selected else before}

    result = list(read_conversation(SimpleNamespace(read_history=read_history), 'thr_test', 2, 4,
                                    may_export_text=lambda event: event['event_seq'] == 2))
    assert cursors == [5, 4, 3]
    assert [(row['event_seq'], row['role']) for row in result] == [(2, 'user'), (4, 'assistant')]
    assert result[0]['text'] == '分析这份输入'
    assert result[0]['attachment_refs'] == ['resource_1']
    assert result[1]['status'] == 'completed'
    assert result[1]['text_status'] == 'withheld'
    assert 'text' not in result[1]
    assert 'exclude' not in str(result)


def test_handoff_manifest_matches_downloaded_members():
    output = BytesIO()
    manifest = write_handoff(
        output,
        thread_id="thr_test",
        start_seq=1,
        through_seq=8,
        members=[HandoffMember("files/report.csv", iter([b"year,value\n", b"2026,5\n"]))],
        gaps=[{"kind": "gateway_receipts", "status": "withheld"}],
        revisions={"capstone": "abc"},
    )
    output.seek(0)
    with ZipFile(output) as archive:
        assert archive.namelist() == ["files/report.csv", "manifest.json"]
        assert json.loads(archive.read("manifest.json")) == manifest
        data = archive.read("files/report.csv")
        assert manifest["members"] == [
            {"path": "files/report.csv", "size": len(data), "sha256": sha256(data).hexdigest()}
        ]
        assert manifest["gaps"] == [{"kind": "gateway_receipts", "status": "withheld"}]


@pytest.mark.parametrize("path", ["manifest.json", "files/../escape", "/escape", "files\\escape"])
def test_handoff_rejects_unsafe_member_path(path):
    with pytest.raises(ValueError, match="handoff member path"):
        write_handoff(
            BytesIO(),
            thread_id="thr_test",
            start_seq=1,
            through_seq=0,
            members=[HandoffMember(path, [b"ignored"])],
            gaps=[],
            revisions={},
        )
