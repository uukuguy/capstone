# Gateway inventory repair

Status: implementation and focused checks complete; real runtime acceptance and
dev integration are pending.

The user asked which grid models the gateway has. Attempt
`attempt_af2c049b632230a5` made seven gateway calls in the existing North Thread.
Each failed after about30 seconds. The SDK replaced every non-success HTTP
response with one generic refusal. The final answer inferred gateway-wide
unavailability without a diagnostic code or successful model inventory.

Fresh MCP discovery succeeded, with the same catalog hash as the running host.
The App scopes endpoint first returned503 and later returned200 without a source
change or restart. Later checks isolated the current transport failure: the
gateway runs on this host, but the recorded LAN address no longer matches the
active network. TCP to that old address timed out; localhost and Docker's
`host.docker.internal:18001` reached the same authenticated service/catalog in
about0.5s. Local inventory returned seven registered scopes. The local protected
container connection now uses that stable host route. No source service, token
or database was changed. Historical timing remains unproven; schema drift and
gateway-wide downtime are not established diagnoses.

The fix admits the published read-only model inventory tool. Other model
operations remain outside the research adapter. Recognized timeout, connection,
authentication and publication codes reach the task without upstream text or
credentials. Resource failures stop subsequent gateway probes in that task;
argument corrections and a new user's task remain possible. In-flight calls can
settle, and failed calls do not issue source receipts.

Focused checks:145 Python tests passed in4.10s, plus6 SDK tests. They cover
inventory admission, denied model execution, wrapped transport errors, task
isolation, unchanged receipt guards and scoped CI selection. Real Provider and
Vivaldi acceptance are still required. All428 SDK checks and types/boundaries
also passed. Independent review found no Important/Critical issue; its minor
error-body cancellation finding was reproduced and corrected with a focused test.

The first real same-Thread Vivaldi attempt, `attempt_f96b240ae1d2869f`, returned
the seven scopes and saved a13,495-byte JSON product (SHA256
`44bac855b09c7ed4df02e0e5dce23e92a677cccca0cb4ca3be43b315dbda8270`).
This confirms the repaired connection and inventory admission. It also exposed
stale host guidance: always discover capabilities/services first, with a blanket
claim that model operations are disabled. The task requested detailed inventory
and three extra topology checks, one of which timed out. The useful list was
delivered, but this is not acceptance of an efficient list-only workflow.

Host guidance now selects the direct published operation for the user's scope.
An inventory question uses its summary/default mode and does not add readiness
or topology audits. Seven captured native configurations first failed the new
scope assertions, then passed after the correction. A second actual query will
verify the resulting tool use. The environment convention is recorded in the
runbook: localhost for host clients, host.docker.internal for local containers,
and the configured fixed address for the development server.
