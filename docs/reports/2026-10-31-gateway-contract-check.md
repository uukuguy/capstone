# Gateway contract freshness

The data-gateway adapter now checks the publication before it reuses a catalog.
Only the adapter owns the agreed gateway protocol names. No business operation
name or provider route is added to the execution code.

- Compare `instance_id` and `contract_updated_at` from the lightweight check.
- Reuse the accepted catalog when both values match. This path does not list tools
  or download the complete contract.
- On change, read discovery, the tool catalog, and the complete contract. Check
  the publication again before admitting that snapshot.
- On failure, mark future gateway grants unavailable. Retain the request ID.
- Keep each running task's accepted catalog and receipts. Reject a call if its
  connected instance or exact tool publication no longer matches.

New sessions and new instructions check freshness before admission. Viewing
history does not call the gateway. The connection panel also offers a manual
contract update, separate from connection health checks.

Local verification: 178 focused backend checks passed in 5.15 seconds. App type
checks and 12 focused panel checks passed. A real reconnect to port 18001 returned
instance `3db5bb96-2c27-4d97-8584-346bc4a18656` and publication
`2026-10-31T13:19:56.304991+08:00`. An unchanged refresh reused the catalog in
20.98 milliseconds. Publication change, instance change, failed checks, and frozen
task snapshots have local contract tests; the real gateway publication was not
changed for those tests.

Final local rebuild passed with API/worker image `cada852ca21a`. Built adapter
and thread-service file hashes match source. Application contract reload passed
in 98.37 milliseconds. Receipt:
`runs/gateway-contract-check-20261031/application-reload.json`.
No visual browser acceptance is claimed. No CI, push, cloud deployment, or release
was started.
