# Lightweight summer-study rerun and title maintenance

## Real task rerun

Submitted the same 1,311-byte instruction in a new session through the existing
Vivaldi workbench tab. Instruction SHA256:
`d3f126381daf74a6d46cd9a3fb1aa8b9cde84813702c305c73ddea0c7ab2e03f`.

- Thread: `thr_24cd727c28ae86115139`.
- Attempt: `attempt_4d0252ebe2c98a28`; completed.
- Commercial DeepSeek Flash; `deep_research=false`; no DR children.
- Local source: `56b83ec4`; backend image:
  `sha256:e42ca852077d22f563d9971ce7572e652378b1dcade3db99b5d8e3291bce1d1e`.
- Canonical rebuild and scoped cleanup completed before submission. Cleanup
  receipt: `.capstone-agent/cache-maintenance-20261029-032937-15833.log`.
- No title-maintenance model calls ran during the timed business attempt.

| Measurement | Prior completed run | This completed run |
| --- | ---: | ---: |
| Total seconds | 420.676 | 384.959 |
| Model calls | 64 | 77 |
| Model response seconds, sum | 336.620 | 328.607 |
| Tool calls | 98 | 102 |
| Error tool receipts | 7 | 12 |
| Last tool return to completion, seconds | 8.643 | 8.360 |
| Uncached input tokens | 254,674 | 787,348 |
| Cache-read tokens | 4,077,696 | 3,615,104 |
| Output tokens | 68,166 | 59,650 |
| Total reported tokens | 4,400,536 | 4,462,102 |

This is one stochastic task comparison, not proof of a performance gain. Total
elapsed time fell 8.49%, but calls and uncached input grew. The bounded old
observation projection may disrupt prefix-cache reuse; this needs a separate
controlled check. Do not describe the candidate as an accepted optimization.

The slowest response was call 69: 45.005 seconds, including 9.549 seconds between
the first and last public Thinking chunks. Remaining time cannot be attributed
to private reasoning from these events. Call 66 took 28.115 seconds, including
11.340 seconds of public Thinking reception. Response timing and Thinking chunk
reception are separate measurements; chunks are not paragraphs.

Error receipts: five shell/script calls, four read-only SQL calls, and one each
for metric discovery, SQL preparation, and table discovery. Changed queries and
scripts recovered and the attempt delivered files. This report does not treat
an error receipt alone as proof of a blind retry.

Downloaded through the published artifact API and checked exact hashes:

- `迎峰度夏负荷与气象分析_2025.pptx`: 826,373 bytes; ZIP intact;
  14 slides and six media entries. SHA256:
  `5a408da417355b3fe737badc7ee48ad184d13559b5e03fb953ec4a71e09ce7f4`.
- `迎峰度夏核心指标_2025.csv`: 5,351 bytes; 18 data rows, 23 columns;
  consistent row width. SHA256:
  `83e289bd6b596143fd9380c066f7265775fa14d84b937033854998dd5fee3a25`.

The PPT cover was shown in Vivaldi's right pane. Full-slide layout and business
conclusion review are not claimed. Evidence is under ignored
`runs/light-rerun-20261029/`; preview capture is
`/tmp/light-rerun-ppt-preview.json`.

## Title scope correction

The first operator pass incorrectly selected 565 database records instead of
the workbench's loaded catalog. It changed 556 titles initially and repaired
nine omitted/invalid outputs. This was too broad for the requested sidebar task.

The actual catalog request loads 128 recent sessions and 20 archived sessions.
Recent pagination reports more records, but the current sidebar has no recent
load-more entry. This display gap is separate unfinished work.

Restored original title content and provenance for all 444 changed records
outside the loaded 148-session scope. Restoration appends control events with
increasing revisions; it does not delete events or reset revision counters.
Concurrent user rename/current execution checks remained in place.

Final loaded scope: 121 automatic titles updated, 10 user titles unchanged,
17 default titles unchanged. Zero `会话主题` placeholders remain in that scope.
All 11 database user-title documents retain the same before/after checksum.
Untargeted empty sessions and conversation bodies remain unchanged.

Protected backup, operation log and corrected counts are under ignored
`runs/title-refresh-20261029/`. Never repeat this operation using a database-wide
selector when the requested scope is the visible workbench catalog.

These are local verification and maintenance results. Dev integration and the
canonical development-control graph remain pending; no cloud/demo deployment
or release acceptance is claimed.
