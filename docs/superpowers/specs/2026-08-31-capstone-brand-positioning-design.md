# Capstone Brand Positioning and Documentation Migration Design

**Status:** approved for planning

## Purpose

Establish **Capstone Agent Framework** (short name: **Capstone**) as the
product identity for this repository's reusable, capability-first framework for
authoritative business-domain applications. Preserve
`grid-static-analysis` as the local repository directory and the first
pandapower application assembled by Capstone.

## Product hierarchy

```text
Capstone Agent Framework
└─ grid-static-analysis
   └─ first pandapower application
```

`grid-agent`, `gridctl`, and the pandapower Domain Pack remain the public
compatibility product for that first application. They are not renamed by this
work.

## Relationship to Asterion

Capstone and Asterion are parallel projects using a common underlying agent
foundation to research and validate different package types:

- **Capstone** validates authoritative business-domain capability packages,
  semantic operations, current-run evidence admission, and reader-facing
  business applications.
- **Asterion** validates multi-runtime control and technical-feature packages,
  with DCI as a reference product.

Neither project is represented as the other's dependency, runtime layer, or
product family. Documentation must avoid claiming an integration, shared
release, or upstream/downstream relationship that does not exist.

## Scope

The migration updates versioned project-facing documentation and package
descriptions so they consistently describe Capstone and identify
`grid-static-analysis` as its first pandapower application. Expected targets
include the English and Chinese READMEs, architecture and operations documents
that state product identity, structural project state, and distribution
metadata whose description is reader-facing.

New language must distinguish:

- the reusable Capstone framework seams and Domain Pack model;
- the current single pandapower application and its preserved v1.0.1
  compatibility contract; and
- future business-domain applications, which remain subject to C.2 selection
  and the later governance/composition workstreams.

## Compatibility and non-goals

This is not a technical rename. It must not change:

- the local directory name `grid-static-analysis`;
- existing Python or npm distribution names, import paths, commands,
  environment variables, protocols, tool names, or run-artifact paths;
- the exact two-field stdout envelope and simulator/evidence authority
  contracts; or
- the configured Git remote. The repository owner will rename the GitHub
  project independently.

The work does not select or implement C.2's second real domain, turn the
inventory conformance fixture into a production application, or introduce
multi-domain routing or governed writes.

## Documentation rules

- Shared product facts, headings, commands, and references remain aligned
  between `README.md` and `README.zh-CN.md`.
- Canonical historical designs remain historical: their dated implementation
  claims are not rewritten. Add a current-positioning note only where needed
  to prevent an obsolete product name from misleading readers.
- `docs/status/CURRENT-STATE.md` remains structural; session narration stays
  in `RESUME-NEXT-SESSION.md` and the append-only journal.

## Acceptance criteria

1. A new reader can identify Capstone as the framework and
   `grid-static-analysis` as its first pandapower application from both
   READMEs.
2. No documentation presents Capstone and Asterion as upstream/downstream or
   claims a runtime dependency between them.
3. All preserved grid compatibility names and contracts remain explicitly
   unchanged.
4. The English and Chinese READMEs remain factually aligned.
5. Documentation link checks, `git diff --check`, and `make doctor` pass.
