# Capstone Portable Deployment Implementation Plan

> **For agentic workers:** Execute each checkbox in order with focused red/green checks and review each committed unit. Inline execution is selected by the user's approval and repository collaboration constraints.

**Goal:** Package one pinned backend image and one static App build for local Compose, Cloud Run plus Vercel, and Railway plus Vercel.

**Architecture:** One backend image takes an `api` or `worker` role at startup. All environments bind the same PostgreSQL and artifact contracts. The frontend stays static and calls the same versioned API; deployment files change environment variables and service roles, not application behavior.

**Tech Stack:** Docker, Compose, uv locked Python environments, PostgreSQL, local S3-compatible storage, Google Cloud Storage, Railway bucket, Vercel Vite build.

## Global constraints

- Build-time checked official PyPSA assets are present in the image. Runtime turns do not download models.
- API and worker roles deploy from the same immutable image digest; no platform-specific agent loops.
- Secrets enter only through ignored local env files or cloud secret bindings. Frontend bundles contain no operator or Provider credential.
- `PORT` is read at runtime; Cloud Run and Railway health checks use `/health/ready`.
- Do not perform a cloud deployment or a billed Provider request in this local implementation.
- Preserve unrelated user changes, especially the staged `.codex/config.toml`.

## File map

- `Dockerfile`, `.dockerignore`, `deploy/entrypoint.sh`: one backend image and role dispatch.
- `compose.yaml`, `deploy/local.env.example`: local API, worker, PostgreSQL, and S3-compatible store.
- `deploy/cloud-run/`: service and worker-pool commands plus required variables/secrets.
- `deploy/railway/`: Web and worker service configuration from the same image.
- `packages/capstone-app/vercel.json`: static App build and API routing.
- `docs/RUNBOOK.md`, `README.md`, `README.zh-CN.md`: build and environment instructions.
- `tools/tests/test_portable_deployment.py`: static configuration invariants.

---

### Task 1: One backend image

- [ ] Add static checks for `api`/`worker` role dispatch, locked install commands, PyPSA asset hash verification, and absence of committed secrets.
- [ ] Run the focused deployment check; expect missing files.
- [ ] Build the image from pinned package locks, install the registered authorities and official model assets during build, and use an unprivileged runtime user with an ephemeral writable run directory.
- [ ] Run `docker build`, image-level `capstone-agent --help`, and asset verification; commit only packaging paths.

### Task 2: Compose parity

- [ ] Add a Compose test that renders configuration and checks shared image, database, artifact store, health readiness, and separate API/worker roles.
- [ ] Run the focused test; expect missing Compose file.
- [ ] Add a local topology with PostgreSQL and S3-compatible storage, documented ignored secret configuration, and no public database or bucket port required for the App.
- [ ] Run `docker compose config` and the two-application scripted three-turn smoke path through the App/API; commit owned files.

### Task 3: Cloud templates and docs

- [ ] Add static checks for a Cloud Run service plus worker pool, Railway Web plus worker service from the same image, Vercel API routing, explicit Host/Origin values, and secret bindings.
- [ ] Run focused checks; expect missing templates.
- [ ] Add Cloud Run and Railway deployment templates, with PostgreSQL/object-store bindings and operational notes for SSE reconnect, worker lease expiry, and model assets. Align both README files and the runbook.
- [ ] Run template syntax checks, `make doctor`, link/symlink checks, and `git diff --check`; commit only task-owned paths.

## Review gate

Build and run the local topology and verify its API behavior matches the cloud templates' environment contract. Record that actual Cloud Run, Railway, and Vercel deployments remain separate authorized operations.
