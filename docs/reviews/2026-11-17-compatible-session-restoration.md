# Compatible session restoration

Owner: capstone-app. Product567d2638; PR133 merged into dev6714d223 after focused
macOS CI44034580886 passed (2m18s). No backend schema migration is included.

Recent-session audit found16 task-style v2 Threads with saved messages; newest15
all had task Works. A real completed Thread displayed welcome content until its
historical Work was selected. The missing default selection hid retained data.

Restore local reading state first. Keep a valid selected Work, explicit new intent,
new draft or pending command. Otherwise prefer a conversation Work, then the last
created task Work. Historical content uses its existing read-only projection.
The local explicit_new marker is optional; older stored reading state is admitted.
Mixed/prepared Thread tests cover missing and valid saved selections and isolated
drafts. Protocol1/professional entry behavior and server representation stay intact.

The initial restore test failed before the fix.137 App/type checks across12 direct
consumers and191 governance checks passed (one existing skip); doctor/diff passed.
Direct source review checked restoration ordering, storage scope, pending commands
and Work ownership. Independent reviewer dispatch was unavailable (Unknown model
gpt-6.1-luna); no independent approval is claimed.

Candidate canonical rebuild61990 completed0 at567d2638/image6eb44977, with
readiness, API/three-worker image identity and scoped cache maintenance. Existing
browser tab restored completed/cancelled task history and a continuous conversation
from old-format selected=new, without manual Work selection. Original instruction
and saved answer/product card were visible. Read-only product projection POSTs
occurred; zero execution commands. Snapshot hashes and persisted pins were equal
before/after. Protocol1 Thread still rendered without fatal restore errors.
Evidence: root ignored runs/recent-session-empty-investigation-20261117.

Actualdev6714d223 canonical rebuild42371 completed0/imageb002e445, readiness,
same-image API/three workers and scoped cache maintenance passed. Actual5173
repeated the three old-format restoration cases; snapshot hashes and pins stayed
equal, execution commands0. Existing Vivaldi5173 also shows the cancelled task's
original instruction, cancelled state and process file. Desktop screenshots checked.
Future important-record conversion is accepted backlog. Preserve lineage/resources/
products/Authority evidence, verify reading/downloads, retire obsolete writers and
readers, then remove unused compatibility. Task-style Work remains supported by
Control and send_message's shared execution core; mode alone is not deprecated.
