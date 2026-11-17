# Persistent workspace navigation

Owner capstone-app. Branch fix/persistent-workspace-navigation-20261117 targets
dev, based on3ef7d5b2. This corrects the earlier sidebar symptom fix. The user
explicitly requires a stationary sidebar: selection changes highlight, while
only the conversation area changes. Catalog updates run in the background.

Accepted design: the workspace route owns one navigation frame and catalog.
Retained React Activities contain only conversation/product views. The frame
retains navigation DOM, width, visibility, scroll and management state through
cold/warm selection, preparation, errors, new entry and cache eviction. Existing
conversation/product retention and session-specific controls remain supported.
No replacement conversation UI, backend mutation or pin migration.

1. Add failing integration assertions for identical sidebar/list DOM during
   cold preparation, completed switches, new entry and eviction. Assert selecting
   a session does not initiate another catalog request or await list loading.
2. Introduce a workspace-owned frame/context; reuse current navigation chrome,
   ControlGoalPanel, new-session control and SessionNavigation. Child frames
   render content and provide session-specific footer/legacy controls through
   slots. Child adapters skip catalog loads when the route owns navigation.
3. Run focused navigation/entry/workspace and direct consumer checks/types.
   Extend only the navigation gate manifest for affected files.
4. Canonical rebuild and existing-browser trial: cold/warm switches preserve the
   exact sidebar/list elements and row geometry, not merely row counts. Verify
   highlight before content readiness, original pin IDs and saved products.
5. Integrate via focused macOS dev PR, verify actual5173 and update canonical
   control/register/graph with an explicit exact deployed-source node before
   any control-only HEAD advances. Final own receipts remain ignored.
