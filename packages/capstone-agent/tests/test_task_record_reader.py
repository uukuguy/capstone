import pytest

from capstone_agent.task_record_reader import SelectedTaskRecordReader


class Records:
    def __init__(self):
        self.calls = []

    def read_attempt_records(self, thread_id, attempt_id, *, after, limit):
        self.calls.append((thread_id, attempt_id, after, limit))
        return {
            "schema": "capstone-attempt-records/1", "thread_id": thread_id,
            "attempt_id": attempt_id, "instruction": "Original question",
            "model_context": {"model_id": "network"}, "next_after": 3,
            "has_more": True, "events": [
                {"event_seq": 1, "event_type": "tool_completed", "visibility": "public",
                 "payload": {"ok": False, "failure": "nonconvergence"}},
                {"event_seq": 2, "event_type": "assistant_process_delta", "visibility": "public",
                 "payload": {"text": "Unneeded process text"}},
                {"event_seq": 3, "event_type": "tool_completed", "visibility": "internal",
                 "payload": {"private": "must not reach model"}},
            ],
        }


def test_reader_is_bound_and_keeps_failure_and_scan_cursor():
    records = Records()
    result = SelectedTaskRecordReader(records, "thr_one", "attempt_old").read(after=0, limit=8)
    assert records.calls == [("thr_one", "attempt_old", 0, 8)]
    assert result["events"][0]["payload"]["ok"] is False
    assert len(result["events"]) == 1
    assert result["next_after"] == 3 and result["has_more"] is True
    assert result["historical_only"] is True


@pytest.mark.parametrize("after,limit", [(True, 8), (-1, 8), (0, 129), (0, 0)])
def test_invalid_cursor_does_not_read_store(after, limit):
    records = Records()
    with pytest.raises(ValueError):
        SelectedTaskRecordReader(records, "thr_one", "attempt_old").read(after=after, limit=limit)
    assert records.calls == []


def test_source_identity_mismatch_is_rejected():
    class WrongSource(Records):
        def read_attempt_records(self, *args, **kwargs):
            page = super().read_attempt_records(*args, **kwargs)
            page["attempt_id"] = "attempt_other"
            return page
    with pytest.raises(ValueError, match="identity"):
        SelectedTaskRecordReader(WrongSource(), "thr_one", "attempt_old").read()
