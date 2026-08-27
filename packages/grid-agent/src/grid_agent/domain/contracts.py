from typing import Protocol


class CapabilityContractSource(Protocol):
    def load(self) -> tuple[dict[str, object], ...]: ...
