"""Inspectable acceptance inputs; these declarations do not execute tests."""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class InventoryAcceptanceCase:
    case_id: str
    mode: Literal["offline", "scripted", "provider"]
    description: str


class InventoryAcceptanceProfile:
    def offline_cases(self) -> tuple[InventoryAcceptanceCase, ...]:
        return (
            InventoryAcceptanceCase("inventory-profile", "offline", "Complete application SPI without provider calls"),
            InventoryAcceptanceCase("inventory-information", "offline", "Packaged information and limited mixed requests"),
        )

    def scripted_cases(self) -> tuple[InventoryAcceptanceCase, ...]:
        return (
            InventoryAcceptanceCase("inventory-context-reuse", "scripted", "Real catalog/assets then stock summary with retained context"),
            InventoryAcceptanceCase("inventory-evidence-boundary", "scripted", "Current-run admission rejects foreign or tampered evidence"),
            InventoryAcceptanceCase("inventory-report-isolation", "scripted", "Report publication is derived and failure-isolated"),
            InventoryAcceptanceCase("inventory-replay", "scripted", "Replay reproduces the committed application state"),
        )

    def provider_cases(self) -> tuple[InventoryAcceptanceCase, ...]:
        return (
            InventoryAcceptanceCase("inventory-provider", "provider", "Optional authorized provider uses the same real authority contract"),
        )
