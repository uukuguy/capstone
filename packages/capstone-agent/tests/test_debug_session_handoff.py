from hashlib import sha256
from io import BytesIO
import json
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from capstone_agent.debug_session_handoff import (
    HandoffMember, import_handoff, read_conversation, read_session_observations, write_handoff, write_session_handoff,
)


def test_session_observations_page_across_attempts_with_frozen_boundary():
    def history(thread, *, before, limit):
        assert limit == 12
        rows = [
            {"thread_id": thread, "event_seq": seq, "attempt_id": f"attempt_{seq}", "visibility": "public",
             "event_type": "attempt_completed", "payload": {"answer": "a" * 650, "secret": "excluded"}}
            for seq in range(1, 4)
        ]
        selected = [row for row in rows if row["event_seq"] < before][-1:]
        seq = selected[0]["event_seq"]
        return {"thread_id": thread, "events": selected, "has_more": seq > 1, "next_before_event_seq": seq}

    service = SimpleNamespace(read_history=history)
    latest = read_session_observations(service, "thr_test", 2)
    earlier = read_session_observations(service, "thr_test", 2, before=latest["next_before"])
    assert latest["events"][0]["attempt_id"] == "attempt_2"
    first = earlier["events"][0]
    assert first["attempt_id"] == "attempt_1"
    assert first["text_truncated"] is True and len(first["text"]) == 600
    assert "secret" not in first
    assert earlier["next_before"] is None
    with pytest.raises(ValueError, match="invalid session observation cursor"):
        read_session_observations(service, "thr_test", 2, before=4)


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


def test_import_validates_members_before_making_files_available(tmp_path):
    source = tmp_path / "source.zip"
    with source.open("wb") as output:
        write_handoff(
            output, thread_id="thr_test", start_seq=1, through_seq=1,
            members=[HandoffMember("files/input.csv", [b"original"])], gaps=[], revisions={},
        )
    target = import_handoff(source, tmp_path, max_uncompressed_bytes=8192)
    assert (target / "files/input.csv").read_bytes() == b"original"
    with ZipFile(source) as original:
        manifest = original.read("manifest.json")
    with ZipFile(source, "w") as changed:
        changed.writestr("manifest.json", manifest)
        changed.writestr("files/input.csv", b"modified")
    with pytest.raises(ValueError, match="member digest mismatch"):
        import_handoff(source, tmp_path, max_uncompressed_bytes=8192)
    assert list(tmp_path.glob("capstone-debug-*")) == [target.parent]
    assert not list(tmp_path.glob(".capstone-import-*"))
    with pytest.raises(ValueError, match="import size limit"):
        import_handoff(source, tmp_path, max_uncompressed_bytes=8)


def test_session_handoff_exports_exact_delivery_revisions(monkeypatch):
    from capstone_agent import thread_deliveries

    rows = [
        {
            "event_type": "delivery_published", "event_seq": version, "thread_id": "thr_test",
            "visibility": "public", "payload": {"delivery": {"artifact_id": "art_abc", "revision": version,
                                                            "file_name": "report.md"}},
        }
        for version in (1, 2, 3)
    ]
    service = SimpleNamespace(read_history=lambda thread, before: {
        "thread_id": thread, "has_more": False, "events": [row for row in rows if row["event_seq"] < before],
    })

    def read_delivery(actual_service, objects, thread_id, ref, version):
        assert (actual_service, thread_id, ref) == (service, "thr_test", "art_abc")
        if version == 2:
            raise FileNotFoundError()
        return b"original"

    monkeypatch.setattr(thread_deliveries, "read_delivery_content", read_delivery)
    output = BytesIO()
    manifest = write_session_handoff(
        output, service, "thr_test", 2, uploads=None, objects=object(), capstone_revision=None,
    )
    with ZipFile(output) as archive:
        assert archive.read("files/deliveries/art_abc/r1") == b"original"
        assert "files/deliveries/art_abc/r2" not in archive.namelist()
        assert "files/deliveries/art_abc/r3" not in archive.namelist()
        assert json.loads(archive.read("files/index.jsonl")) == {
            "path": "files/deliveries/art_abc/r1", "file_name": "report.md", "revision": 1,
            "artifact_id": "art_abc", "attempt_id": None, "capstone_event_seqs": [1],
        }
    assert {
        "kind": "produced_file", "status": "unavailable", "artifact_id": "art_abc",
        "attempt_id": None, "revision": 2,
    } in manifest["gaps"]


def test_missing_attachment_chunk_preserves_other_session_evidence():
    ref = "resource_" + "a" * 32
    event = {"event_type": "command_accepted", "event_seq": 1, "thread_id": "thr_test",
             "visibility": "public", "payload": {"kind": "send_auto", "text": "Read the input",
             "attachment_refs": [ref], "attachment_versions": {ref: 2}}}
    service = SimpleNamespace(read_history=lambda thread, before: {
        "thread_id": thread, "has_more": False, "events": [event],
    })

    def chunks(thread, resource, *, version):
        assert (thread, resource, version) == ("thr_test", ref, 2)
        yield b"first"
        raise FileNotFoundError()

    uploads = SimpleNamespace(read=chunks, published=lambda *_args, **_kwargs: {})
    output = BytesIO()
    manifest = write_session_handoff(output, service, "thr_test", 1, uploads=uploads, capstone_revision=None)
    assert {"kind": "input_file", "status": "unavailable", "resource_id": ref, "version": 2} in manifest["gaps"]
    with ZipFile(output) as archive:
        assert archive.testzip() is None
        assert b"Read the input" in archive.read("conversation.jsonl")
        assert all(not path.startswith("files/inputs/") for path in archive.namelist())


def test_package_correlates_gateway_calls_with_capstone_events_without_exporting_operation():
    common = {"thread_id": "thr_test", "visibility": "public", "attempt_id": "attempt_test"}
    rows = [
        {**common, "event_seq": 3, "event_type": "runtime_event", "payload": {
            "native_type": "tool_execution_start", "task_id": "private-task", "tool_call_id": "private-call"}},
        {**common, "event_seq": 4, "event_type": "runtime_event", "payload": {
            "native_type": "tool_execution_end", "task_id": "private-task", "tool_call_id": "private-call",
            "is_error": True, "tool_name": "private-operation"}},
        {**common, "event_seq": 5, "event_type": "attempt_completed", "payload": {"answer": "Done"}},
    ]
    service = SimpleNamespace(read_history=lambda thread, before: {
        "thread_id": thread, "has_more": False, "events": rows,
    })
    def read_calls(attempts):
        assert attempts == ["attempt_test"]
        return {"status": "available", "truncated": False, "events": [
            {"entry": 1, "attempt_id": "attempt_test", "status": "available", "_operation": "private-task:private-call"},
        ]}
    output = BytesIO()
    write_session_handoff(output, service, "thr_test", 5, uploads=None, capstone_revision=None,
                          read_gateway_calls=read_calls)
    with ZipFile(output) as archive:
        evidence = archive.read("execution/data-gateway/original-calls.json")
        assert b"private-call" not in evidence
        linked, = json.loads(evidence)["events"]
        assert linked["capstone_event_seqs"] == [3, 4] and linked["correlation_status"] == "linked"
        execution = archive.read("execution/capstone/events.jsonl")
        assert b"private-operation" not in execution
        start, end, _ = [json.loads(line) for line in execution.splitlines()]
        assert start["native_stage"] == "tool_execution_start"
        assert end["native_stage"] == "tool_execution_end" and end["is_error"] is True
