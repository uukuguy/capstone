"""Neutral validation and projection helpers for registered model identities."""

from __future__ import annotations

import re
from hashlib import sha256
from typing import TypeGuard


# A model may use one authority namespace segment, e.g.
# ``pypsa-example/scigrid_de``.  The slash is an identity separator, never a
# filesystem path; callers must use ``page_id_for_model`` for page keys.
MODEL_ID_PATTERN = re.compile(
    r"^(?:[A-Za-z][A-Za-z0-9_-]{0,63}|[a-z][a-z0-9_-]{0,63}/[a-z0-9][a-z0-9._-]{0,63})$"
)


def is_valid_model_id(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and MODEL_ID_PATTERN.fullmatch(value) is not None


def validate_model_id(value: object, *, name: str = "model_id") -> str:
    if not is_valid_model_id(value):
        raise ValueError(f"{name} is invalid")
    return value


def page_id_for_model(model_id: str) -> str:
    """Return a stable page key that cannot create a nested path."""

    validated = validate_model_id(model_id)
    readable = "page_" + validated.replace("/", "__")
    if "__" not in validated and re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", readable):
        return readable
    # The double underscore after the prefix cannot come from a model's
    # leading letter. It keeps hashed keys separate from readable page keys.
    return "page__" + sha256(validated.encode("utf-8")).hexdigest()[:40]


__all__ = [
    "MODEL_ID_PATTERN",
    "is_valid_model_id",
    "page_id_for_model",
    "validate_model_id",
]
