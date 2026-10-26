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
