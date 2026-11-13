# Resource projection verification

The approved architecture improvement plan adds a PostgreSQL resource read model.
Thread events remain authoritative. Three additive tables store a projection
cursor, upload metadata and indexed parts. The cursor and projection rows commit
together. Deleting a cursor cascades only its derived rows; the next read rebuilds
from retained events. Old writers can continue to append events. No existing
event, resource object or user data is migrated or deleted.

Projection recovery reads at most 256 events per database fetch. Transactions
always acquire the Thread row before the projection cursor. Object storage I/O
stays outside these transactions. Part admission reads one indexed part; its
HTTP size check reads only metadata. Listing resources does not load part bodies.
Upload quotas still count published resources and release cancelled reservations.

## Evidence

- 87 focused Python checks passed, including real PostgreSQL and memory paths,
  in 10.05 seconds. Coverage includes cancellation during storage, late duplicate
  acknowledgement, hash checks, attachment adoption, projection rebuild and
  projection/event rollback. One existing Starlette deprecation warning remains.
- Real loopback HTTP, isolated PostgreSQL 16 and temporary disk object adapter:
  uploaded and downloaded 1,077,936,128 bytes in 257 bounded parts. SHA-256:
  `075dd52c81f01dbfa58c6f9d886dce4f3648184bf243e427a99d042c00afe244`.
- Upload: 12.251 seconds; whole-file verification: 0.986 seconds;
  streamed download: 1.030 seconds. First/last 32 part means: 49.744/45.070 ms.
- Peak process RSS: 151,896,064 bytes. Client and API ran in the same process;
  this is not a measurement of the deployed API alone. Temporary files and the
  test Thread were removed after verification.
- Probe script: `/tmp/capstone_resource_scale_probe.py` on the development host.

## Remaining acceptance

This is local implementation evidence, not cloud acceptance or a performance
comparison with the previous version. S3/GCS adapters, many-resource pagination,
long-history first-rebuild latency, deployed runtime identity, browser checks,
real model continuation and dev integration remain open. The in-memory adapter
still uses event replay. Full resource scale acceptance remains open.
