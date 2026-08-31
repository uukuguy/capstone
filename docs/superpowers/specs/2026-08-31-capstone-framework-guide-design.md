# Capstone Framework Guide and README Design

**Status:** approved for specification review

## Goal

Make Capstone legible as an evidence-backed framework for authoritative
business-domain applications, not merely as the renamed grid application.

## Reader model

The guide serves two readers: an application integrator deciding how to add a
new domain, and a framework contributor protecting Kernel/Domain Pack/
Application/Authority boundaries. It must distinguish implemented facts,
conformance proof, working theories, and deferred capabilities.

## Framework guide structure

`docs/architecture/capstone-framework.md` will explain, in order:

1. Capstone's purpose and explicit non-goals.
2. The four-layer dependency direction: Kernel, Domain Pack, Application, and
   registered Authority.
3. The runtime/tool, composite-output, and current-run evidence protocols.
4. The integration path for a new application: authority protocol, Domain Pack,
   Application assembly, provider-free acceptance, and authorized real-path
   validation.
5. The first verified `grid-static-analysis` application and its preserved
   compatibility contract.
6. The inventory conformance proof, C.2 working theory, and deferred
   multi-domain/write-governance capabilities.

## README structure

The English and Chinese READMEs will lead with Capstone's purpose, framework
guarantees, architecture, and application-integration path. They will then
present `grid-static-analysis` as the first verified application, with its
static-analysis features and commands moved beneath that heading. Existing
commands, protocol names, artifacts, and compatibility wording remain intact.

## AGENTS contract

`AGENTS.md` will name the four layers, dependency direction, and the rule that
new domain capabilities enter through a selected Domain Pack and registered
authority. Grid-specific simulator rules remain explicit for the first
application; generic framework text must not imply that unimplemented domain
discovery, writes, or multi-binding routing already exist.

## Acceptance criteria

1. A new reader can state Capstone's purpose and all four layers before reading
   the grid application section.
2. An integrator can follow a concrete, bounded application-addition sequence.
3. Each protocol boundary identifies its owner and prohibited leakage.
4. The grid application is clearly verified without being presented as the
   framework itself.
5. README translations remain aligned; `AGENTS.md` and architecture guidance
   agree; no compatibility identifier changes.
