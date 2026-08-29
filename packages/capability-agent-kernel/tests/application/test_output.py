from __future__ import annotations

import json
import sys

import pytest
from pydantic import ValidationError

from capability_agent import (
    ApplicationConfigurationError,
    ApplicationResult,
    BindingIdentity,
    CoreRunResult,
    FrameworkOutputComposer,
    JsonOutputRenderer,
    ValidatedDomainOutput,
)
from capability_agent.application.output import OutputRenderer


def _core() -> CoreRunResult:
    return CoreRunResult(
        application_id="app",
        application_version="1.0.0",
        run_id="run-1",
        status="completed",
        answer_refs=(),
        report_ref=None,
        diagnostic_refs=(),
    )


def _binding(binding_id: str = "inventory") -> BindingIdentity:
    return BindingIdentity(
        binding_id=binding_id,
        domain_id="inventory-readonly",
        domain_version="1.0.0",
    )


def _domain() -> ValidatedDomainOutput:
    return ValidatedDomainOutput(
        schema="inventory-output/1.0",
        status="completed",
        payload={"completed_count": 2},
    )


def test_framework_output_keeps_core_and_domain_ownership() -> None:
    result = FrameworkOutputComposer().compose(
        core=_core(), bindings=(_binding(),), domains={"inventory": _domain()}
    )

    assert result.core.run_id == "run-1"
    assert result.domains["inventory"].payload == {"completed_count": 2}
    assert result.model_dump(mode="json") == {
        "schema": "capability-agent-output/1.0",
        "core": {
            "application_id": "app",
            "application_version": "1.0.0",
            "run_id": "run-1",
            "status": "completed",
            "answer_refs": [],
            "report_ref": None,
            "diagnostic_refs": [],
        },
        "domains": {
            "inventory": {
                "domain_id": "inventory-readonly",
                "domain_version": "1.0.0",
                "schema": "inventory-output/1.0",
                "status": "completed",
                "payload": {"completed_count": 2},
            }
        },
    }


@pytest.mark.parametrize(
    "domains",
    [{}, {"inventory": _domain(), "extra": _domain()}],
)
def test_framework_output_rejects_missing_or_extra_binding_outputs(domains) -> None:
    with pytest.raises(ApplicationConfigurationError, match="binding outputs"):
        FrameworkOutputComposer().compose(
            core=_core(), bindings=(_binding(),), domains=domains
        )


@pytest.mark.parametrize("reserved", ["core", "domains"])
def test_framework_output_rejects_domain_payload_owning_top_level_sections(
    reserved: str,
) -> None:
    domain = ValidatedDomainOutput(
        schema="inventory-output/1.0",
        status="completed",
        payload={reserved: {}},
    )

    with pytest.raises(ApplicationConfigurationError, match="reserved top-level"):
        FrameworkOutputComposer().compose(
            core=_core(), bindings=(_binding(),), domains={"inventory": domain}
        )


def test_output_models_are_strict_frozen_and_reject_extra_fields() -> None:
    with pytest.raises(ValidationError):
        CoreRunResult(
            application_id="app",
            application_version="1.0.0",
            run_id="run-1",
            status="completed",
            answer_refs=(),
            report_ref=None,
            diagnostic_refs=(),
            undeclared="value",
        )
    with pytest.raises(ValidationError):
        CoreRunResult(
            application_id="app",
            application_version="1.0.0",
            run_id=1,
            status="completed",
            answer_refs=(),
            report_ref=None,
            diagnostic_refs=(),
        )

    result = FrameworkOutputComposer().compose(
        core=_core(), bindings=(_binding(),), domains={"inventory": _domain()}
    )
    with pytest.raises(ValidationError):
        result.schema = "changed"


def test_application_result_domains_reject_replacement_and_mutation() -> None:
    result = FrameworkOutputComposer().compose(
        core=_core(), bindings=(_binding(),), domains={"inventory": _domain()}
    )

    with pytest.raises(TypeError, match="mapping is immutable"):
        result.domains["replacement"] = result.domains["inventory"]
    with pytest.raises(TypeError, match="mapping is immutable"):
        result.domains.clear()


def test_bound_domain_payload_rejects_reserved_key_insertion() -> None:
    result = FrameworkOutputComposer().compose(
        core=_core(), bindings=(_binding(),), domains={"inventory": _domain()}
    )

    with pytest.raises(TypeError, match="mapping is immutable"):
        result.domains["inventory"].payload["core"] = {}


def test_bound_domain_payload_deeply_rejects_nested_mutation() -> None:
    domain = ValidatedDomainOutput(
        schema="inventory-output/1.0",
        status="completed",
        payload={"summary": {"items": [{"count": 1}]}},
    )
    result = FrameworkOutputComposer().compose(
        core=_core(), bindings=(_binding(),), domains={"inventory": domain}
    )
    summary = result.domains["inventory"].payload["summary"]
    items = summary["items"]

    with pytest.raises(TypeError, match="mapping is immutable"):
        summary["extra"] = True
    with pytest.raises(TypeError):
        items[0] = {"count": 2}
    with pytest.raises(TypeError, match="mapping is immutable"):
        items[0]["count"] = 2


def test_composed_payload_is_detached_from_original_input_mutation() -> None:
    original_payload = {"summary": {"items": [{"count": 1}]}}
    domain = ValidatedDomainOutput(
        schema="inventory-output/1.0",
        status="completed",
        payload=original_payload,
    )
    result = FrameworkOutputComposer().compose(
        core=_core(), bindings=(_binding(),), domains={"inventory": domain}
    )

    original_payload["summary"]["items"][0]["count"] = 9
    original_payload["summary"]["items"].append({"count": 2})

    assert result.domains["inventory"].payload == {
        "summary": {"items": ({"count": 1},)}
    }


def test_validated_domain_output_rejects_mutable_sets() -> None:
    mutable_tags = {"new"}

    with pytest.raises(ApplicationConfigurationError, match="JSON value"):
        ValidatedDomainOutput(
            schema="inventory-output/1.0",
            status="completed",
            payload={"tags": mutable_tags},
        )


def test_framework_rejects_bypassed_set_before_and_after_source_mutation() -> None:
    mutable_tags = {"new"}
    domain = ValidatedDomainOutput.model_construct(
        schema="inventory-output/1.0",
        status="completed",
        payload={"tags": mutable_tags},
    )

    with pytest.raises(ApplicationConfigurationError, match="JSON value"):
        FrameworkOutputComposer().compose(
            core=_core(), bindings=(_binding(),), domains={"inventory": domain}
        )

    mutable_tags.add("changed-after-validation")
    with pytest.raises(ApplicationConfigurationError, match="JSON value"):
        FrameworkOutputComposer().compose(
            core=_core(), bindings=(_binding(),), domains={"inventory": domain}
        )


def test_validated_domain_output_detaches_supported_original_values() -> None:
    original_payload = {"summary": {"items": [{"count": 1}]}}
    domain = ValidatedDomainOutput(
        schema="inventory-output/1.0",
        status="completed",
        payload=original_payload,
    )

    original_payload["summary"]["items"][0]["count"] = 9
    original_payload["summary"]["items"].append({"count": 2})
    result = FrameworkOutputComposer().compose(
        core=_core(), bindings=(_binding(),), domains={"inventory": domain}
    )

    assert result.domains["inventory"].payload == {
        "summary": {"items": ({"count": 1},)}
    }


@pytest.mark.parametrize(
    ("unsupported", "message"),
    [
        (b"bytes", "JSON value"),
        (object(), "JSON value"),
        ({1: "non-string key"}, "string keys"),
        (float("nan"), "finite"),
        (float("inf"), "finite"),
        (float("-inf"), "finite"),
    ],
    ids=("bytes", "custom-object", "non-string-key", "nan", "inf", "negative-inf"),
)
def test_validated_domain_output_rejects_unsupported_recursive_json_values(
    unsupported: object, message: str
) -> None:
    with pytest.raises(ApplicationConfigurationError, match=message):
        ValidatedDomainOutput(
            schema="inventory-output/1.0",
            status="completed",
            payload={"nested": {"value": unsupported}},
        )


def test_validated_domain_output_rejects_cyclic_mapping() -> None:
    cyclic: dict[str, object] = {}
    cyclic["self"] = cyclic

    with pytest.raises(ApplicationConfigurationError, match="cycle"):
        ValidatedDomainOutput(
            schema="inventory-output/1.0",
            status="completed",
            payload={"cyclic": cyclic},
        )


def test_validated_domain_output_rejects_cyclic_list() -> None:
    cyclic: list[object] = []
    cyclic.append(cyclic)

    with pytest.raises(ApplicationConfigurationError, match="cycle"):
        ValidatedDomainOutput(
            schema="inventory-output/1.0",
            status="completed",
            payload={"cyclic": cyclic},
        )


@pytest.mark.parametrize("container_kind", ["mapping", "list"])
def test_framework_defensively_rejects_bypassed_cycles(
    container_kind: str,
) -> None:
    if container_kind == "mapping":
        cyclic_mapping: dict[str, object] = {}
        cyclic_mapping["self"] = cyclic_mapping
        cyclic: object = cyclic_mapping
    else:
        cyclic_list: list[object] = []
        cyclic_list.append(cyclic_list)
        cyclic = cyclic_list
    domain = ValidatedDomainOutput.model_construct(
        schema="inventory-output/1.0",
        status="completed",
        payload={"cyclic": cyclic},
    )

    with pytest.raises(ApplicationConfigurationError, match="cycle"):
        FrameworkOutputComposer().compose(
            core=_core(), bindings=(_binding(),), domains={"inventory": domain}
        )


def test_validated_domain_output_accepts_repeated_acyclic_aliases() -> None:
    shared = {"items": [{"count": 1}]}
    original_payload = {"left": shared, "right": shared}

    domain = ValidatedDomainOutput(
        schema="inventory-output/1.0",
        status="completed",
        payload=original_payload,
    )
    shared["items"].append({"count": 2})
    result = FrameworkOutputComposer().compose(
        core=_core(), bindings=(_binding(),), domains={"inventory": domain}
    )

    assert result.domains["inventory"].payload == {
        "left": {"items": ({"count": 1},)},
        "right": {"items": ({"count": 1},)},
    }


def test_validated_domain_output_translates_excessive_nesting() -> None:
    payload: dict[str, object] = {}
    cursor = payload
    for _ in range(sys.getrecursionlimit() + 100):
        nested: dict[str, object] = {}
        cursor["nested"] = nested
        cursor = nested

    with pytest.raises(ApplicationConfigurationError, match="nesting"):
        ValidatedDomainOutput(
            schema="inventory-output/1.0",
            status="completed",
            payload=payload,
        )


def test_json_output_renderer_canonicalizes_the_complete_result() -> None:
    result = FrameworkOutputComposer().compose(
        core=_core(), bindings=(_binding(),), domains={"inventory": _domain()}
    )

    rendered = JsonOutputRenderer().render(result)

    assert rendered.endswith("\n")
    assert json.loads(rendered) == result.model_dump(mode="json")
    assert rendered == json.dumps(
        result.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    assert isinstance(result, ApplicationResult)
    assert OutputRenderer.__module__ == "capability_agent.application.output"
