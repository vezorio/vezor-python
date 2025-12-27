"""
Backwards compatibility shim - import from vezor package instead.

This module is deprecated. Use:
    from vezor import VezorClient
"""

from vezor.client import VezorClient, VezorAPIClient

__all__ = ["VezorClient", "VezorAPIClient"]
