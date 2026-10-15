# User-local offline delivery

## Accepted scope

The user selected an offline package for `linux/amd64`. The internal LLM uses
the tested OpenAI-compatible Provider, including models such as deepseek-flash.
Default `PROVIDER=openai`; prefer `OPENAI_BASE_URL`, `OPENAI_MODEL` and
`OPENAI_API_KEY`. Keep secrets in the backend environment. Packaging validation
uses scripted cases. The user separately authorized a minimal real check with
the existing DeepSeek API mapped to `OPENAI_*`. ARM64 is optional local test support.

For the local-trial profile, custom OpenAI endpoints use Pi's
`openai-completions` API. The official OpenAI endpoint retains Responses.
The application selects the protocol; the Kernel passes the explicit protocol
to Pi. Do not retry automatically with a different protocol.

## Delivery

Use a self-contained directory with the frozen deployment package, four Docker
image archives, image identities, SHA256 checksums and an offline installer.
Docker and Compose v2 are prerequisites. Installation must not download scripts,
catalogs, models or images. Model assets are already inside the backend image.
The runtime may access the configured internal LLM endpoint.

Keep existing online installation available. Reuse the lifecycle manager and
its shared-data compatibility check. Verify imported images by platform and
the config and AMD64 leaf-manifest digests read from each final tagged archive.
Docker storage backends expose different runtime IDs. Validate the imported ID
against that bound pair and materialize the private installation projection
before registering a version. Keep the static data contract unchanged. Verify
all layer blobs, ordered legacy/OCI mappings and uncompressed DiffIDs. Do not
assume docker save/load preserves registry RepoDigests.
Missing or corrupt inputs fail before stopping an active installation.
Preserve installation data, volumes and private configuration.

## Verification

Test Provider selection and custom endpoint propagation to both worker families.
Use real pinned Pi with a loopback SSE service to check HTTP path, model,
Bearer authentication, streamed text and a harmless tool round trip. Record
the separately authorized real DeepSeek text/tool check without credentials.
Test offline installation with network commands rejected, checksum failure,
architecture mismatch, repeat installation and preservation of existing data.
Run an actual AMD64 container installation and registered scripted cases,
report/evidence replay, restart and stop. Record exact source and image identity.
Existing cloud and demo stages are outside this change.
