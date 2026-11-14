# Three development deployments

Source: 22cd17287c97659bd487008be087b0948009d67c.

| Environment | App | Readiness | Real short instruction |
| --- | --- | --- | --- |
| local-dev | http://localhost:5173/ | ready | completed, 3.10 s |
| intranet-dev | http://192.168.72.63:5173/ | ready | completed, 8.86 s |
| dky3-dev | http://192.168.72.66:5173/ | ready | completed, 9.61 s |

All App bundles contain the exact source revision. API and workers use the same
image within each environment. Both intranet API/worker images are
038a69260cea02136c53e7523d12f71af00c0b425f1d90449e8de7b1435291eb.
Local API and workers use095a2a81d87451818a80250c8b33fc97df6e017f8d715e91aa47f96ca6a76899.

The canonical local rebuild passed readiness and scoped cache maintenance. Local
App serves the prepared exact-source bundle with Vite preview and same-origin API.
Intranet builds reused installed dependencies after confirming lock/manifest inputs
were unchanged from367374aa. A native resource symlink packaging error on63 was
corrected by dereferencing source resources before successful activation.66 received
the same backend image and corrected native resources. No repository runtime code
was changed by deployment.

Database dumps and old configuration remain in each installation's private
backups/deploy-22cd1728 directory. Existing data volumes, gateway credentials,
provider settings and default model selections were retained. No CI was started.
Short live tasks verify basic execution, not complex business-task acceptance.
Private deployment receipts and logs: .capstone-agent/deploy-20261106/.

## Shared gateway options

At the recorded 2026-11-06 verification, all three installations offered 内网联调 (192.168.72.63:18001/mcp) and
三区研发 (192.168.72.66:18001/mcp). Both entries reported connected in each
installation. Additions used the supported gateway API and durable protected registry.
This is a historical receipt, not a current connectivity probe.
Existing selections were retained: local-dev本机联调,intranet-dev内网联调,
dky3-dev三区研发. No application rebuild, restart or credential logging was needed.
