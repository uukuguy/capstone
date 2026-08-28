from typing import Protocol


class CapabilityExecutor(Protocol):
    def invoke(
        self, capability: str, arguments: dict[str, object]
    ) -> dict[str, object]: ...
