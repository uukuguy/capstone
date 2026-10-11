"""Resolve grid requirements and prove conclusions using current-run Authority facts."""
from __future__ import annotations

import json
import math
from collections.abc import Mapping

from capability_agent.domain.task import ResolvedTaskGoal, TaskConclusion
from pandapower_domain.authority import SimulatorIntegrityError
from pandapower_domain.execution import SimulatorCapabilityError

SCHEMA = "pandapower-task-requirement/1"
_KINDS = {"bus", "load", "line", "trafo", "trafo3w", "gen", "sgen", "ext_grid", "network"}
_BRANCHES = {"line", "trafo", "trafo3w"}
_OPERATIONS = {"overview", "powerflow", "limits", "contingency", "ranking", "compare"}
_MEASURES = {None, "loading_percent", "p_from_mw", "p_to_mw", "pl_mw", "risk_score", "max_loading_percent"}
_CONTINGENCY_CHECKS = {"line_overload", "bus_voltage_low", "bus_voltage_high", "non_convergence"}
_SELECTOR_SCHEMA = {"type": "object", "additionalProperties": False,
    "required": ["kind", "namespace", "identifier"], "properties": {
        "kind": {"enum": sorted(_KINDS)},
        "namespace": {"enum": ["name", "alias", "pandapower_index", "asset_ref", "all"]},
        "identifier": {"type": "string", "minLength": 1, "maxLength": 512}},
    "if": {"properties": {"namespace": {"const": "all"}}},
    "then": {"properties": {"identifier": {"const": "*"}}}}
_PAYLOAD_SCHEMA = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
    "additionalProperties": False, "required": ["operation", "objects", "changes", "measure", "direction", "scenario", "scope"],
    "properties": {
        "operation": {"enum": sorted(_OPERATIONS)}, "objects": {"type": "array", "maxItems": 64, "items": _SELECTOR_SCHEMA},
        "changes": {"type": "array", "maxItems": 16, "items": {"type": "object", "additionalProperties": False,
            "required": ["target", "fields", "factor"], "properties": {
                "target": {**_SELECTOR_SCHEMA,
                    "description": "A bus selector identifies the connection point: scale its connected loads. A load selector identifies an individual load device itself. Preserve the kind of the user-identified anchor; its attached devices need not have that identifier.",
                    "properties": {**_SELECTOR_SCHEMA["properties"], "kind": {"enum": ["bus", "load"]}}},
                "fields": {"type": "array", "uniqueItems": True, "items": {"enum": ["p_mw", "q_mvar"]},
                           "description": "Empty means proportional scaling of the whole load, preserving its power factor. Explicit components restrict scaling to those components."},
                "factor": {"type": "number", "exclusiveMinimum": 0, "maximum": 100}}}},
        "measure": {"enum": sorted(item for item in _MEASURES if item is not None) + [None]},
        "direction": {"enum": [None, "ascending", "descending"]},
        "scenario": {"enum": ["baseline", "changed", "contingency", "comparison"]},
        "scope": {"enum": ["subset", "full"]}}}


class _ResolutionScopeExceeded(ValueError):
    pass


def _display_limit(requirement):
    return {"concise": 1, "standard": 5, "detailed": 20}[requirement.get("answer_policy", {}).get("scale", "standard")]


def _whole_network(requirement):
    return requirement["scope"] == "full" and requirement["objects"] == [
        {"kind": "network", "namespace": "all", "identifier": "*"}]


def _display_note(requirement, count):
    limit = _display_limit(requirement)
    return f" Shown: {min(limit, count)} of {count} verified entries; full values are in the result view." if count > limit else ""


def _fields(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError("grid task requirement fields are invalid")


def _selector(value):
    _fields(value, {"kind", "namespace", "identifier"})
    if value["kind"] not in _KINDS or value["namespace"] not in {"name", "alias", "pandapower_index", "asset_ref", "all"}:
        raise ValueError("grid task selector is invalid")
    if not isinstance(value["identifier"], str) or not 1 <= len(value["identifier"]) <= 512:
        raise ValueError("grid task identifier is invalid")
    if value["namespace"] == "all" and value["identifier"] != "*":
        raise ValueError("full grid task selector is invalid")


def _decode(payload):
    # Resolve business semantics in the Pack, before freezing Authority patches.
    # Never mutate the recognizer's original proposal.
    payload = json.loads(json.dumps(payload, allow_nan=False))
    _fields(payload, {"operation", "objects", "changes", "measure", "direction", "scenario", "scope"})
    if (payload["operation"] not in _OPERATIONS or payload["measure"] not in _MEASURES
        or payload["direction"] not in {None, "ascending", "descending"}
        or payload["scenario"] not in {"baseline", "changed", "contingency", "comparison"}
        or payload["scope"] not in {"subset", "full"}):
        raise ValueError("grid task requirement choice is invalid")
    if not isinstance(payload["objects"], list) or len(payload["objects"]) > 64:
        raise ValueError("grid task objects are invalid")
    for item in payload["objects"]:
        _selector(item)
    if not isinstance(payload["changes"], list) or len(payload["changes"]) > 16:
        raise ValueError("grid task changes are invalid")
    for change in payload["changes"]:
        _fields(change, {"target", "fields", "factor"})
        _selector(change["target"])
        if change["target"]["kind"] not in {"bus", "load"}:
            raise ValueError("grid load change target is invalid")
        fields = change["fields"]
        if (not isinstance(fields, list) or len(set(fields)) != len(fields)
            or not set(fields) <= {"p_mw", "q_mvar"}):
            raise ValueError("grid load change fields are invalid")
        if not fields:
            change["fields"] = ["p_mw", "q_mvar"]
        factor = change["factor"]
        if type(factor) not in {int, float} or not math.isfinite(factor) or not 0 < factor <= 100:
            raise ValueError("grid load change factor is invalid")
    return json.loads(json.dumps(payload, allow_nan=False))


def _overview_metadata(value, context_ref, revision_ref):
    _fields(value, {"context_ref", "revision_ref", "model", "counts"})
    if (value["context_ref"] != context_ref or value["revision_ref"] != revision_ref
        or not isinstance(value["model"], str) or not 1 <= len(value["model"]) <= 128):
        raise ValueError("overview metadata is not bound to the selected model revision")
    _fields(value["counts"], {"buses", "lines", "transformers"})
    if any(type(count) is not int or count < 0 for count in value["counts"].values()):
        raise ValueError("overview metadata counts are invalid")
    return json.loads(json.dumps(value, allow_nan=False))


class PandapowerTaskProvider:
    schema = SCHEMA

    def validate_semantic_binding(self, task, *, semantic_goal, answer_policy):
        requirement = task.requirement
        if (requirement.get("semantic_goal") != semantic_goal or requirement.get("answer_policy") != answer_policy):
            raise ValueError("Pack requirement lost its accepted semantic goal binding")

    def render_conclusion(self, conclusion, *, language, scale):
        from .task_language import localize
        if scale not in {"concise", "standard", "detailed"}:
            raise ValueError("unsupported answer scale")
        text = conclusion.text
        if scale == "detailed" and conclusion.result_refs:
            text += f" Verification basis: {len(conclusion.result_refs)} admitted results and {len(conclusion.evidence_refs)} evidence records for this goal."
        return localize(text, language)

    def required_capabilities(self, payload):
        req = _decode(payload)
        if req["operation"] == "overview":
            return ("context.get",)
        result = ["analysis.contingency.n_minus_one.run"] if req["scenario"] == "contingency" else ["analysis.powerflow.ac.run"]
        if req["operation"] == "limits" or req["measure"] == "risk_score":
            result.append("analysis.result.violations.evaluate")
        if req["measure"] == "risk_score":
            result.append("analysis.result.risk.rank")
        if req["changes"]:
            result.append("model.revision.derive")
        return tuple(result)
    schema_document: Mapping[str, object] = {
        "schema": SCHEMA,
        "recognition_projection": {"scope": "scope", "scenario": "scenario", "measure": "measure"},
        "recognition_constraints": {"type": "object", "allOf": [
            {"if": {"properties": {"domain_request": {"properties": {"payload": {
                "properties": {"operation": {"const": operation}}, "required": ["operation"]}}}}},
             "then": {"properties": {"conclusion": {"enum": conclusions}}}}
            for operation, conclusions in {
                "overview": ["description"], "powerflow": ["description", "impact"],
                "limits": ["limit"], "contingency": ["impact", "limit"],
                "compare": ["comparison"], "ranking": ["ranking"]}.items()] + [
            {"if": {"properties": {"domain_request": {"properties": {"payload": {
                "properties": {"operation": {"const": "limits"}}, "required": ["operation"]}}}}},
             "then": {"properties": {"domain_request": {"properties": {"payload": {
                "properties": {"objects": {"maxItems": 0}, "measure": {"type": "null"}}}}}}}},
            {"if": {"properties": {"domain_request": {"properties": {"payload": {
                "properties": {"operation": {"enum": ["powerflow", "compare"]}}, "required": ["operation"]}}}}},
             "then": {"properties": {"domain_request": {"properties": {"payload": {"anyOf": [
                {"properties": {"objects": {"maxItems": 0}, "measure": {"type": "null"}}},
                {"properties": {"objects": {"const": [{"kind": "network", "namespace": "all", "identifier": "*"}]},
                                "scope": {"const": "full"}, "measure": {"type": "null"}}},
                {"properties": {"objects": {"minItems": 1, "items": {"properties": {
                    "kind": {"enum": sorted(_BRANCHES)}}}}, "measure": {
                    "enum": ["loading_percent", "p_from_mw", "p_to_mw", "pl_mw"]}}}
             ]}}}}}},
            {"if": {"properties": {"domain_request": {"properties": {"payload": {
                "properties": {"operation": {"const": "contingency"}}, "required": ["operation"]}}}}},
             "then": {"properties": {"domain_request": {"properties": {"payload": {
                "properties": {"measure": {"type": "null"}}}}}}}}
        ]},
        "load_scaling_contract": {
            "whole_load": "Proportional change of a load scales both active and reactive power by the same factor, preserving power factor. An unqualified load multiplier requests this whole-load operation.",
            "whole_load_fields": [],
            "resolved_whole_load_fields": ["p_mw", "q_mvar"],
            "explicit_components": "Respect explicitly requested active-only or reactive-only changes. An explicit unresolved alternative requires clarification. Never supply a missing target or multiplier.",
        },
        "payload_schema": _PAYLOAD_SCHEMA,
        "payload_fields": {"operation": sorted(_OPERATIONS), "objects": [{"kind": sorted(_KINDS),
            "namespace": ["name", "alias", "pandapower_index", "asset_ref", "all"], "identifier": "exact user identifier; * only for all"}],
            "changes": [{"target": "same object selector, bus or load", "fields": ["p_mw", "q_mvar"], "factor": "positive finite multiplier"}],
            "measure": sorted(item for item in _MEASURES if item is not None) + [None],
            "direction": [None, "ascending", "descending"], "scenario": ["baseline", "changed", "contingency", "comparison"],
            "scope": ["subset", "full"]},
        "rules": "Use all exact fields. Goal scenario/scope/measure/conclusion must agree with the payload; use the same canonical measure identifier in both. Never convert a bus name into an index. Preserve unresolved user identifiers for Authority resolution; internal namespace labels are not business questions for the user. Empty changes for baseline. Preserve the requested subject; the selected Pack resolves capability availability from its registered contracts. Overview covers both current-model basic facts and registered analysis capabilities; it needs no calculation, object scope or ordering, so use direction=null. Other non-ranking operations may also use direction=null. Ranking requires an ordering direction grounded in the meaning of the user request, a measure and accepted scope; the user need not write a machine enum literal; unspecified scope cannot become exhaustive. Scope describes the selected input object set: a single outage is subset even when its constraints cover the network. Contingency constraint evaluation uses measure=null; the evaluated constraints include branch loading and bus voltages. Existing model constraints are the default for limit checks; do not demand a user threshold unless the user requests a different standard. For limits, use objects=[] and measure=null; load-change targets are complete selector objects inside changes.target, never a string or a second measurement object. Topology endpoint and other object-query operations are outside this typed execution schema; use the published professional compatibility schema rather than overview for those operations. No caller context or result refs. Verified answer languages: en and zh; other languages require clarification.",
    }

    def resolve(self, goal_id, payload, *, context_ref, revision_ref, invoke, semantic_goal=None, answer_policy=None):
        requirement = _decode(payload)
        if semantic_goal is not None:
            requirement["semantic_goal"] = json.loads(json.dumps(semantic_goal, allow_nan=False))
        requirement["answer_policy"] = dict(answer_policy or {"language": "en", "scale": "standard"})
        requirement.update(context_ref=context_ref, revision_ref=revision_ref, patches=[], targets=[],
                           required_capabilities=list(self.required_capabilities(payload)))
        def resolved(status, reason=""):
            document = json.dumps(requirement, ensure_ascii=False, allow_nan=False)
            if len(document.encode()) > 32768:
                requirement.update(targets=[], patches=[])
                document = json.dumps(requirement, ensure_ascii=False, allow_nan=False)
                status, reason = "unsupported", "The requested object set exceeds the bounded task resolution limit. Select a smaller explicit scope."
            return ResolvedTaskGoal(goal_id, status, document, reason,
                                    execution_required=status == "ready" and requirement["operation"] != "overview")
        language = requirement["answer_policy"]["language"]
        if language.split("-")[0] not in {"en", "zh"}:
            return resolved("clarification", f"Requested answer language '{language}' is not supported by this Pack's verified renderer. Select English or Chinese.")
        if semantic_goal is not None:
            operations = {"description": {"overview", "powerflow"}, "impact": {"powerflow", "contingency"},
                          "limit": {"limits", "contingency"}, "comparison": {"compare"}, "ranking": {"ranking"}}
            scenario = semantic_goal.get("scenario")
            valid_scenario = scenario == requirement["scenario"] or (scenario == "none" and requirement["operation"] == "overview")
            informational = (requirement["operation"] == "overview" and not requirement["changes"]
                             and (not requirement["objects"] or _whole_network(requirement)))
            valid_scope = semantic_goal.get("scope") == requirement["scope"] or (informational and semantic_goal.get("scope") == "unspecified")
            if (semantic_goal.get("id") != goal_id or not valid_scenario
                or not valid_scope
                or semantic_goal.get("measure") != requirement["measure"]
                or requirement["operation"] not in operations.get(semantic_goal.get("conclusion"), set())
                or (scenario == "baseline" and semantic_goal.get("change") is not None)):
                return resolved("clarification", "The proposed operation, scenario, scope or measure contradicts the accepted goal. Clarify the requirements before execution.")
        if requirement["scenario"] == "contingency" and any(item["kind"] not in _BRANCHES for item in requirement["objects"]):
            return resolved("unsupported", "Generator and other non-branch N−1 outages are not supported by the registered contingency capability. Select line or transformer outages to request an alternative.")
        if requirement["operation"] == "ranking" and requirement["direction"] is None:
            return resolved("clarification", "Specify the requested ranking direction: ascending or descending.")
        if requirement["operation"] == "overview":
            if (requirement["scenario"] != "baseline" or requirement["changes"]
                or requirement["objects"] and not _whole_network(requirement) or requirement["measure"] is not None):
                return resolved("clarification", "A capability overview cannot answer object, measurement or change requirements. Select the requested analysis operation.")
            requirement["model_metadata"] = _overview_metadata(invoke("context.get", {"context_ref": context_ref}),
                                                              context_ref, revision_ref)
            return resolved("ready")
        if requirement["operation"] in {"powerflow", "compare"}:
            element_query = bool(requirement["objects"]) and not _whole_network(requirement)
            if element_query != (requirement["measure"] is not None):
                return resolved("clarification", "Specify both the exact objects and their requested measure, or request the whole-scenario convergence and losses without object measurements.")
            if requirement["measure"] is not None and (requirement["measure"] not in {"loading_percent", "p_from_mw", "p_to_mw", "pl_mw"}
                    or any(item["kind"] not in _BRANCHES for item in requirement["objects"])):
                return resolved("clarification", "This measurement contract covers branch loading and active power values. Other registered analyses can use the explicitly unverified compatibility path.")
        if requirement["operation"] == "limits" and (requirement["objects"] or requirement["measure"] is not None):
            return resolved("clarification", "This constraint contract evaluates the whole scenario. Object-specific limit or measurement requirements need their own explicit coverage contract.")
        if requirement["operation"] == "contingency" and requirement["measure"] is not None:
            return resolved("clarification", "Contingency coverage reports evaluated violations and convergence. Request explicit scenario ranking for max_loading_percent values.")
        if requirement["operation"] == "ranking" and ((requirement["scenario"] == "contingency") != (requirement["measure"] == "max_loading_percent")):
            return resolved("clarification", "Outage scenario ranking requires max_loading_percent; branch operating and violation-risk measures require a baseline or changed-load scenario.")
        if requirement["scope"] == "full" and any(item["namespace"] != "all" for item in requirement["objects"]):
            return resolved("clarification", "Full scope requires an explicit complete element kind, not individual selectors.")
        if ((requirement["operation"] == "contingency" and requirement["scenario"] != "contingency")
            or (requirement["scenario"] == "contingency" and requirement["operation"] not in {"contingency", "ranking"})
            or (requirement["operation"] == "compare") != (requirement["scenario"] == "comparison")):
            return resolved("clarification", "The requested operation and scenario do not match. Specify the intended calculation and scenario.")
        if requirement["operation"] == "ranking" and requirement["measure"] is None:
            return resolved("clarification", "Specify the ranking measure and the exact requested objects.")
        risk = requirement["operation"] == "ranking" and requirement["measure"] == "risk_score"
        if risk and not (requirement["objects"] == [{"kind": "network", "namespace": "all", "identifier": "*"}]):
            return resolved("clarification", "Risk ranking orders all sourced violations, not every grid element. Select the full network violation scope.")
        if requirement["operation"] == "ranking" and not risk and any(item["kind"] not in _BRANCHES for item in requirement["objects"]):
            return resolved("unsupported", "This ranking contract covers branch operating measures. Select a branch set and measure; generator, bus, and violation-risk rankings need a distinct contract.")
        if requirement["scenario"] in {"changed", "comparison"} and not requirement["changes"]:
            return resolved("clarification", "Specify the load targets and requested change factors.")
        if requirement["scenario"] == "baseline" and requirement["changes"]:
            return resolved("clarification", "Confirm whether the requested result is for the baseline or the changed load scenario.")
        if requirement["scenario"] == "contingency" and requirement["changes"]:
            return resolved("clarification", "Changed-load contingency composition requires a separate explicit scenario contract. Confirm the intended sequence before execution.")
        if requirement["operation"] in {"contingency", "ranking"} and not requirement["objects"]:
            return resolved("clarification", "Specify the requested objects or an explicit full element kind.")
        try:
            for selector in requirement["objects"]:
                if selector["kind"] == "network":
                    continue
                requirement["targets"].extend(_resolve_selector(selector, context_ref, revision_ref, invoke))
            for change in requirement["changes"]:
                target = change["target"]
                selected = _resolve_selector(target, context_ref, revision_ref, invoke)
                if target["kind"] == "bus":
                    buses = [row["index"] for row in selected]
                    selected = _query_rows("load", context_ref, revision_ref, invoke,
                                           filters=[{"field": "bus", "operator": "in", "value": buses}])
                indices = sorted({row["index"] for row in selected})
                if not indices:
                    return resolved("clarification", "No load rows match the requested target. Select a bus with load or explicit load objects.")
                requirement["patches"].append({"operation": "scale", "kind": "load", "selector": {"indices": indices},
                                                "fields": change["fields"], "factor": change["factor"]})
        except _ResolutionScopeExceeded:
            requirement.update(targets=[], patches=[])
            return resolved("unsupported", "The requested object set exceeds the bounded task resolution limit. Select a smaller explicit scope.")
        except SimulatorCapabilityError as error:
            if error.error.get("code") not in {"unknown_element", "ambiguous_element", "unknown_element_kind", "unsupported_dataset"}:
                raise
            return resolved("clarification", "The requested object is missing or ambiguous. Supply its exact name, alias, or explicit index.")
        if len({item["asset_ref"] for item in requirement["targets"]}) != len(requirement["targets"]):
            return resolved("clarification", "Requested object selectors overlap. Supply a unique object set.")
        if requirement["operation"] in {"contingency", "ranking"} and not risk and not requirement["targets"]:
            return resolved("clarification", "The requested object set is empty.")
        return resolved("ready")

    def conclude(self, task, *, authority, result_refs, evidence_refs):
        req = task.requirement
        def conclusion(status, text, results=(), evidence=(), context=None, revision=None):
            return TaskConclusion(task.goal_id, status, text, tuple(results), tuple(evidence),
                context or req.get("context_ref", ""), revision or req.get("revision_ref", ""), req.get("scenario", ""))
        if task.status != "ready":
            return conclusion(task.status if task.status in {"unsupported", "clarification"} else "unresolved", task.reason)
        if req["operation"] == "overview":
            if "model_metadata" not in req:
                return conclusion("unresolved", "The saved overview has no selected-model metadata. Submit a new request to describe the current model.")
            metadata = _overview_metadata(req["model_metadata"], req["context_ref"], req["revision_ref"])
            counts = metadata["counts"]
            text = (f"Selected model {metadata['model']}: {counts['buses']} buses, {counts['lines']} lines, "
                    f"{counts['transformers']} transformers. "
                    "The selected pandapower model supports registered model queries, AC power flow, load revision, evaluated limit checks, and line or transformer N−1 analysis. No calculation was requested or needed.")
            if req.get("answer_policy", {}).get("scale", "standard") != "concise":
                text = ("## Grid overview\n\n"
                    f"Selected model {metadata['model']}: {counts['buses']} buses, {counts['lines']} lines, "
                    f"{counts['transformers']} transformers. \n\n"
                    "This is a pandapower static network model. Buses represent connection points; lines and transformers connect those points. Operating values depend on the selected model revision and calculated scenario.\n\n"
                    "## Available analyses\n\n"
                    "- Model queries: inspect equipment, connections and model parameters.\n"
                    "- AC power flow: calculate bus voltages, branch loading and active power losses, with convergence status.\n"
                    "- Load changes: create a derived scenario and recalculate its operating state while preserving the original revision.\n"
                    "- Limit evaluation: assess bus voltages and branch loading against available model limits; identify the affected equipment, values and limits.\n"
                    "- Line or transformer N−1: evaluate individual branch outages, convergence and constraint violations, and order the supported impacts.\n\n"
                    "Choose an analysis and identify the equipment or change of interest. Calculated conclusions will use that task's admitted results and evidence. This introduction does not establish that the present operating point meets its limits.")
            return conclusion("supported", text)
        # Every passed reference is checked, including references irrelevant to this goal.
        documents = {ref: authority.verify_result(ref).document for ref in result_refs}
        evidence = {ref: authority.verify_evidence(ref).document for ref in evidence_refs}
        matching = {}
        for ref, doc in documents.items():
            context = doc.get("context_ref")
            if not isinstance(context, str):
                raise SimulatorIntegrityError("result has no context")
            if context == req["context_ref"]:
                if doc.get("revision_ref") != req["revision_ref"]:
                    raise SimulatorIntegrityError("result revision does not match selected context")
                matches = not req["patches"]
            else:
                patches = authority.verify_context_changes(context, req["context_ref"])
                matches = bool(req["patches"]) and list(patches) == req["patches"]
            if matches:
                matching[ref] = doc
        if req["operation"] == "contingency" or req["operation"] == "ranking" and req["scenario"] == "contingency":
            return self._contingency(req, matching, evidence, authority, conclusion)
        if req["operation"] == "ranking":
            return self._ranking(req, matching, evidence, conclusion)
        if req["operation"] == "compare":
            base = [(ref, doc) for ref, doc in documents.items() if doc.get("context_ref") == req["context_ref"]
                    and doc.get("revision_ref") == req["revision_ref"] and _powerflow(doc) and _support(ref, doc, evidence)]
            changed = [(ref, doc) for ref, doc in matching.items() if _powerflow(doc) and _support(ref, doc, evidence)]
            if len(base) == 1 and len(changed) == 1:
                base_ref, baseline = base[0]
                changed_ref, candidate = changed[0]
                if req["measure"] is not None:
                    return self._compare_measure(req, base_ref, baseline, changed_ref, candidate, evidence, conclusion)
                before, after = _active_loss(baseline), _active_loss(candidate)
                if _finite(before) and _finite(after):
                    refs = tuple(dict.fromkeys(_support(base_ref, baseline, evidence) + _support(changed_ref, candidate, evidence)))
                    return conclusion("supported", f"Baseline AC power flow converged with total active loss {before:.6g} MW; the exact changed-load scenario converged with total active loss {after:.6g} MW. Limit compliance requires evaluated constraints for both scenarios.",
                                      (base_ref, changed_ref), refs, candidate["context_ref"], candidate["revision_ref"])
        if req["operation"] == "limits":
            for ref, doc in matching.items():
                if doc.get("operation") != "constraints.violations":
                    continue
                meta = doc.get("metadata", {})
                source = meta.get("source_result_ref")
                if source not in matching or not _powerflow(matching[source]):
                    continue
                refs = _support(ref, doc, evidence)
                if not refs:
                    continue
                missing = meta.get("unavailable_quantities", [])
                count = meta.get("violation_count")
                if type(count) is not int:
                    continue
                rows = doc.get("datasets", {}).get("result.res_violation", {}).get("rows", [])
                if not isinstance(rows, list) or len(rows) != count:
                    raise SimulatorIntegrityError("violation detail count is inconsistent")
                text = f"The requested scenario has {count} evaluated limit violations."
                details, complete = _violation_details(rows, matching[source])
                text += details
                if missing:
                    text += " Limits were not evaluated for: " + ", ".join(str(item) for item in missing) + "."
                elif count == 0:
                    text += " No violations were found for the defined, evaluated constraints; this does not certify undefined limits."
                return conclusion("partial" if missing or not complete else "supported", text, (ref, source), refs,
                                  doc["context_ref"], doc["revision_ref"])
        elif req["operation"] == "powerflow":
            for ref, doc in matching.items():
                refs = _support(ref, doc, evidence)
                if _powerflow(doc) and refs:
                    if req["measure"] is not None:
                        values = self._measurement_values(req, doc)
                        if values is None:
                            continue
                        text = f"The requested {req['measure']} values cover all {len(values)} resolved branches. "
                        text += "; ".join(f"{kind} {index}: {value:.6g}" for (kind, index), value in sorted(values.items())[:_display_limit(req)]) + "."
                        text += _display_note(req, len(values))
                        return conclusion("supported", text, (ref,), refs, doc["context_ref"], doc["revision_ref"])
                    text = "The requested " + ("changed-load" if req["patches"] else "baseline") + " AC power flow converged."
                    loss = _active_loss(doc)
                    if _finite(loss):
                        text += f" Total active loss is {loss:.6g} MW."
                    text += " Limit compliance requires a separate evaluated constraint result."
                    return conclusion("supported", text, (ref,), refs, doc["context_ref"], doc["revision_ref"])
            for ref, diagnostic in evidence.items():
                if (diagnostic.get("evidence_type") != "powerflow_non_convergence"
                    or diagnostic.get("capability_id") != "analysis.powerflow.ac.run"
                    or diagnostic.get("diagnostic") != "pandapower.LoadflowNotConverged"):
                    continue
                context = diagnostic.get("context_ref")
                revision = diagnostic.get("revision_ref")
                if not isinstance(context, str) or not isinstance(revision, str):
                    raise SimulatorIntegrityError("powerflow diagnostic has no model identity")
                if context == req["context_ref"]:
                    matches = revision == req["revision_ref"] and not req["patches"]
                else:
                    verified_context = authority.verify_context(context).document
                    if verified_context.get("revision_ref") != revision:
                        raise SimulatorIntegrityError("powerflow diagnostic revision is inconsistent")
                    patches = authority.verify_context_changes(context, req["context_ref"])
                    matches = bool(req["patches"]) and list(patches) == req["patches"]
                if matches:
                    return conclusion("partial", "The requested AC power flow did not converge. The verified diagnostic provides no valid numerical operating result; loading and limit compliance cannot be concluded.",
                                      evidence=(ref,), context=context, revision=revision)
        return conclusion("unresolved", "No admitted result proves the requested operation on the exact scenario. Run that operation with the resolved objects and changes.")

    def _measurement_values(self, req, document):
        requested = {(row["kind"], row["index"]): row["asset_ref"] for row in req["targets"]}
        rows = [row for row in document.get("branch_results", []) if (row.get("element_kind"), row.get("pandapower_index")) in requested]
        identities = [(row.get("element_kind"), row.get("pandapower_index")) for row in rows]
        if (not requested or len(set(identities)) != len(identities) or set(identities) != set(requested)
                or not all(_finite(row.get(req["measure"])) for row in rows)
                or (document.get("context_ref") == req["context_ref"] and any(row.get("asset_ref") != requested[key] for key, row in zip(identities, rows)))):
            return None
        return {key: row[req["measure"]] for key, row in zip(identities, rows)}

    def _compare_measure(self, req, base_ref, baseline, changed_ref, candidate, evidence, conclusion):
        targets = {(row["kind"], row["index"]) for row in req["targets"]}
        before, after = self._measurement_values(req, baseline), self._measurement_values(req, candidate)
        if before is None or after is None:
            return conclusion("unresolved", "The paired comparison lacks a valid requested measure for every resolved object.")
        entries = "; ".join(f"{kind} {index}: {before[kind,index]:.6g} → {after[kind,index]:.6g}" for kind, index in sorted(targets)[:_display_limit(req)])
        entries += _display_note(req, len(targets))
        refs = tuple(dict.fromkeys(_support(base_ref, baseline, evidence) + _support(changed_ref, candidate, evidence)))
        return conclusion("supported", f"Baseline → changed {req['measure']} values cover all {len(targets)} requested branches. {entries}.",
                          (base_ref, changed_ref), refs, candidate["context_ref"], candidate["revision_ref"])

    def authorizes_context(self, task, authority, context_ref, revision_ref):
        req = task.requirement
        document = authority.verify_context(context_ref).document
        if document.get("revision_ref") != revision_ref:
            return False
        if context_ref == req.get("context_ref"):
            return revision_ref == req.get("revision_ref")
        return bool(req.get("patches")) and list(authority.verify_context_changes(context_ref, req["context_ref"])) == req["patches"]

    def _contingency(self, req, documents, evidence, authority, conclusion):
        requested = {row["asset_ref"] for row in req["targets"]}
        targets = {row["asset_ref"]: row for row in req["targets"]}
        covered = {}
        checked = {}
        used_results, used_evidence = [], []
        # Prefer a complete candidate per outage; do not combine independent
        # filtered evaluations into a claimed complete certificate.
        ordered = sorted(documents.items(), key=lambda item: len(item[1].get("violation_types", []))
                         if isinstance(item[1].get("violation_types"), list) else 0, reverse=True)
        for ref, doc in ordered:
            if doc.get("result_type") != "analysis.contingency.n_minus_one.aggregate":
                continue
            # AC subsets are useful evidence, but cannot establish full coverage.
            violation_types = doc.get("violation_types")
            if (doc.get("solver", {}).get("operation") != "pandapower.runpp"
                or not isinstance(violation_types, list)
                or not all(isinstance(item, str) for item in violation_types)
                or not violation_types or not set(violation_types) <= _CONTINGENCY_CHECKS):
                continue
            scenarios = doc.get("scenarios")
            if not isinstance(scenarios, list) or type(doc.get("scenario_count")) is not int or doc.get("scenario_count") != len(scenarios):
                raise SimulatorIntegrityError("contingency count is inconsistent")
            if any(row.get("branch_ref") not in requested for row in scenarios):
                continue
            if len({row.get("branch_ref") for row in scenarios}) != len(scenarios):
                raise SimulatorIntegrityError("duplicate contingency coverage")
            selected = False
            for ordinal, row in enumerate(scenarios):
                branch = row.get("branch_ref")
                if branch not in requested:
                    continue
                if branch in covered:
                    continue
                child_ref, ev_ref = row.get("scenario_result_ref"), row.get("evidence_ref")
                child = authority.verify_result(child_ref).document
                ev = authority.verify_evidence(ev_ref).document
                outage = child.get("outage", {})
                if (child.get("context_ref") != doc.get("context_ref") or child.get("revision_ref") != doc.get("revision_ref")
                    or ev.get("context_ref") != doc.get("context_ref") or ev.get("revision_ref") != doc.get("revision_ref")
                    or ev.get("subject_ref") != branch or outage.get("branch_ref", outage.get("asset_ref")) != branch
                    or child.get("scenario_index") != ordinal or row.get("status") != child.get("status")
                    or row.get("element_kind") != targets[branch]["kind"] or row.get("pandapower_index") != targets[branch]["index"]
                    or outage.get("kind") != targets[branch]["kind"] or outage.get("index") != targets[branch]["index"]
                    or ev.get("capability_id") != "analysis.contingency.n_minus_one.run"
                    or ev_ref not in doc.get("evidence_refs", []) or ev_ref not in evidence):
                    raise SimulatorIntegrityError("contingency child identity is inconsistent")
                converged = row.get("converged")
                if converged is True:
                    if (child.get("operation") != "contingency.n_minus_one.scenario" or child.get("status") != "succeeded"
                        or ev.get("result_ref") != child_ref or child.get("converged") is not True
                        or ev.get("evidence_type") != "contingency_scenario"):
                        raise SimulatorIntegrityError("successful contingency schema is inconsistent")
                elif converged is False:
                    if (child.get("result_type") != "analysis.contingency.n_minus_one.scenario" or child.get("status") != "non_converged"
                        or ev.get("evidence_type") != "powerflow_non_convergence" or child.get("converged") is not False
                        or child.get("evidence_ref") != ev_ref):
                        raise SimulatorIntegrityError("non-converged contingency schema is inconsistent")
                else:
                    raise SimulatorIntegrityError("contingency convergence status is missing")
                if row.get("violations") != child.get("violations"):
                    raise SimulatorIntegrityError("contingency violation link is inconsistent")
                covered[branch] = child
                checked[branch] = set(violation_types)
                used_evidence.append(ev_ref)
                selected = True
            if selected:
                used_results.append(ref)
        if not covered:
            return conclusion("unresolved", "No admitted outage result covers the requested branch set. Run the resolved N−1 cases.")
        failed = sum(doc.get("converged") is False for doc in covered.values())
        violations = sum(len(doc.get("violations", [])) for doc in covered.values() if doc.get("converged") is True)
        missing_limits = any(doc.get("constraint_evaluation", {}).get("status") != "evaluated"
                             for doc in covered.values() if doc.get("converged") is True)
        text = f"Executed {len(covered)} of {len(requested)} requested branch outages. {violations} evaluated limit violations were found; {failed} cases did not converge."
        missing_checks = set().union(*(_CONTINGENCY_CHECKS - scope for scope in checked.values()))
        if missing_checks:
            text += " Some required constraint checks are not covered by retained evidence: " + ", ".join(sorted(missing_checks)) + "."
        details_complete = True
        remaining_details = 20
        for branch, child in covered.items():
            if child.get("converged") is not True:
                continue
            rows = child.get("violations", [])
            details, complete = _violation_details(rows, child, limit=remaining_details)
            remaining_details = max(0, remaining_details - len(rows))
            if details:
                target = targets[branch]
                text += f" Outage {target['kind']} index {target['index']}:" + details
            details_complete = details_complete and complete
        if failed:
            text += " Non-converged cases have no valid numerical operating result."
        if missing_limits:
            text += " Some model limits are undefined or were not evaluated."
        if set(covered) != requested:
            text += " Execute the remaining requested outages before claiming full coverage."
        ranking_complete = True
        if req["operation"] == "ranking":
            if req["measure"] != "max_loading_percent":
                return conclusion("partial", text + " The requested measure is not an available outage scalar ordering.", used_results, tuple(dict.fromkeys(used_evidence)))
            scalar_cases = [(branch, doc["max_loading_percent"]) for branch, doc in covered.items()
                            if doc.get("converged") is True and _finite(doc.get("max_loading_percent"))]
            scalar_cases.sort(key=lambda row: (row[1], row[0]), reverse=req["direction"] == "descending")
            ranking_complete = set(covered) == requested and len(scalar_cases) == len(requested)
            labels = {row["asset_ref"]: f"{row['kind']} {row['index']}" for row in req["targets"]}
            if ranking_complete:
                text += f" Complete Pack ordering by max_loading_percent ({req['direction']}): "
            else:
                text += f" Partial Pack ordering: {len(scalar_cases)} of {len(requested)} cases have valid max_loading_percent values. "
            text += "; ".join(f"{labels[branch]}: {value:.6g}%" for branch, value in scalar_cases[:_display_limit(req)]) + "." + _display_note(req, len(scalar_cases))
            text += " This is an ordering of verified scenario scalars, not a separate Authority ranking result."
        return conclusion("supported" if set(covered) == requested and not failed and not missing_limits and not missing_checks and ranking_complete and details_complete else "partial",
                          text, used_results, tuple(dict.fromkeys(used_evidence)))

    def _ranking(self, req, documents, evidence, conclusion):
        # The original powerflow result does not record ranking invocation arguments.
        # Build a Pack ordering only when its persisted rows cover the exact resolved set.
        if req["measure"] == "risk_score":
            return self._risk_ranking(req, documents, evidence, conclusion)
        if req["scenario"] == "contingency" or req["measure"] == "max_loading_percent":
            return conclusion("unresolved", "The requested ranking needs a matching complete ranking dataset and its source scenario. Branch loading is not outage or violation-risk ranking.")
        requested = {(row["kind"], row["index"]): row["asset_ref"] for row in req["targets"]}
        for ref, doc in documents.items():
            if not _powerflow(doc):
                continue
            refs = _support(ref, doc, evidence)
            rows = doc.get("branch_results", [])
            selected = [row for row in rows if (row.get("element_kind"), row.get("pandapower_index")) in requested]
            identities = [(row.get("element_kind"), row.get("pandapower_index")) for row in selected]
            if (not refs or len(set(identities)) != len(identities) or set(identities) != set(requested)
                or (doc.get("context_ref") == req["context_ref"] and any(row.get("asset_ref") != requested[key] for key, row in zip(identities, selected)))
                or not all(_finite(row.get(req["measure"])) for row in selected)):
                continue
            selected.sort(key=lambda row: (row[req["measure"]], row.get("asset_ref", row.get("branch_ref"))), reverse=req["direction"] == "descending")
            display = "; ".join(f"{row['element_kind']} {row['pandapower_index']}: {row[req['measure']]:.6g}" for row in selected[:_display_limit(req)])
            display += _display_note(req, len(selected))
            return conclusion("supported", f"The {req['direction']} {req['measure']} ordering covers all {len(requested)} requested branches. First entries: {display}.", (ref,), refs,
                              doc["context_ref"], doc["revision_ref"])
        return conclusion("unresolved", "A complete ranking is not supported: requested objects or valid values for the selected measure are missing. Retrieve the full requested result scope.")

    def _risk_ranking(self, req, documents, evidence, conclusion):
        for ref, doc in documents.items():
            if doc.get("operation") != "risk.rank":
                continue
            source_ref = doc.get("metadata", {}).get("source_result_ref")
            source = documents.get(source_ref, {})
            base_ref = source.get("metadata", {}).get("source_result_ref")
            if source.get("operation") != "constraints.violations" or base_ref not in documents or not _powerflow(documents[base_ref]):
                continue
            rows = doc.get("datasets", {}).get("result.res_risk", {}).get("rows", [])
            violations = source.get("datasets", {}).get("result.res_violation", {}).get("rows", [])
            refs = _support(ref, doc, evidence)
            if (not refs or doc.get("metadata", {}).get("ranked_count") != len(rows) or len(rows) != len(violations)
                or not all(_finite(row.get("risk_score")) for row in rows)):
                continue
            def identity(row):
                return json.dumps({key: value for key, value in row.items() if key not in {"index", "rank", "risk_score"}}, sort_keys=True, allow_nan=False)
            if sorted(identity(row) for row in rows) != sorted(identity(row) for row in violations):
                raise SimulatorIntegrityError("risk rows do not cover their exact source violations")
            ordered = sorted(rows, key=lambda row: (row["risk_score"], row.get("asset_ref", "")), reverse=req["direction"] == "descending")
            missing = source.get("metadata", {}).get("unavailable_quantities", [])
            text = f"The {req['direction']} risk_score ordering covers all {len(rows)} sourced violations. Scores prioritize normalized exceedance with the recorded severity weights; they are not probabilities or scores for every grid element."
            if ordered:
                labels = {row["asset_ref"]: f"{dataset.removeprefix('result.res_')} {row['index']}"
                          for dataset, data in documents[base_ref].get("datasets", {}).items()
                          for row in data.get("rows", []) if isinstance(row.get("asset_ref"), str) and "index" in row}
                text += " First scores: " + "; ".join(f"{labels.get(row.get('asset_ref'), row.get('kind', 'violation'))}: {row['risk_score']:.6g}" for row in ordered[:_display_limit(req)]) + "." + _display_note(req, len(ordered))
            if missing:
                text += " Missing evaluated quantities: " + ", ".join(missing) + "."
            return conclusion("partial" if missing else "supported", text, (ref, source_ref, base_ref), refs, doc["context_ref"], doc["revision_ref"])
        return conclusion("unresolved", "No complete admitted risk ranking is bound to the requested scenario's evaluated violations and source calculation.")


def _violation_details(rows, source, *, limit=20):
    labels = {row["asset_ref"]: (dataset.removeprefix("result.res_"), row["index"])
        for dataset, data in source.get("datasets", {}).items()
        if dataset in {"result.res_bus", "result.res_line", "result.res_trafo", "result.res_trafo3w"}
        for row in data.get("rows", []) if isinstance(row.get("asset_ref"), str) and type(row.get("index")) is int}
    entries = []
    for row in rows[:limit]:
        identity = labels.get(row.get("asset_ref"))
        if identity is None and isinstance(row.get("element_kind"), str) and type(row.get("pandapower_index")) is int:
            identity = (row["element_kind"], row["pandapower_index"])
        if identity is None or not _finite(row.get("value")) or not _finite(row.get("limit")):
            continue
        kind, index = identity
        entries.append(f"{kind} index {index}: {row.get('kind', 'violation')}, value {row['value']:.6g} {row.get('unit', '')}, limit {row['limit']:.6g} {row.get('unit', '')}")
    complete = len(entries) == len(rows)
    text = " Verified violation details: " + "; ".join(entries) + "." if entries else ""
    if not complete:
        text += " Some verified violation details are not shown; the object list is incomplete."
    return text, complete


def _finite(value):
    return type(value) in {int, float} and math.isfinite(value)


def _active_loss(document):
    loss = document.get("losses", {}).get("total_active_loss", {})
    return loss.get("value") if isinstance(loss, dict) and loss.get("unit") == "MW" else None


def _powerflow(document):
    return document.get("operation") == "powerflow.ac" and document.get("status") == "succeeded" and document.get("converged", document.get("metadata", {}).get("converged")) is True


def _support(reference, document, evidence):
    return tuple(ref for ref, ev in evidence.items() if ev.get("result_ref") == reference
                 and ev.get("context_ref") == document.get("context_ref") and ev.get("revision_ref") == document.get("revision_ref"))


def _resolve_selector(selector, context, revision, invoke):
    if selector["namespace"] == "all":
        return _query_rows(selector["kind"], context, revision, invoke)
    namespace = selector["namespace"]
    field = "index" if namespace == "pandapower_index" else namespace
    identifier = selector["identifier"]
    if namespace == "pandapower_index":
        try:
            identifier = str(int(identifier))
        except ValueError:
            raise SimulatorCapabilityError({"code": "unknown_element", "message": "requested index is invalid"}) from None
    fields = (field,) if namespace in {"name", "alias"} else ()
    predicate_value = int(identifier) if namespace == "pandapower_index" else identifier
    filters = ([{"field": field, "operator": "eq", "value": predicate_value}]
               if namespace in {"pandapower_index", "asset_ref"} else None)
    matches = [row for row in _query_rows(selector["kind"], context, revision, invoke, fields=fields,
               filters=filters)
               if str(row.get(field)) == identifier]
    if len(matches) != 1:
        raise SimulatorCapabilityError({"code": "ambiguous_element", "message": "requested object is missing or ambiguous"})
    result = invoke("model.element.get", {"context_ref": context, "kind": selector["kind"],
                    "namespace": "asset_ref", "identifier": matches[0]["asset_ref"]})
    _identity(result, context, revision)
    element = result["element"]
    if matches[0]["asset_ref"] != result["asset_ref"] or matches[0]["index"] != element["index"]:
        raise SimulatorIntegrityError("resolved element does not match its unique dataset row")
    return [{"kind": selector["kind"], "index": element["index"], "asset_ref": result["asset_ref"]}]


def _identity(result, context, revision):
    if result.get("context_ref") != context or result.get("revision_ref") != revision:
        raise SimulatorIntegrityError("resolved object is outside selected context")


def _query_rows(kind, context, revision, invoke, *, filters=None, fields=()):
    rows, offset = [], 0
    while True:
        arguments = {"context_ref": context, "dataset": "network." + kind,
                     "select": ["index", "asset_ref", *fields], "offset": offset, "limit": 50}
        if filters:
            arguments["filters"] = filters
        result = invoke("model.dataset.query", arguments)
        _identity(result, context, revision)
        page = result.get("rows")
        if not isinstance(page, list) or result.get("returned_row_count") != len(page):
            raise SimulatorIntegrityError("resolved object page is inconsistent")
        rows.extend({"kind": kind, "index": row["index"], "asset_ref": row["asset_ref"], **{field: row[field] for field in fields}} for row in page)
        if len(rows) > 2048:
            raise _ResolutionScopeExceeded("requested object set exceeds bounded task resolution")
        next_offset = result.get("next_offset")
        if next_offset is None:
            if result.get("row_count") != len(rows):
                raise SimulatorIntegrityError("resolved object set is incomplete")
            return rows
        if type(next_offset) is not int or next_offset <= offset:
            raise SimulatorIntegrityError("resolved object paging did not progress")
        offset = next_offset
