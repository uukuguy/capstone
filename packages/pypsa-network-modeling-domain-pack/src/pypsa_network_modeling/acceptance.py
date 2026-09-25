"""Provider-free acceptance declarations for the modeling Pack."""

from __future__ import annotations


class ModelAcceptanceProfile:
    def offline_cases(self) -> tuple[object, ...]:
        return ("pypsa-model-profile",)

    def scripted_cases(self) -> tuple[object, ...]:
        return ("pypsa-model-current-run",)

    def provider_cases(self) -> tuple[object, ...]:
        return ()
