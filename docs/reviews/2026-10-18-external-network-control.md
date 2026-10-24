# External network control verification

Status: local executor control and App interaction verified. Broader host-owned retrieval paths and research skill acceptance remain open.

Final canonical rebuild: API and worker share sha256:02bd859bb90716902c4fd66c5520836fad6abce7304072c2c587fb80105fa2c0. App click, reload, and closure passed. Real UI request in thread thr_0e6413c0834c71b9b2a1 completed as attempt_9a1f723460d8fb5f (9.4 s). Its persisted native tool observation contains HTTP 200 and the Example Domain HTML title; this is actual retrieval evidence. External access was then closed through the lamp. No cloud or demo change.

## Accepted interaction

Default closed. One small lamp next to CAPSTONE in the left navigation. Grey means confirmed closed; teal means confirmed open. An unknown backend state must remain distinct. A click changes the global task network policy. The UI waits for the backend result. Internal endpoint configuration remains deployment-owned.

## Implemented candidate

- Native task egress uses a dedicated nftables `inet` table in the executor namespace. It covers IPv4 and IPv6 and task UIDs from 10000 upward.
- The trusted local Provider relay and exact deployment-owned internal endpoints remain reachable. Enabling public access does not open private, loopback, link-local or metadata addresses.
- Default public DNS is also blocked while closed. An approved internal resolver must not forward queries externally.
- Changes replace the table in one transaction. There is no established-connection bypass. The service fails startup if rules cannot load.
- Authenticated private control endpoints and the application endpoint return confirmed enforcement state. Scripted public-demo access does not grant control.
- The native execution prompt receives the enforced state; legacy stored contexts remain readable. User source limits remain in force.

## Evidence so far

An isolated Linux container ran native task probes as UID 10000 with no supplementary groups:

| State | Public IPv4 TCP 1.1.1.1:443 | Approved internal endpoint | Local relay | Unapproved IPv6 loopback |
| --- | --- | --- | --- | --- |
| Closed | Blocked | Connected | Connected | Blocked |
| Open | Connected | Connected | Connected | Blocked |
| Closed again | Blocked | Connected | Connected | Blocked |

The task UID could not flush firewall rules. A second test assigned a global-unicast IPv6 address inside the isolated test namespace: closed/open/closed TCP probes passed, and a previously established echo connection was blocked after closure. This proves IPv6 filtering without claiming that this host has an external IPv6 route. Docker's resolver was separately tested on a user-defined bridge: name resolution failed/succeeded/failed across closed/open/closed. The initial default-bridge DNS probe failed while open because that bridge uses a different resolver; the deployed Compose path uses the verified user-defined bridge.

Focused backend checks: 35 passed. Additional application/profile checks: 4 passed, 5 PostgreSQL-dependent checks skipped. App lamp/workspace checks: 7 passed; TypeScript check passed. No full integration claim.

## Local deployment

Two canonical local rebuilds stopped when the Docker socket disappeared. Diagnosis: the host disk had only 270 MiB free; OrbStack logged StorageFull / OS error 28 and stopped the VM. `orb start` restored it. Only regenerable builder cache was pruned (approximately 60 GB); no images, volumes, uploads or user files were removed. The subsequent inventory policy regression was fixed and covered by a test. The final canonical rebuild passed readiness and identical API/worker image checks.

## Remaining acceptance

Private policy-change intent and applied-state records are now persisted and tested. App click/refresh, effective native prompt and real retrieval passed. Other host-owned retrieval/download paths and a pinned research skill installation/load/use test remain open. Do not describe the executor proof as complete system-wide isolation.
