# Commercial idle and recovery patterns

Research checked on 2026-10-08 after the user rejected keeping compute alive
for an indefinitely open page. These sources describe specific products and
platforms; they do not establish one universal commercial-application policy.

| Source | Verified behavior | Capstone implication |
| --- | --- | --- |
| [GitHub Codespaces idle policy](https://docs.github.com/en/codespaces/setting-your-user-preferences/setting-your-timeout-period-for-github-codespaces) | Default 30-minute timeout; keyboard, mouse and terminal activity reset it. | A browser tab remaining open is not proof of user presence. Preserve running tasks rather than copying its whole policy. |
| [Snowflake warehouse cache guidance](https://docs.snowflake.com/en/user-guide/performance-query-warehouse-cache) | Suspension drops warehouse cache. Guidance differs by workload: about 5 minutes for ad-hoc data-science work and at least 10 minutes for BI queries that benefit from cache. | The shortest possible timeout is not always the best user experience or cost policy. Measure repeated-task latency and real activity gaps before tuning the timeout. These numbers are not Railway defaults. |
| [Render free-service idle policy](https://render.com/docs/free) | No inbound HTTP or WebSocket messages for 15 minutes permits sleep. Wake can take about a minute and uses a loading page. | Heartbeats can defeat idle savings. Loading feedback helps, but this free-tier latency is not a commercial UX target. |
| [Cloud Run WebSockets](https://docs.cloud.google.com/run/docs/triggering/websockets) | An open WebSocket makes its instance active and billable. | Long-lived realtime traffic has a cost; it must follow activity/task need. Capstone uses SSE, so verify Railway's own policy rather than transplanting this rule. |
| [Cloudflare hibernation](https://developers.cloudflare.com/durable-objects/best-practices/websockets/) | Clients can stay connected while a Durable Object leaves memory; messages wake it. | Connection lifetime and compute lifetime can be separate, but this feature is platform-specific. It is not an existing Railway container capability. |
| [Vercel Fluid Compute](https://vercel.com/docs/fluid-compute) | Concurrency reuse and pre-warming reduce cold starts. | Optimize startup and reuse resources instead of only decorating a long wait. These mechanisms are not assumed available in Railway. |
| [Replit deployment types](https://docs.replit.com/features/publishing/deployment-types) | Static, autoscale-to-zero and always-on services serve different traffic needs. | Keep the small presentation/storage baseline where it improves reliability, and sleep expensive compute. |
| [Chrome lifecycle guidance](https://developer.chrome.com/docs/web-platform/page-lifecycle-api) and [TanStack focus recovery](https://tanstack.com/query/latest/docs/framework/react/guides/window-focus-refetching) | Hidden/frozen pages should release unnecessary work; visibility/focus can trigger state refresh. | Stop passive background traffic and reconnect from the durable event cursor. Preserve unsaved state. |

## Proposed Capstone policy

The user's accepted requirements are: a very small idle bill is acceptable;
long-open idle pages must not keep cloud compute awake; running work is safe;
first opening waits for readiness; progress is truthful; local and cloud share
the fix. The following defaults are implementation choices to validate:

- Keep the small static App and PostgreSQL baseline. Sleep API and both workers.
- Release inactive browser subscriptions after 15 minutes, sooner when hidden.
  Keyboard, pointer, scroll and touch are activity; heartbeat, polling and
  task-progress rendering are not. A running task or uncertain submission
  prevents foreground inactivity suspension.
- Never replace a loaded conversation with a sleep screen. Preserve local
  draft, visible history, graph and scroll position. Initial opening uses the
  preparation view; return uses a small local progress surface.
- Resume on real intent/focus and admit mutating actions only after actual
  component readiness. Reconcile durable state before sending a queued action.
  Recover with the original command identity where the receipt is uncertain.
- Measure cold-start time and total residual cost. A long cold start is a
  performance defect to address; it cannot be fixed by fake progress or by
  quietly keeping every idle page alive.
- Use cloud-dev as the first measured rollout. Do not apply the same timeout
  to demo until cold-start and interaction evidence supports its trial-user
  experience. A cold-start penalty must be compared with the small warm
  baseline, not accepted solely because a platform offers scale to zero.

The earlier unbounded connected-page keepalive is rejected. This policy is not
yet a verified cloud deployment or an acceptance tag.
