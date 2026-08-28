import json
from pathlib import Path

import pytest

from grid_agent.tools.guide import GuideIndex, GuideNotFound


ROOT = Path(__file__).resolve().parents[4]


def test_guide_index_loads_overview_and_reference_documents() -> None:
    guide = GuideIndex.load(ROOT / "skills/grid-static-analysis")

    overview = guide.open("overview")
    topology = guide.open("topology-analysis")

    assert overview.title == "Grid Static Analysis"
    assert "Capability Status" in overview.text
    assert topology.title == "Topology Analysis"
    assert "topology.branch.endpoints.get" in topology.text


def test_guide_index_materializes_current_protocol_and_root(tmp_path: Path) -> None:
    skill_root = ROOT / "skills/grid-static-analysis"
    guide = GuideIndex.load(skill_root)

    payload = json.loads(
        guide.materialize(tmp_path / "guide-index.json").read_text(encoding="utf-8")
    )

    assert payload["protocol"] == "capability-guide-index"
    assert payload["version"] == "1.0"
    assert "overview" in payload["resources"]
    assert all(
        Path(path).is_relative_to(skill_root.resolve())
        for path in payload["resources"].values()
    )


@pytest.mark.parametrize(
    "resource_id",
    [
        "../../.env",
        "references/topology-analysis",
        "topology%2fanalysis",
        "topology%5canalysis",
        "TOPology-analysis",
        "-topology-analysis",
        "unknown-guide",
    ],
)
def test_guide_index_opens_only_published_resources(resource_id: str) -> None:
    guide = GuideIndex.load(ROOT / "skills/grid-static-analysis")

    with pytest.raises(GuideNotFound):
        guide.open(resource_id)
