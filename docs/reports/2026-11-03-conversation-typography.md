# Conversation typography

The user requested instruction and formal-answer text to match the session list.
Candidate2148db14 on fix/conversation-typography-20261103 uses one13px variable
for the session navigation, user body and Markdown body. Body line-height is1.6.
Workspace heading levels1–3 use1.23/1.15/1.08em (about16/15/14px);
levels4–6 use1em. Tables and inline code use1em. Semantic levels are preserved.
The user's screenshot exposed a later workspace12px override missed by the
first09391ff5 candidate;2148db14 fixes that override and inline-code shrink.

TypeScript checks and151 direct conversation/process tests pass in7.87s.
The existing local browser tab shows saved real instructions and answers with
matching body size, list wrapping and code blocks. No new model task was sent.
Final2148db14 canonical rebuild passes readiness and API/worker image
equalitybc0ded4b; scoped cache cleanup receipt:
.capstone-agent/cache-maintenance-20261103-201310-62318.log.
The exact enterprise thread from the user's screenshot was revisited after
correction: instruction, answer paragraphs, table, headings and inline code
were visually checked together against the sidebar. No model request was sent.
The shared stylesheet warrants the App-only CI route before dev integration;
no CI is authorized for this new candidate yet. Dev remains7ad2529a.
Main, intranet and cloud/demo are unchanged.
