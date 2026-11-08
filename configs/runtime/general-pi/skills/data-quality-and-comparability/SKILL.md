---
name: data-quality-and-comparability
description: Assess source coverage, measurement quality and prerequisites for comparisons or downstream analysis.
---

# data-quality-and-comparability

Check source environment, exact object identity, metric meaning, unit evidence, timezone, sampling and selected immutable input versions. Directory presence proves neither measurement availability nor a known population.
Distinguish requests attempted/completed, valid sample-grid coverage and population coverage. Keep missing pages, invalid values, conflicts, duplicates, truncation and unexamined scope visible. Empty records do not establish zero values; missing values are not zeros.
State the counting unit and denominator. Quality categories can overlap: a missing primary value and conflicting alternatives may describe the same expected time cell. Do not add overlapping categories as if they were disjoint coverage totals.
Before comparison, inspect window lengths, workday/calendar effects, units, sampling and baseline alignment. A fixed-second offset is not an automatic calendar match. Near-zero baselines need absolute change and an explicit undefined relative result where applicable.
Before downstream analysis, check actual result kind and algorithm prerequisites. Discontinuous event windows are not complete regular grids. Sample sums are not energy; sample means are not automatically time-weighted. Heterogeneous metrics cannot be aligned merely because they share timestamps.
Require evidence for additive and mutually exclusive relationships before contribution analysis, and preserve residuals. Check the selected object's continuity, point count, distance mode and search coverage before historical matching.
Record the permitted interpretation and limits in the shared evidence record. If a prerequisite fails, choose a suitable method, acquire a bounded missing slice, or narrow the conclusion. Do not silently clean, interpolate, convert or guess mappings. Host schema and reference checks remain authoritative.

When the native skill record tool is available, load this exact admitted skill and report meaningful public phases with related tool IDs and product references. Loading does not prove application or successful verification. Use a bounded summary; never include credentials or private reasoning.

