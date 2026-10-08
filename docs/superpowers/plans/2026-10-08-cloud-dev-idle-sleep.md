# Cloud-dev automatic idle sleep implementation

1. Add failing worker/wake/API tests for no idle database calls, wake delivery
   to both schedulers/families, queue draining, error recovery and shutdown.
   Update `thread_worker.py`, `worker_wake.py`, `cli.py` and `host_api.py`.
2. Add cold-start read retry tests in the App HTTP transport, retaining abort
   and command idempotency rules. Update only the transport/request bootstrap
   paths needed for first-page recovery.
3. Check database startup and family-health cold-start failure paths. Use
   bounded retries where needed, with safe errors and no idle network probes.
   Add a bounded public readiness stream and a restrained preparation view.
   Test incremental updates, failed/truncated streams and blocked input until
   all components are ready. Connected readers retain worker availability;
   disconnects remove client-owned keepalive traffic.
4. Run focused tests, integration gates and `make capstone-local-rebuild`.
   Measure idle CPU/memory and database transaction rates before/after;
   verify tasks still wake the sleeping scheduler and histories remain intact.
5. Compare total idle cost and wake reliability. Keep the small static App
   running for first-page reliability and a small PostgreSQL
   baseline initially; evaluate database sleep only if its measured cost
   justifies extra wake complexity. Commit the tested backend, enable
   Serverless on cloud-dev API and family workers, resume
   PostgreSQL/workers/API/App from that commit and verify source identity.
   Observe an actual no-client idle interval and the first request/task after
   sleep. Repeat the cycle. Preserve demo and persistent resources.
6. Record measured limits, restore the correct lifecycle/runbook statements,
   and create/push the cloud-dev stage tag only after required checks pass.

No Provider test is authorized by this cost task. Use registered scripted
cases and provider-free worker fixtures. Do not send commands in user Threads.
