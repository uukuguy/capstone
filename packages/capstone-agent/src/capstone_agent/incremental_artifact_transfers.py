"""Optional live transfers never wait or retry on the native control channel."""
import logging
from collections import OrderedDict

from .native_failure_origin import native_failure_origin
from threading import Condition, Thread


class IncrementalArtifactTransfers:
    def __init__(self, transfer, *, maximum):
        self.transfer, self.maximum = transfer, maximum
        self.condition = Condition()
        self.pending = OrderedDict()
        self.closed = False
        self.error = None
        self.thread = Thread(target=self._run, daemon=True)
        self.thread.start()

    def submit(self, artifact):
        # Same task/path, newer captured bytes replace only a waiting version.
        key = (artifact.get('task_id'), artifact['host_artifact_id'].rsplit('-', 1)[0])
        with self.condition:
            if self.closed:return
            if key not in self.pending and len(self.pending) >= self.maximum:
                self.error = 'queue_full'
                return  # Terminal persistence remains mandatory and independent.
            self.pending[key] = artifact
            self.condition.notify()

    def check(self):
        if self.closed:raise InterruptedError('live artifact transfer closed')

    def close(self):
        with self.condition:
            if self.closed:return
            self.closed = True
            self.pending.clear()
            self.condition.notify()
        self.thread.join(timeout=.1)

    def _run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda:self.pending or self.closed)
                if self.closed:return
                _, artifact = self.pending.popitem(last=False)
            try:
                self.check()
                self.transfer(artifact, self.check)
            except Exception as error:
                # A single best-effort live transfer; never retry until deadline.
                self.error = type(error).__name__
                if not (isinstance(error, InterruptedError) and self.closed):
                    logging.getLogger(__name__).warning(
                        'Incremental artifact transfer failed; exception_type=%s; origin=%s',
                        type(error).__name__, native_failure_origin(error))
