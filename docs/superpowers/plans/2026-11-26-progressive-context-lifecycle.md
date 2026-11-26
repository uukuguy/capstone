# Progressive context implementation

1. Extend request observation in general-sdk.mjs and preserve the fields in
   general_pi_server.py. Test window and output allowance in the native
   context receipt test. Extend provider timing at the dispatch boundary.
2. Connect the current Thread state and admitted references to the existing
   request projection. Verify parameter and revision matching, dependencies,
   and stable ordering with identical inputs.
3. Apply the profile budget to the assembled request. Bound optional
   projections first. Exercise automatic compaction, restart and recovery
   through ordinary execution with a small model window.
4. Compare matched control and candidate runs using the design's instruction
   matrix. Check actual dispatch content against expected context and final
   products against tool receipts. Record per-type quality and cost before
   changing rollout defaults.
