"""Bounded operator labels for registered authority model metadata."""


def model_display_name(title: str, model_id: str) -> str:
    """Retain short names; use the exact registered ID for descriptive titles."""
    name = title.strip()
    return name if name and len(name) <= 80 and "\n" not in name else model_id
