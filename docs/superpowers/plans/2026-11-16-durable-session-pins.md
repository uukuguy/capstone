# Durable pins implementation

Owner: capstone-agent + capstone-app. Branch: fix/durable-session-pins-20261116.
Destination: dev. Acceptance: durable workspace pins and original data recovery.

1. Add failing backend tests for persisted reads, workspace isolation, additive
   import and explicit unpin tombstones. Implement workspace preference storage
   and private HTTP routes with atomic per-workspace updates.
2. Add failing App tests for response validation, stale response rejection,
   legacy import and retaining confirmed state on read failure. Connect existing
   session management to the pin hook and show retry feedback.
3. Recheck cleanup protection at the backend deletion boundary. Test importing
   from a stale browser after unpin and concurrent distinct-thread updates.
4. Run focused local tests and type checks. Rebuild through
   `make capstone-local-rebuild`, recover original pins through the public API,
   and verify both existing browser origins and backend restart.
5. Record exact source, local acceptance and remaining integration state in the
   canonical register and journal. Prepare reviewed commits; request one scoped
   macOS CI only after the local candidate is concrete.

No cloud/demo update, release verification or CI is authorized by this plan.
