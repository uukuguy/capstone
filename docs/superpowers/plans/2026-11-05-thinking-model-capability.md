# Thinking model capability implementation plan

**Goal:** Restore genuine dsv4 Thinking through the existing intent and native paths.
**Architecture:** Application-selected optional boolean capability flows to managed
SDK model declarations. Existing inference policy, display, persistence and grants stay.

1. Parent owns configs/runtime/workbench-llm-profiles.json and workbench_llm_profiles.py.
   Add a failing registered-default/invalid-type/revision test, then admit reasoning=true
   only for verified18804. Run test_workbench_llm_profiles.py.
2. Intent worker owns pi_intent.py/native_hosted_worker.py and their direct tests.
   Add model_reasoning: bool|None=None to the builder; bind config identity; set only
   its matching private per-session model. Resolve the frozen profile and respect
   recognition overrides. First fail, then prove actual SDK effort/deltas with loopback.
3. Native worker owns general_pi_executor.py/general_pi_server.py and direct tests.
   Add model_reasoning: bool=False to native_pi_launch; feed the resolved profile
   capability. Prove default compatibility and actual SDK reasoning requests/deltas.
4. Review the combined diff againstbfb16344; run only affected runtime/profile/stream
   checks. Snapshot explicit paths with a temporary index; preserve unrelated work.
5. Parent runs canonical local rebuild, real model/visible-page verification, then
   builds and deploys one source across local/63/三区 with fresh idle guards and backups.
   Re-run the original metadata query; verify Thinking before DB, once after DB, and
   after refresh. Persist measured limits and source/image receipts. No CI is authorized.
