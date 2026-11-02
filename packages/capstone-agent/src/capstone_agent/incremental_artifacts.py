"""One coalesced file capture worker per active native task; no timer polling."""
from threading import Condition, Event, Thread

from .general_pi_executor import collect_artifacts


class IncrementalArtifacts:
    def __init__(self, *, workspace, request, identity, storage, publish):
        self.workspace, self.request = workspace, request
        self.identity, self.storage, self.publish = identity, storage, publish
        self.condition = Condition()
        self.cancel = Event()
        self.pending = self.stopping = False
        self.fingerprints, self.seen = {}, set()
        self.error = None
        self.thread = Thread(target=self._run, daemon=True)
        self.thread.start()

    def trigger(self):
        with self.condition:
            if not self.stopping:
                self.pending = True
                self.condition.notify()

    def close(self):
        with self.condition:
            self.stopping = True
            self.pending = False
            self.cancel.set()
            self.condition.notify()
        self.thread.join(timeout=.1)

    def check(self):
        if self.cancel.is_set():raise InterruptedError('incremental capture closed')

    def _run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.pending or self.stopping)
                if not self.pending:
                    return
                self.pending = False
            try:
                fingerprints = {}
                artifacts = collect_artifacts(self.workspace, self.request.task_id,
                    self.request.parent_attempt_id, unchanged=self.fingerprints, fingerprints=fingerprints, check=self.check)
                for artifact in artifacts:
                    self.check()
                    if artifact['artifact_id'] not in self.seen:
                        self.storage.capture_artifact(self.request.task_id, self.workspace, artifact, check=self.check)
                        self.check()
                        self.publish({'type':'native_artifact_captured',
                            'schema':'capstone-pi-artifact-capture/1', 'task_id':self.request.task_id,
                            'parent_attempt_id':self.request.parent_attempt_id,
                            'executor_identity':dict(self.identity), 'artifact':artifact})
                        self.seen.add(artifact['artifact_id'])
                    path = artifact['metadata']['path']
                    self.fingerprints[path] = fingerprints[path]
                self.error = None
            except Exception as error:
                # A live writer can race a capture. Keep prior committed versions;
                # the next tool completion can try again. Final capture is mandatory.
                self.error = type(error).__name__
