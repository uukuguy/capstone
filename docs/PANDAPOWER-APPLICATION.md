# Pandapower Static-Analysis Application

> Status: current operator reference.

This is the single operator reference for the first production domain
application. It defines how to run the complete pandapower static-analysis
application, how its output differs from the v1.0.1 compatibility path, and how
to verify current-run evidence.

## Formal application entry

The primary Makefile entry is:

```sh
make application
```

It defaults to:

- application ID `pandapower-static-analysis`;
- instruction file `validation/questions/task.md.txt`;
- the Provider and model resolved by the existing runtime configuration,
  including the Git-ignored `.env` file.

Operators may override the instruction file, Provider, or model explicitly:

```sh
make application INSTRUCTIONS=questions.txt
make application PROVIDER=deepseek MODEL=deepseek-v4-flash
```

`make application` is a production application command. It invokes the
registered `ApplicationProfile -> AgentApplication -> DomainBinding -> Domain
Pack` path and may perform billable LLM requests. It is not an alias for a test
or validation target.

The Makefile default remains the built-in pandapower application, while an
explicit `APPLICATION=registered-application-id` override remains available for future
registered single-domain applications. This does not add dynamic plugin
discovery, multiple active bindings, or cross-domain routing.

## Runtime and output contract

The formal application delegates to the existing `analysis-generic` runtime.
Its stdout is exactly one `capability-agent-output/1.0` JSON object containing:

- framework-owned `core` lifecycle, run, turn, audit, and reference metadata;
- pandapower-owned `domains.grid` status and semantic payload.

Progress, tool events, warnings, and diagnostics remain on stderr. Numerical
and network claims must come from current-run `gridctl` results admitted through
the pandapower authority. The run directory retains turns, context, tool
results, result/evidence artifacts, answer audits, replay state, and the report.

During a multi-question run, stderr shows model/tool activity, each finalized
turn, and each report checkpoint. `runs/<run_id>/output/report.md` is atomically
refreshed after every finalized answer, using the v1.0.1 pandapower report
structure (runtime, per-question answer, simulation context, trajectory, and
evidence). It is an operator-visible mutable checkpoint until normal completion;
only then is the final report admitted as the immutable report artifact.

If a run is interrupted, inspect the latest completed work without treating it
as final output:

```sh
sed -n '1,240p' runs/<run_id>/output/report.md
find runs/<run_id>/turns -name answer.json -print
```

The absence of a final `report_ref` or a non-completed outcome means the run was
not successfully finalized, even when the checkpoint contains prior answers.

Provider and model arguments never carry credentials. Credentials continue to
come from environment variables or project-owned ignored authentication state.

## Compatibility boundary

The existing commands remain supported and unchanged:

```sh
make analysis
make analysis INSTRUCTIONS=validation/questions/test.md.txt
```

They are the explicit v1.0.1 compatibility application. Their stdout remains
one JSON object whose only top-level fields are `question_id` and
`answer_output`. `make report` remains an alias for this compatibility path.

The compatibility envelope is not the framework-wide application output
contract. Promoting `make application` must not alter `run`, `analysis`,
`report`, `grid_*` tools, `grid-capability/1.0`, stderr diagnostics, or current-
run evidence admission.

## Validation commands

Provider-free wiring and regression checks remain separate from application
execution:

```sh
make doctor
make validate-application
make test
make test-e2e
make validate
make test-packages
```

`make validate-application` exercises the same prepared pandapower endpoint
with deterministic scripted model transport and real semantic `gridctl` calls.
It does not replace a real Provider-backed application run.

When Provider use is authorized, run both canonical business task files through
the formal application:

```sh
make application INSTRUCTIONS=validation/questions/task.md.txt \
  PROVIDER=deepseek MODEL=deepseek-v4-flash
make application INSTRUCTIONS=validation/questions/test.md.txt \
  PROVIDER=deepseek MODEL=deepseek-v4-flash
```

The Provider and model shown above are examples; the selected values must match
configured credentials and supported runtime IDs. Provider-backed commands may
incur charges.

## Success and failure behavior

A successful formal application run must:

1. emit one valid composite JSON object to stdout;
2. complete every required turn;
3. bind result and evidence references to the current run;
4. pass answer, report, and context-replay audits;
5. retain inspectable artifacts under the reported `runs/{run_id}/` directory.

Missing instruction files, unknown application IDs, invalid Provider/model
configuration, startup integrity failures, failed required turns, or invalid
answer evidence must return non-zero. Diagnostics go to stderr and must not
introduce a second stdout object or a raw traceback.

## Implementation acceptance

The Makefile change is complete only when:

- `application` is phony and appears in `make help` as the production registered
  application entry;
- `make application` supplies the pandapower application and canonical task
  defaults to the existing `analysis-generic` implementation;
- command-line `APPLICATION`, `INSTRUCTIONS`, `PROVIDER`, and `MODEL` overrides
  continue to work;
- no application runtime logic is duplicated in the Makefile;
- v1.0.1 compatibility commands and their stdout contract remain unchanged;
- provider-free repository gates pass; and
- at least one authorized real Provider run completes through the new entry.
