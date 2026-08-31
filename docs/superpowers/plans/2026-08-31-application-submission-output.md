# Formal Application Submission Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the formal pandapower application an atomically refreshed v1.0.1-compatible `output/answers.jsonl` submission checkpoint without making that output format a Kernel protocol.

**Architecture:** Keep the Kernel limited to its existing call to the application report shell with ordered questions, accepted answer text, and workspace. Add a pandapower application-owned submission writer and invoke it from `PandapowerApplicationReportShell.render`; the report and JSONL checkpoints share accepted-answer inputs but neither is derived from the other.

**Tech Stack:** Python 3.12, pytest, standard-library `json`, `os`, and `pathlib`; existing `ApplicationWorkspace` and `AgentApplication` lifecycle.

## Global Constraints

- The stdout contract stays exactly one JSON object; generic application output remains `capability-agent-output/1.0`.
- Each JSONL line contains exactly `question_id` and `answer_output`, matching v1.0.1 `TurnController` envelopes.
- `answers.jsonl` and its lifecycle are owned by the pandapower application adapter; do not add a JSONL protocol or domain-specific output field to Kernel contracts.
- Use atomic same-directory replacement with flushed content; a later failed/interrupted turn retains the prior accepted-answer checkpoint.
- Do not change current-run evidence, report-artifact admission, or run provider-backed validation without authorization.

---

## File structure

- Create: `packages/grid-agent/src/grid_agent/compat/v1_0_1_submission.py` — application-owned strict JSONL renderer and atomic writer.
- Modify: `packages/capability-agent-kernel/src/capability_agent/application/runner.py` — invoke an optional application-owned output-preparation hook without naming output formats.
- Modify: `packages/grid-agent/src/grid_agent/compat/v1_0_1_report.py` — prepare and invoke the writer at its formal-application output boundary.
- Create: `packages/grid-agent/tests/compat/test_v1_0_1_submission.py` — focused writer tests.
- Modify: `packages/grid-agent/tests/application/test_generic_entrypoint.py` — formal application checkpoint and later-failure integration tests.
- Modify: `docs/PANDAPOWER-APPLICATION.md`, `docs/MANUAL-VALIDATION.md` — exact paths and incomplete-run semantics.

### Task 1: Pandapower-owned atomic submission writer

**Files:**
- Create: `packages/grid-agent/src/grid_agent/compat/v1_0_1_submission.py`
- Test: `packages/grid-agent/tests/compat/test_v1_0_1_submission.py`

**Interfaces:**
- Consumes: `ApplicationWorkspace.run_id`, `ApplicationWorkspace.output_path`, `questions: Iterable[str]`, and ordered accepted `answers: Iterable[str]`.
- Produces: `write_submission_checkpoint(*, workspace: ApplicationWorkspace, questions: Iterable[str], answers: Iterable[str]) -> Path`.
- Maps answer ordinal `n` to `question_id=f"{workspace.run_id}-t{n:03d}"`; rejects more answers than questions.

- [ ] **Step 1: Write the failing tests**

```python
def test_submission_checkpoint_writes_only_v1_envelopes_in_turn_order(tmp_path: Path) -> None:
    workspace = ApplicationWorkspace.create(tmp_path / "runs", "submission-run", ("grid",))
    path = write_submission_checkpoint(
        workspace=workspace, questions=("first", "second"), answers=("answer one", "answer two")
    )
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert lines == [
        {"question_id": "submission-run-t001", "answer_output": "answer one"},
        {"question_id": "submission-run-t002", "answer_output": "answer two"},
    ]
    assert all(set(line) == {"question_id", "answer_output"} for line in lines)


def test_submission_checkpoint_replaces_prior_complete_contents(tmp_path: Path) -> None:
    workspace = ApplicationWorkspace.create(tmp_path / "runs", "submission-run", ("grid",))
    path = write_submission_checkpoint(workspace=workspace, questions=("first", "second"), answers=("one",))
    write_submission_checkpoint(workspace=workspace, questions=("first", "second"), answers=("one", "two"))
    assert [json.loads(line) for line in path.read_text().splitlines()] == [
        {"question_id": "submission-run-t001", "answer_output": "one"},
        {"question_id": "submission-run-t002", "answer_output": "two"},
    ]
```

- [ ] **Step 2: Run tests to verify RED**

Run: `uv run --project packages/grid-agent pytest packages/grid-agent/tests/compat/test_v1_0_1_submission.py -q`

Expected: FAIL during collection because `grid_agent.compat.v1_0_1_submission` does not exist.

- [ ] **Step 3: Implement the minimal writer**

```python
def write_submission_checkpoint(*, workspace: ApplicationWorkspace, questions: Iterable[str], answers: Iterable[str]) -> Path:
    question_values = tuple(questions)
    answer_values = tuple(answers)
    if len(answer_values) > len(question_values):
        raise ValueError("accepted answers exceed application questions")
    payload = "".join(
        json.dumps({"question_id": f"{workspace.run_id}-t{ordinal:03d}", "answer_output": answer},
                   ensure_ascii=False, separators=(",", ":")) + "\\n"
        for ordinal, answer in enumerate(answer_values, start=1)
    )
    target = workspace.output_path / "answers.jsonl"
    temporary = target.with_name(f".{target.name}.tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(target)
    return target
```

- [ ] **Step 4: Run tests to verify GREEN**

Run: `uv run --project packages/grid-agent pytest packages/grid-agent/tests/compat/test_v1_0_1_submission.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add packages/grid-agent/src/grid_agent/compat/v1_0_1_submission.py packages/grid-agent/tests/compat/test_v1_0_1_submission.py && git commit -m "feat: add application submission checkpoint"`

### Task 2: Attach checkpointing only to the pandapower application output adapter

**Files:**
- Modify: `packages/capability-agent-kernel/src/capability_agent/application/runner.py`
- Modify: `packages/grid-agent/src/grid_agent/compat/v1_0_1_report.py`
- Modify: `packages/grid-agent/tests/application/test_generic_entrypoint.py`

**Interfaces:**
- Consumes: the existing `PandapowerApplicationReportShell.render(questions, answers, workspace, ...)` call after accepted answers plus an optional `prepare(*, questions, workspace)` method called by the runner after workspace creation.
- Produces: an empty submission checkpoint at setup, unchanged report text, and a refreshed `workspace.output_path / "answers.jsonl"` side effect after accepted answers.
- Does not modify: `ApplicationProfile`, `ReportShell`, or `ApplicationWorkspace` to name or define submission JSONL output. The runner's optional lifecycle callback names only application-output preparation, never a filename or format.

- [ ] **Step 1: Write failing integration tests**

```python
def test_generic_pandapower_application_checkpoints_standard_submission_answers(tmp_path: Path) -> None:
    profile = build_pandapower_application_profile()
    workspace = ApplicationWorkspace.create(tmp_path / "runs", run_id="run-1", binding_ids=("grid",))
    application = build_generic_application(
        "pandapower-static-analysis", prepared_application=_prepared(profile),
        provider=_Provider(), workspace=workspace, catalog=object(),
    )
    outcome = run_generic_application("pandapower-static-analysis", ("question one", "question two"), application=application)
    assert outcome.status == "completed"
    assert [json.loads(line) for line in (workspace.output_path / "answers.jsonl").read_text().splitlines()] == [
        {"question_id": "run-1-t001", "answer_output": "first"},
        {"question_id": "run-1-t002", "answer_output": "second"},
    ]


def test_generic_pandapower_application_retains_checkpoint_after_later_failure(tmp_path: Path) -> None:
    class FailingProvider(_Provider):
        def prompt_and_wait(self, question: str, **kwargs: object) -> str:
            if self.index == 1:
                raise RuntimeError("second question failed")
            return super().prompt_and_wait(question, **kwargs)
    profile = build_pandapower_application_profile()
    workspace = ApplicationWorkspace.create(tmp_path / "runs", run_id="run-1", binding_ids=("grid",))
    application = build_generic_application(
        "pandapower-static-analysis", prepared_application=_prepared(profile),
        provider=FailingProvider(), workspace=workspace, catalog=object(),
    )
    outcome = run_generic_application("pandapower-static-analysis", ("first", "second"), application=application)
    assert outcome.status == "failed"
    assert [json.loads(line) for line in (workspace.output_path / "answers.jsonl").read_text().splitlines()] == [
        {"question_id": "run-1-t001", "answer_output": "first"},
    ]


def test_generic_pandapower_application_prepares_empty_submission_checkpoint(tmp_path: Path) -> None:
    class FirstQuestionFails(_Provider):
        def prompt_and_wait(self, _question: str, **_kwargs: object) -> str:
            raise RuntimeError("first question failed")
    profile = build_pandapower_application_profile()
    workspace = ApplicationWorkspace.create(tmp_path / "runs", run_id="run-1", binding_ids=("grid",))
    application = build_generic_application(
        "pandapower-static-analysis", prepared_application=_prepared(profile),
        provider=FirstQuestionFails(), workspace=workspace, catalog=object(),
    )
    outcome = run_generic_application("pandapower-static-analysis", ("first",), application=application)
    assert outcome.status == "failed"
    assert (workspace.output_path / "answers.jsonl").read_text(encoding="utf-8") == ""
```

- [ ] **Step 2: Run tests to verify RED**

Run: `uv run --project packages/grid-agent pytest packages/grid-agent/tests/application/test_generic_entrypoint.py -k 'submission_checkpoint' -q`

Expected: FAIL because the formal adapter does not create `output/answers.jsonl`.

- [ ] **Step 3: Add a format-neutral optional preparation callback, then implement it in the pandapower adapter**

```python
# capability_agent.application.runner.AgentApplication.run, immediately after _ensure_workspace:
self._prepare_application_output(request=request, workspace=workspace)

def _prepare_application_output(self, *, request: ApplicationRequest, workspace: ApplicationWorkspace | None) -> None:
    if workspace is None:
        return
    method = getattr(self.report_shell, "prepare", None)
    if callable(method):
        _call_factory(method, questions=request.questions, workspace=workspace)

# grid_agent.compat.v1_0_1_report
from grid_agent.compat.v1_0_1_submission import write_submission_checkpoint

class PandapowerApplicationReportShell:
    def prepare(self, *, questions: Iterable[str], workspace: ApplicationWorkspace) -> None:
        write_submission_checkpoint(workspace=workspace, questions=questions, answers=())

    def render(self, *, questions: Iterable[str] = (), answers: Iterable[str] = (), workspace: ApplicationWorkspace | None = None, **_: object) -> str:
        question_values = tuple(_text_values(questions, "questions"))
        answer_values = tuple(_text_values(answers, "answers"))
        if workspace is None:
            raise RuntimeError("pandapower application report requires a workspace")
        write_submission_checkpoint(workspace=workspace, questions=question_values, answers=answer_values)
        # Retain the existing AnalysisWorkspace adaptation and report rendering below.
```

The existing `_write_report_checkpoint()` runs after an accepted turn; its final render repeats the complete checkpoint idempotently. A second-turn failure never refreshes it, preserving the first answer. Preparation of an empty checkpoint is invoked before provider startup, so a first-question failure leaves a readable empty file.

- [ ] **Step 4: Run focused tests to verify GREEN**

Run: `uv run --project packages/grid-agent pytest packages/capability-agent-kernel/tests/application/test_runner.py packages/grid-agent/tests/application/test_generic_entrypoint.py -q`

Expected: PASS; generic report lifecycle stays green and the pandapower adapter checkpoints accepted answers.

- [ ] **Step 5: Commit**

Run: `git add packages/grid-agent/src/grid_agent/compat/v1_0_1_report.py packages/grid-agent/tests/application/test_generic_entrypoint.py && git commit -m "feat: checkpoint formal application submissions"`

### Task 3: Document compact submission versus final report semantics

**Files:**
- Modify: `docs/PANDAPOWER-APPLICATION.md`
- Modify: `docs/MANUAL-VALIDATION.md`
- Test: `packages/grid-agent/tests/application/test_generic_entrypoint.py`

**Interfaces:**
- Consumes: running or complete `runs/<run-id>/output/answers.jsonl`, `output/report.md`, and final `report_ref` state.
- Produces: operator guidance that treats JSONL as a standard submission checkpoint, not evidence or whole-run success proof.

- [ ] **Step 1: Keep the artifact assertions in the completed integration test before editing docs**

```python
assert workspace.output_path.joinpath("answers.jsonl").is_file()
assert workspace.output_path.joinpath("answers.jsonl").read_text(encoding="utf-8").splitlines()
```

- [ ] **Step 2: Run the focused proof before documentation edits**

Run: `uv run --project packages/grid-agent pytest packages/grid-agent/tests/application/test_generic_entrypoint.py -k 'submission_checkpoint' -q`

Expected: PASS.

- [ ] **Step 3: Document exact checkpoint semantics**

Add this meaning in both documents:

```markdown
`runs/<run-id>/output/answers.jsonl` is the standard submission checkpoint.
Each line contains only `question_id` and `answer_output`, in input order, and
is atomically refreshed after every accepted answer. It can be a valid prefix
after interruption or failure; completed status plus the admitted final
`output/report.md`/`report_ref` determines whole-run success.
```

State explicitly that JSONL contains no evidence, diagnostics, or report-artifact admission data.

- [ ] **Step 4: Run repository verification**

Run: `git diff --check && make doctor && make test && make test-e2e && make validate`

Expected: exit `0` for every command; no stdout-envelope, simulator-boundary, or capability-coverage regression.

- [ ] **Step 5: Commit**

Run: `git add docs/PANDAPOWER-APPLICATION.md docs/MANUAL-VALIDATION.md && git commit -m "docs: document application submission checkpoint"`

## Plan self-review

- Task 1 covers strict envelopes, turn ordering, and atomic replacement.
- Task 2 keeps all formatting in the pandapower application adapter and verifies accepted-prefix retention after later failure.
- Task 3 distinguishes standard submission from report/evidence finality and runs the required project gates.
- No task adds JSONL names, schemas, or writer types to Kernel interfaces; every implementation and verification step is explicit.
