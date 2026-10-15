# User-local offline delivery

## Accepted scope

The user selected an offline package for `linux/amd64`. The internal LLM uses
the tested OpenAI-compatible Provider, including models such as deepseek-flash.
Default `PROVIDER=openai`; prefer `OPENAI_BASE_URL`, `OPENAI_MODEL` and
`OPENAI_API_KEY`. Keep secrets in the backend environment. Do not call a real
Provider for packaging validation. ARM64 is optional local test support.

## Delivery

Use a self-contained directory with the frozen deployment package, four Docker
image archives, image identities, SHA256 checksums and an offline installer.
Docker and Compose v2 are prerequisites. Installation must not download scripts,
catalogs, models or images. Model assets are already inside the backend image.
The runtime may access the configured internal LLM endpoint.

Keep existing online installation available. Reuse the lifecycle manager and
its shared-data compatibility check. Verify imported images by platform and
image ID; do not assume docker save/load preserves registry RepoDigests.
Missing or corrupt inputs fail before stopping an active installation.
Preserve installation data, volumes and private configuration.

## Verification

Test Provider selection and custom endpoint propagation to both worker families.
Test offline installation with network commands rejected, checksum failure,
architecture mismatch, repeat installation and preservation of existing data.
Run an actual AMD64 container installation and registered scripted cases,
report/evidence replay, restart and stop. Record exact source and image identity.
Existing cloud and demo stages are outside this change.
