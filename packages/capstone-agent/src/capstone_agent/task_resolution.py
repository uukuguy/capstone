"""Application persistence and reader rendering for Pack-owned task coverage."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json

from collections.abc import Sequence
from capability_agent.domain.task import ResolvedTaskGoal, TaskConclusion
from .task_understanding import TaskRequest


def _digest(document):
    return sha256(json.dumps(document, sort_keys=True, ensure_ascii=False, allow_nan=False,
                             separators=(",", ":")).encode()).hexdigest()


def resolution_payload(request, goals):
    body = {"request": request.to_document(), "goals": [goal.to_document() for goal in goals]}
    return {**body, "digest": _digest(body)}


def resolution_state_from_events(events, *, request):
    selected = [event for event in events if event.event_type == "task_requirements_resolved"]
    if not selected:
        return {}
    payload = selected[0].payload
    if (set(payload) != {"request", "goals", "digest"} or TaskRequest.from_document(payload["request"]) != request
        or payload["digest"] != _digest({key: payload[key] for key in ("request", "goals")})
        or any(event.payload != payload for event in selected)):
        raise ValueError("resolved requirements changed or lost request binding")
    if not isinstance(payload["goals"], list) or not 1 <= len(payload["goals"]) <= 8:
        raise ValueError("resolved requirement count is invalid")
    goals = tuple(ResolvedTaskGoal.from_document(goal) for goal in payload["goals"])
    if len({goal.goal_id for goal in goals}) != len(goals):
        raise ValueError("resolved requirement identities are duplicated")
    return {"task_resolutions": goals, "task_resolution_route": _route(goals)}


def _route(goals):
    return "ordinary" if all(goal.status == "general" for goal in goals) else "professional"


def accept_resolution(service, claim, resolver):
    if claim.task_understanding is None or claim.task_resolutions:
        return claim
    goals = tuple(resolver(claim))
    if {goal.goal_id for goal in goals} != {goal.id for goal in claim.task_understanding.goals}:
        raise ValueError("resolved goals do not match accepted task")
    payload = resolution_payload(claim.task_request, goals)
    service.append_runtime_event(claim, event_type="task_requirements_resolved", payload=payload, visibility="diagnostic")
    return replace(claim, task_resolutions=goals, task_resolution_route=_route(goals))


def resolve_profiles(claim, profiles):
    if getattr(claim, "kind", None) == "send_ordinary":
        return tuple(ResolvedTaskGoal(goal.id, "general" if goal.execution == "general" else "clarification", "{}",
                     "" if goal.execution == "general" else "This request needs professional execution. Select professional mode to run the requested operation.",
                     execution_required=False) for goal in claim.task_understanding.goals)
    bindings = {}
    for profile in profiles:
        for binding_id, binding in profile.prepared_application.bindings.items():
            bindings[binding_id] = (profile, binding)
    goals = []
    for goal in claim.task_understanding.goals:
        proposal = goal.domain_request
        if goal.execution == "general":
            goals.append(ResolvedTaskGoal(goal.id, "general", "{}"))
            continue
        if goal.missing_requirements:
            goals.append(ResolvedTaskGoal(goal.id, "clarification", "{}", "; ".join(goal.missing_requirements),
                                          "" if proposal is None else proposal.binding_id, False))
            continue
        if proposal is None:
            goals.append(ResolvedTaskGoal(goal.id, "uncertified", "{}", "This saved task has no typed execution requirements. Submit the request again to resolve its scope.", execution_required=False))
            continue
        selected = bindings.get(proposal.binding_id)
        if selected is None:
            goals.append(ResolvedTaskGoal(goal.id, "clarification", "{}", "The requested Domain Pack is not enabled for this model.", proposal.binding_id, False))
            continue
        profile, binding = selected
        runtime = binding.runtime
        provider = getattr(runtime.profile, "task_provider", None)
        if proposal.schema == "capstone-professional-task/1":
            payload = proposal.payload
            if set(payload) != {"purpose"} or not isinstance(payload["purpose"], str) or not 1 <= len(payload["purpose"]) <= 1024:
                raise ValueError("compatibility purpose is invalid")
            stored = {**payload, "semantic_goal": goal.to_document()}
            goals.append(ResolvedTaskGoal(goal.id, "uncertified", json.dumps(stored),
                "Published execution remains available; task goal coverage is not verified by this Pack.", proposal.binding_id, True))
            continue
        if provider is None or provider.schema != proposal.schema:
            goals.append(ResolvedTaskGoal(goal.id, "clarification", "{}", "This task schema is not registered for the selected Domain Pack.", proposal.binding_id, False))
            continue
        allowed = {document.get("id") for document in getattr(runtime, "capability_documents", ())
                   if document.get("availability") == "published"}
        required = getattr(provider, "required_capabilities", lambda payload: ())(proposal.payload)
        if not isinstance(required, tuple) or len(required) > 32 or any(not isinstance(capability, str) or len(capability) > 128 for capability in required):
            raise ValueError("Pack capability requirement is not bounded")
        if not set(required) <= allowed:
            goals.append(ResolvedTaskGoal(goal.id, "unsupported", "{}", "Required published capabilities are not enabled in the selected binding.", proposal.binding_id, False))
            continue
        def invoke(capability, arguments):
            if capability not in allowed:
                raise ValueError("task resolution capability is not published in the selected binding")
            return binding.endpoint.executor.invoke(capability, arguments)
        resolved = provider.resolve(goal.id, proposal.payload, context_ref=profile.model_binding.context_ref,
                                    revision_ref=profile.model_binding.model_revision, invoke=invoke,
                                    semantic_goal=goal.to_document(), answer_policy={
                                        "language": claim.task_understanding.answer_policy.language,
                                        "scale": claim.task_understanding.answer_policy.scale})
        bind_candidates = getattr(provider, "bind_result_candidates", None)
        if callable(bind_candidates) and resolved.status == "ready":
            manifest = getattr(runtime.profile, "manifest", None)
            pack_id = getattr(manifest, "domain_id", None)
            if not isinstance(pack_id, str) or not pack_id:
                raise ValueError("selected Pack manifest identity is unavailable")
            candidates = tuple((item.result_ref, item.evidence_refs)
                               for item in getattr(claim, "prior_results", ())
                               if item.domain_pack_id == pack_id)
            resolved = bind_candidates(resolved, authority=runtime.authority, candidates=candidates)
            if not isinstance(resolved, ResolvedTaskGoal):
                raise ValueError("Pack result candidate binding returned an invalid task")
        goals.append(replace(resolved, binding_id=proposal.binding_id))
    for _ in goals:
        blocked = {goal.goal_id for goal in goals if goal.status not in {"ready", "general"}}
        goals = [replace(goal, status="clarification", execution_required=False,
                         reason="A required preceding goal is unresolved. Resolve that goal before this operation.")
                 if goal.status in {"ready", "general", "clarification"} and any(dependency in blocked for original in claim.task_understanding.goals
                                                    if original.id == goal.goal_id for dependency in original.dependencies)
                 else goal for goal in goals]
    return tuple(goals)


def render_conclusions(conclusions: Sequence[TaskConclusion], *, language: str, scale: str) -> str:
    # Text is produced by the selected Pack. Application formatting adds no facts.
    rows = sorted(conclusions, key=lambda item: item.status not in {"supported", "partial"})
    texts = [item.text for item in rows]
    if language.startswith("zh"):
        translations = {
            "Required published capabilities are not enabled in the selected binding.": "所选绑定未启用完成此任务所需的已发布能力。",
            "This request needs professional execution. Select professional mode to run the requested operation.": "此请求需要专业执行。请选择专业模式后运行所需操作。",
            "This saved task has no typed execution requirements. Submit the request again to resolve its scope.": "此历史任务未保存类型化执行要求。请重新提交请求以解析其范围。",
            "The requested Domain Pack is not enabled for this model.": "所需领域包尚未在当前模型中启用。",
            "This task schema is not registered for the selected Domain Pack.": "所选领域包未注册此任务契约。",
            "A required preceding goal is unresolved. Resolve that goal before this operation.": "前置目标尚未解决，请先完成前置目标。",
            "This goal has no verified Domain Pack conclusion.": "此目标尚无已验证的领域包结论。",
        }
        texts = [translations.get(text, text) for text in texts]
    return "\n\n".join(texts)


def requirement_schemas(profiles):
    documents = []
    for profile in profiles:
        for binding_id, binding in profile.prepared_application.bindings.items():
            provider = getattr(binding.runtime.profile, "task_provider", None)
            if provider is not None:
                documents.append({"binding_id": binding_id, **dict(provider.schema_document)})
            schema = {
                "schema": "capstone-professional-task/1", "payload_fields": {"purpose": "bounded user purpose, maximum 1024 characters"},
                "rules": "Professional compatibility request only for registered operations outside the selected Pack's typed requirement schema. Prefer the typed schema when it covers the requested operation, including unsupported subjects and clarification. Never use compatibility to retry or bypass a frozen unsupported/clarification decision. Preserve the full goal intent. This grants no new tools and verifies no task coverage. Existing selected published capabilities remain available."}
            documents.append({"binding_id": binding_id, **schema})
    return tuple(documents)


def compatibility_prefix(language):
    return ("以下结果沿用该领域包的证据准入规则；该领域包尚未验证本次任务的目标覆盖范围。" if language.startswith("zh")
            else "These results use the Pack's existing evidence admission. This Pack has not verified task goal coverage.")
