from __future__ import annotations

from typing import Any


def resolve_component(component: Any) -> Any:
    """Return the underlying LiveKit client if wrapped, else the object itself.

    Many plugin wrappers expose an internal ``_client`` attribute that is the
    actual LiveKit SDK instance. This helper centralizes the logic for
    unwrapping that client when constructing an AgentSession.
    """

    if hasattr(component, "_client"):
        return getattr(component, "_client")
    return component
