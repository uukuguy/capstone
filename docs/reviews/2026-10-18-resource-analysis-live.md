# Uploaded resource analysis: local acceptance

## Scope

Keep upload interaction in the conversation. Do not add a file-manager page.
Use actual browser uploads and ordinary user requests. Evaluation reference
values stay outside the model inputs. No cloud or demo deployment is included.

## GB resource reading

- Session: `thr_35b6fdb2979e66d4c4f6`.
- Previously uploaded through the App, with pause/reload/resume: 1,077,936,128 bytes.
- Resource: `resource_781aa31037c2496b97e6a05e023c9983`, version 1.
- SHA-256: `c475c1483304d6170450472d482030f64798a90b4fbc1d56cf28260066553ae8`.
- User request: 请检查我上传的测试文件，告诉我文件大小和实际内容特征，给我一份简短的检查结果。不要把它当作业务数据。
- Native task: `pi-90ee37343b7a1296e947e3bbe4500a3310ac57ed0263c7dcd95023dacb8d4a2c`.
- Completed. The agent ran full-file SHA verification and a bounded full-file
  byte scan. It found 47 nonzero bytes followed by zero padding, and saved
  `file-check-result.md`. This is a synthetic transport fixture, not business data.
- Execution snapshots and staged bytes were removed after the task.
- Actual container permission check: owner read allowed; owner write denied;
  another task identity read denied.
- Verified local image:
  `sha256:f7f9e5a60e4a3c3b6916124001879ada9069caad66d3c21228c71493ff1eecd7`.

## Research from the upload control

- New session created through the App menu: `thr_9d2f1e36c89a120d9e97`.
- Selected ZIP through the browser file chooser:
  `两月电力市场模拟资料-15分钟.zip` (488,911 bytes).
- Contains README.md and the three unchanged CSV inputs from
  `docs/examples/enterprise-research-demo1-15min/inputs/`.
- The browser automation's file-chooser handoff submitted the same archive
  twice. Both persisted copies have the same bytes. The agent's reported
  input row counts match one dataset, not a doubled dataset.
- User request: 请分析我上传的两个月电力市场资料，重点看看负电价、外送通道利用和新能源限发的变化，做一份带图表、能直接打开的中文报告，方便我拿去汇报。资料是模拟样例，只用这些资料即可。
- Initial attempt: `attempt_2497250f89bf31db`. It extracted and read the ZIP,
  checked coverage and missing values, and computed metrics. It failed after
  about four minutes with private reason `model_turn_incomplete`.
  This is not accepted as a delivered report.
- The existing terminal projection discarded the provider failure category.
  Added fixed, non-sensitive categories; raw error strings remain excluded.
- Receipt storage was near its old 64 MiB total bound. Raised the host default
  to 256 MiB, without deleting old records. Large input bytes use a separate
  disk volume and quota.
- Natural continuation `attempt_12a2041b3190512d` also failed after 3m53s.
  Four input copies, seven SVG charts and three calculation files survived;
  no HTML report was delivered. Failure remains `model_turn_incomplete`.
- Event timestamps show extraction and row-count checks completed in about
  12 seconds. Later time was used for calculations, chart generation and
  corrections. `agent_research_read` returned `invalid_arguments` in about
  68 ms. It reads committed research state, not uploaded files.
- Found a lifecycle defect: the bridge forwarded intermediate `agent_end`
  before the native SDK could finish retry or compaction. The bridge now waits
  for prompt settlement. Native model-request retry is bounded to two retries;
  it does not replay tool operations. Regression and related checks: 77 passed,
  13 skipped. A local rebuild is in progress; real recovery is not yet verified.
- Report/revision acceptance remains pending. Do not count charts or source
  programs as the requested report.
- The research reader rejected `request_id: null` even though the published
  ResearchRead contract permits null outside receipt lookup. Fixed both native
  resource copies and added a regression covering all read sections. The test
  failed before the fix; all 17 research-tool tests now pass. This establishes
  the contract defect; the old public receipt does not retain the actual args.
- App research tools now use accurate reader-facing labels. The internal tool
  identifier remains in the details. Failed or interrupted runs show their last
  saved progress record without requiring expansion; absent records stay absent.
  All 97 message tests and TypeScript pass. Actual browser screenshot
  `/tmp/research-last-work.png` confirms the preserved chart-generation record
  is visible beneath the failed run, with no horizontal overflow.
- Remaining diagnostic gap: the old native event for the rejected research
  read says `is_error: false` while its actual returned body says
  `invalid_arguments`. Review semantic tool-result status propagation separately;
  do not treat transport success as successful research work.

## First delivered report after fixes

- Local API/worker image:
  `sha256:65b2ff8f0a6adb49042228ace8af61790212c0ef95e2a7cd4d318f8fd909b158`.
- UI continuation: 请继续把报告完成，先给我能打开看的版本。
- Attempt `attempt_ffe593f5dce76442`, native task
  `pi-e21e991038adaf6ee599a2729253a7d1ea227850052a85540f61d5e2acfac456`
  completed in 3m28s. The agent created report.html and metrics.csv and committed
  research revision 3. Earlier failures remain visible.
- Downloaded through the actual App link: report.html, 66,125 bytes,
  SHA-256 `aeb665a244120ec20dd5bd1254434387858aee81031038a61e9b085ad563d701`.
  Eight inline SVGs, no external src/href resources. Standalone browser preview
  has no horizontal overflow. Saved unchanged under root
  `outputs/uploaded-research-acceptance/report.html`.
- Province negative hours and channel utilization match the held-out fixture.
  The report labels summed province hours as hours without explaining overlap.
  This needs revision before calling the wording suitable for business use.
- Actual UI selected the report with 引用到下一轮 and sent:
  报告能看了。不过负价小时有点看不懂，是三个省加起来，还是实际持续了这么久？请按省讲清楚，最前面再放几条适合汇报的重点，现有图表保留。
- Revision `attempt_86b4c1c56da2c09b` / native task
  `pi-7d297e1a1a2ed64ba889bd0e93e141fec3a4c63aca4b1ffe5399b0fcabdab423`
  completed in 2m57s. Downloaded revised report through the App: 79,883 bytes,
  SHA-256 `b2b749e47350ffa2ae931ce978b560cb2a9675afe0de6d98d9bd28faef0d093e`.
  Nine inline SVGs and no external src/href resources. All eight original chart
  geometries are preserved; differences are labels and numbering. Browser
  preview shows the new briefing section and no horizontal overflow.
- Revision distinguishes 56.25 province-hours from 23.5 deduplicated clock
  hours across seven days. Province totals are 23.5, 22.0 and 10.75 hours.
- Adopted through the App as task delivery “两月电力市场分析报告 · 汇报修订版”.
  Page reload preserves the updated session title. The original and revised
  downloads are in root `outputs/uploaded-research-acceptance/`.
- This sample now passes report generation, download and natural revision.
  Progress reporting remains intermittent; the third execution did not emit
  a useful progress record for almost three minutes. This is still open.
  No Provider task is active. No cloud/demo deployment or dev merge is claimed.

## Earlier checks

63 focused backend tests passed. App: 25 upload/execution tests and 96 message
tests passed; TypeScript passed. One local HTTP test initially used the shell
proxy and returned 502; it passed with localhost in NO_PROXY.

Post-failure changes were rebuilt and the real continuation and revision above
completed. Final native resource/research checks: 30 passed, 1 skipped. These
are focused local checks, not a release or full-framework acceptance claim.
