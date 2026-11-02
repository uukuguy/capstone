# External network control implementation plan

**Goal:** Default-deny external access with an explicit user switch, while retaining registered internal tools.

**Architecture:** The application owns the switch. The native executor enforces task egress in its Linux network namespace. Trusted Provider relay access remains separate from task Internet access. Domain Packs retain their tool contracts.

**Constraints:** No automatic development enablement; no browser secrets; no prompt-only enforcement; no changes to user data or other deployments.

## Execution sequence

- [ ] Add tested IPv4/IPv6 task egress control, default closed. Allow only the fixed local relay and deployment-owned internal endpoints while closed. Fail startup if enforcement cannot be installed. Switch existing task connections as well as new ones.
- [ ] Connect authenticated control endpoints and bounded public application state. Record policy changes; show actual backend state in the App. Do not let model tools change policy.
- [ ] Replace unconditional prompt denial with effective policy, keeping legacy context readable. Keep internal retrieval capability independent from Internet access.
- [ ] Rebuild the current local lane. Test closed/open/closed from an actual task UID and retain evidence. Verify the relay and a configured internal endpoint remain reachable while external access is denied.
- [ ] Install a reviewed, pinned skill through CAPSTONE's managed resource path. Run a natural user request through the App and record loaded revision and real output. Restore closed state after testing.
- [ ] Update the canonical project register and verification record; distinguish implementation, local validation and deployment.

First unit: `native_network_policy.py`, tested by `test_native_network_policy.py`. It renders a dedicated nftables inet table and applies changes as one transaction. Only the trusted service can apply rules; task UIDs cannot change them. Readiness depends on successful installation. Application and UI integration follows only after kernel-level verification.
