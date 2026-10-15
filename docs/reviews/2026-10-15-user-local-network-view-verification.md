# User-local network view corrections

These changes are separate from the Linux offline delivery branch. They have
not been deployed to the user's existing19173 service.

## Scene selection

Read-only inspection of the user's b7e68dd records found one attempt that solved
the outage scenario, solved the base case for comparison, then read both results.
The final read selected the outage result. Scene projection instead used the
reverse order of first admission and selected the base case. The backend itself
returned the wrong scene; the screenshots alone did not establish cross-model
state leakage.

Projection now orders successful analysis outputs and exact result reads in the
same attempt by their actual tool-event order. References must be admitted and
correlated with the successful event. Authority verification still checks model
ancestry, revisions and geometry. Each N-1 parent retains its verified peak child.
Ranking and scene use the same source. A later base read can still select base.

Six first-consumption tests reproduced the old failure. Independent review then
found an earlier-read/later-analysis regression. Four further failing tests
covered base-read followed by outage AC or N-1; the implementation was corrected.
The full projection file passed106 tests, including failed, foreign-binding,
unadmitted and cross-model events. Independent review approved the correction.

## Camera requests

An isolated rendering of the real NetworkView component reproduced a camera
overwrite: after a return-to-task request and a user fit-to-view action, a later
layer ordinal replayed the old request. Static fit actions on the user's existing
Threads worked during inspection. This does not prove every reported fit failure
has the same cause.

A return request is now consumed once after the task layer is ready. New requests
still focus the task; subsequent layers, resize and camera-key changes do not
replay old requests. Tests cover delayed geometry, previews and model-camera
restoration.109 related component/Thread/model tests and TypeScript checks passed.
Browser checks of the isolated real component confirmed focus, full view, later
layer preservation, a new request and narrow viewport behavior without JS errors.

## Limits

No user Thread, Provider configuration, existing service or cloud deployment was
modified. Broader multi-model leakage was not reproduced. Actual runtime rebuild
and accepted-source verification remain separate from these focused checks.
