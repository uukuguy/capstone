# Direct Thinking preview experiment

The user approved direct provisional Thinking display and asynchronous durable
batch writes. This trial covers supplied assistant_thinking_delta text only.
Tools, products, final answers and terminal success remain durable first.

Worker publishes bounded private HTTP batches to a single API process. Operator
authentication and the active attempt lease, thread and workspace protect this
endpoint. Browser SSE uses thinking_preview frames without durable sequence IDs.
Each preview has a UUID batch_id. Durable batches list preview_batch_ids.
The frame contains an ISO8601 UTC created_at and a payload with bounded
task, step, runtime and correlation metadata from the admitted Thinking event.
The existing Thinking view reconciles IDs and clears provisional state on reconnect.
The API keeps a bounded expiring suffix. Preview delivery is best effort.
The suffix holds at most 256 batches for 30 seconds. Publish wakes connected
streams through an in-process condition. The writer groups up to 16 KiB of
UTF8 text and 64 batches, with a five-second persistence interval. In-flight
publish reservations count toward bounds and flush barriers. One additional
bounded batch can be in the database writer. Failed durable writes stop the
writer and fail the attempt through the original synchronous service.
Durability errors remain fatal. All semantic and terminal events flush pending
Thinking first. Independent lease renewal, reads and cancellation use the original
service and never wait on the writer lock.

Flags default off: CAPSTONE_THINKING_PREVIEW=1 enables the API bus;
CAPSTONE_THINKING_PREVIEW_ORIGIN selects the private API origin on the worker.
CAPSTONE_OPERATOR_TOKEN remains backend only. This trial assumes one API process.
