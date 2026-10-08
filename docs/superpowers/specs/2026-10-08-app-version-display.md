# App build version

The user requested a visible App version during demo promotion. Show the package
version and seven-character source commit beside CAPSTONE in the shared header.
Use small muted text, no badge background, and a native tooltip with the complete
source commit. Keep the label visible on small screens without adding a row.

Local Vite reads the current Git commit. Release archives replace
`packages/capstone-app/build-revision.txt` with the exact archived commit before
upload. The tracked `development` marker is the local fallback. A release must
verify that the visible revision matches its deployed source. This public build
receipt contains no credentials and adds no hosted build environment variables.

Local Vite also reports uncommitted product changes as “开发中”. Its local-only
metadata route refreshes the header every 30 seconds and on focus, so a running
development server tracks later commits. Production bundles have no metadata
polling. Documentation and status edits do not mark product code as dirty.

The source is built into the bundle; a deployment tag is created only after
verification, so it cannot be the pre-build version. The package version remains
the product version, while the commit distinguishes each tested release.
