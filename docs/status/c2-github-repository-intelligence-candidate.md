# C.2 Working Theory — GitHub Repository Intelligence

**Status:** current working theory; no production domain is selected or implemented.

## Candidate

Use GitHub's versioned REST API as a registered, read-only authority for a
repository-intelligence application. The prospective application would answer
auditable questions about a configured repository's issues, pull requests,
releases, and commits without giving the model a generic HTTP client, token,
shell, or write capability.

GitHub documents read and mutation endpoints separately for issues, pull
requests, releases, and commits. Authentication is explicit and permissions
are endpoint-specific, which supports a least-privilege, read-only first
profile. See [GitHub REST API overview](https://docs.github.com/en/rest/about-the-rest-api/about-the-rest-api),
[issues](https://docs.github.com/en/rest/issues),
[pull requests](https://docs.github.com/en/rest/pulls),
[releases](https://docs.github.com/en/rest/releases), and
[authentication](https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api).

## Proposed Capstone boundary

```text
repository-intelligence application
  -> github Domain Pack
  -> githubctl (registered repositories + allowlisted read operations)
  -> GitHub REST API
```

- The Domain Pack would provide contracts, policy, guides, projectors, and a
  current-run authority adapter through the public Kernel SPI.
- `githubctl` would own repository registration, exact API-version binding,
  credential injection, rate-limit handling, response capture, revision
  identity, and evidence artifacts.
- The model could receive only semantic operations such as repository summary,
  issue query, pull-request query, release lookup, and commit comparison.
- Current-run evidence would bind every reader-facing claim to the captured
  response identity and the configured repository.

## Business acceptance tasks

1. **Backlog triage:** identify open issues matching a declared label/state and
   report their authoritative fields with evidence.
2. **Release readiness:** compare a configured release/tag or commit range with
   open pull requests and report the referenced, current API facts.

Both tasks are useful without any mutation. Creating issues, changing labels,
reviewing, merging, or publishing releases are deliberately excluded until
Workstream D supplies approval, actor/tenant scope, authorization, idempotency,
audit, and compensation semantics.

## Validation questions

- Can an immutable response/evidence model retain API version, repository
  identity, pagination/cursor boundaries, ETag or revision metadata, and a
  content digest without exposing credentials?
- Can provider-free acceptance use recorded public API fixtures while a
  separately authorized bounded run verifies the real authority path?
- Can this be added as a separately installable Domain Pack without modifying
  Kernel, generic Pi transport, replay, answer commit, or Workbench core?

## Rejected shortcuts

- Do not expose arbitrary URLs, `gh`, shell, or a generic REST client to the
  model.
- Do not treat cached GitHub responses as current-run authority.
- Do not reuse or promote the inventory fixture as this production domain.
- Do not add write actions merely because GitHub supports them.

## Next experiment

Write the C.2 design contract around this candidate, then prove a minimal
registered-repository read path with two provider-free acceptance fixtures and
one separately authorized real-authority probe.
