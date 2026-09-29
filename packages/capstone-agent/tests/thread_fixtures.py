from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from capstone_agent.thread_protocol import EventPage, ThreadSnapshot


_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "thread-ui"


def load_fixture(name: str) -> dict[str, Any]:
    path = _FIXTURE_ROOT / f"{name}.json"
    with path.open(encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict) or document.get("fixture_id") != name:
        raise ValueError(f"fixture identity is invalid: {name}")
    snapshot = ThreadSnapshot.from_document(document["snapshot"])
    event_page = EventPage.from_document(
        document["events"], expected_after_seq=snapshot.last_event_seq
    )
    document["snapshot"] = snapshot
    document["event_page"] = event_page
    return document
