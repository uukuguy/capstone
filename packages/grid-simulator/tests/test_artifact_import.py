import json

import pandapower as pp
import pytest
from grid_simulator.evidence import canonical_json, fingerprint, write_json


def provision(root, *, foreign=False, member=None, wrong_map=False, radial=False):
    import io
    import zipfile
    from datetime import datetime, timedelta, timezone
    from grid_simulator.artifact_import import grant_fingerprint

    net = pp.create_empty_network()
    pp.create_bus(net, 110, index=17)
    pp.create_ext_grid(net, 17)
    mapping = {
        "schema": "gateway-element-map/1",
        "engine": "pandapower",
        "engine_version": "3.4.0",
        "artifact_ref": "a" * 64,
        "model_ref": "grid:test",
        "model_revision": "r1",
        "scenario_revision": "s1",
        "covered_element_tables": ["bus", "ext_grid"],
        "elements": [
            {
                "element_table": "bus",
                "element_key": "17" if wrong_map else 17,
                "element_ref": "element:bus",
                "endpoints": [],
            },
            {
                "element_table": "ext_grid",
                "element_key": 0,
                "element_ref": "element:grid",
                "endpoints": [],
            },
        ],
    }
    if radial:
        mapping["covered_element_tables"] += ["line", "load"]
        for index in (18, 19, 20):
            pp.create_bus(net, 110, index=index)
            pp.create_line_from_parameters(
                net, index - 1, index, 1, 0.1, 0.2, 0, 1, index=index
            )
            mapping["elements"] += [
                {
                    "element_table": "bus",
                    "element_key": index,
                    "element_ref": f"element:bus:{index}",
                    "endpoints": [],
                },
                {
                    "element_table": "line",
                    "element_key": index,
                    "element_ref": f"element:line:{index}",
                    "endpoints": [],
                },
            ]
        pp.create_load(net, 20, 1, 0.2)
        mapping["elements"].append(
            {
                "element_table": "load",
                "element_key": 0,
                "element_ref": "element:load:0",
                "endpoints": [],
            }
        )
    contents = {
        "model.pandapower.json": pp.to_json(net),
        "element-map.json": canonical_json(mapping),
        "quality.json": canonical_json(
            {
                "quality": {
                    "demo_only": True,
                    "power_flow_ready": True,
                    "real_power_flow_ready": False,
                }
            }
        ),
        "demo-assumptions.json": "{}",
        "calculation-structure.json": "{}",
        "source-model.json": "{}",
    }
    if member:
        contents[member] = "{}"
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, data in contents.items():
            archive.writestr(name, data)
    payload = stream.getvalue()
    digest = fingerprint(payload)
    grant = {
        "schema": "grid-model-input-grant/1",
        "task_id": "other" if foreign else "task",
        "attempt_id": "attempt",
        "authority": "grid-simulator",
        "artifact_ref": "a" * 64,
        "bundle_sha256": digest,
        "bundle_bytes": len(payload),
        "engine": "pandapower",
        "engine_version": "3.4.0",
        "model_id": "grid:test",
        "model_revision": "r1",
        "scenario_revision": "s1",
        "map_sha256": fingerprint(contents["element-map.json"]),
        "allow_demo": True,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "revoked": False,
    }
    ref = "input:sha256:" + grant_fingerprint(grant)
    grant["input_ref"] = ref
    write_json(
        root / "application-model-input-binding.json",
        {
            "schema": "grid-model-input-binding/1",
            "task_id": "task",
            "attempt_id": "attempt",
            "authority": "grid-simulator",
        },
    )
    write_json(root / "inputs" / "grants" / f"{ref.split(':')[-1]}.json", grant)
    target = root / "inputs" / "objects" / f"{digest}.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return ref, target


def test_import_public_operation_survives_restart_and_map_tamper(grid):
    ref, _ = provision(grid.workspace.root)
    result = grid.call("model.artifact.import", {"input_ref": ref})
    from grid_simulator.models import ContextStore, ModelRegistry, ContextIntegrityError

    store = ContextStore(grid.workspace, ModelRegistry(grid.engine))
    assert store.require(result["context_ref"]).origin == "imported"
    assert list(store.load_network(result["context_ref"]).bus.index) == [17]
    assert grid.call("model.artifact.import", {"input_ref": ref}) == result
    map_path = (
        grid.workspace.root
        / "evidence"
        / "mappings"
        / f"{result['mapping_ref'].split(':')[-1]}.json"
    )
    map_path.write_text("{}")
    with pytest.raises(ContextIntegrityError):
        store.require(result["context_ref"])


def test_declared_small_demo_import_solves_and_ranks_exact_native_keys(grid):
    ref, _ = provision(grid.workspace.root, radial=True)
    imported = grid.call("model.artifact.import", {"input_ref": ref})
    result = grid.call(
        "analysis.powerflow.ac.run", {"context_ref": imported["context_ref"]}
    )
    assert result["converged"] is True
    ranked = grid.call(
        "result.branches.rank",
        {
            "result_ref": result["result_ref"],
            "metric": "loading_percent",
            "direction": "descending",
            "element_kind": "line",
            "limit": 3,
        },
    )
    assert len(ranked["branches"]) == 3
    assert {row["pandapower_index"] for row in ranked["branches"]} == {18, 19, 20}


@pytest.mark.parametrize(
    "kwargs", [{"foreign": True}, {"member": "../bad"}, {"wrong_map": True}]
)
def test_invalid_admission_creates_no_context(grid, kwargs):
    ref, target = provision(grid.workspace.root, **kwargs)
    if kwargs.get("foreign"):
        target.unlink()  # Binding failure must precede content resolution.
    error = grid.call_error("model.artifact.import", {"input_ref": ref})
    assert error.code == "model_import_rejected"
    assert not grid.workspace.contexts_dir.exists()


@pytest.mark.parametrize(
    "mode", ["expired", "revoked", "engine", "digest", "corrupt", "symlink"]
)
def test_reject_invalid_grant_or_storage(grid, mode):
    from grid_simulator.artifact_import import grant_fingerprint

    ref, target = provision(grid.workspace.root)
    path = grid.workspace.root / "inputs" / "grants" / f"{ref.split(':')[-1]}.json"
    grant = json.loads(path.read_text())
    if mode == "expired":
        grant["expires_at"] = "2020-01-01T00:00:00+00:00"
    if mode == "revoked":
        grant["revoked"] = True
    if mode == "engine":
        grant["engine_version"] = "3.3.0"
    if mode == "digest":
        grant["map_sha256"] = "0" * 64
    if mode == "corrupt":
        target.write_bytes(b"corrupt")
    if mode == "symlink":
        actual = target.with_suffix(".real")
        target.rename(actual)
        target.symlink_to(actual)
    ref = "input:sha256:" + grant_fingerprint(grant)
    grant["input_ref"] = ref
    write_json(path.parent / f"{ref.split(':')[-1]}.json", grant)
    assert (
        grid.call_error("model.artifact.import", {"input_ref": ref}).code
        == "model_import_rejected"
    )
    assert not grid.workspace.contexts_dir.exists()


def test_interrupt_persistence_does_not_publish_context(grid, monkeypatch):
    from grid_simulator import artifact_import

    ref, _ = provision(grid.workspace.root)
    original = artifact_import.write_json

    def fail_before_commit(path, document):
        if path.parent == grid.workspace.contexts_dir:
            raise OSError("injected write failure")
        original(path, document)

    monkeypatch.setattr(artifact_import, "write_json", fail_before_commit)
    assert (
        grid.call_error("model.artifact.import", {"input_ref": ref}).code
        == "persist_failed"
    )
    assert not grid.workspace.contexts_dir.exists()


def test_reject_fractional_native_reference_and_boolean_coercion():
    from grid_simulator.artifact_import import decode_network, ModelImportError

    net = pp.create_empty_network()
    pp.create_bus(net, 110)
    document = json.loads(pp.to_json(net))
    table = json.loads(document["_object"]["bus"]["_object"])
    table["data"][0][table["columns"].index("in_service")] = "false"
    document["_object"]["bus"]["_object"] = json.dumps(table)
    with pytest.raises(ModelImportError):
        decode_network(json.dumps(document))


def test_data_only_decoder_preserves_integer_keys():
    from grid_simulator.artifact_import import decode_network

    net = pp.create_empty_network()
    pp.create_bus(net, 110, index=17)
    restored = decode_network(pp.to_json(net))
    assert list(restored.bus.index) == [17]


@pytest.mark.parametrize(
    "attack",
    [
        {"_module": "os", "_class": "system", "_object": "touch /tmp/forbidden"},
        {
            "_module": "pandas.core.frame",
            "_class": "DataFrame",
            "_object": "/tmp/forbidden.json",
        },
    ],
)
def test_data_only_decoder_rejects_external_constructors_and_paths(attack):
    from grid_simulator.artifact_import import decode_network, ModelImportError

    document = json.loads(pp.to_json(pp.create_empty_network()))
    document["_object"]["bus"] = attack
    with pytest.raises(ModelImportError):
        decode_network(json.dumps(document))
