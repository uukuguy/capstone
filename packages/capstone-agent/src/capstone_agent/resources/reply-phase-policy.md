## Execution and formal reply phases

The same agent and session perform the work and write the formal reply.
When the required work is complete, or a supported partial outcome must be delivered,
call capstone_begin_reply with outcome completed, partial or blocked. It may accompany
the last planned tool batch. The application changes phase after that entire turn ends,
then removes all executable tool definitions before the reply model call.

Use the collected observations, results, evidence and failed work to write the reply.
Entering this phase does not prove scientific correctness or erase unresolved work.
Answer admission still checks the saved references. If admission requires further work,
the host restores the original authorized tools in the same session and remaining budget.
