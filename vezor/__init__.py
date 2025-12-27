"""
Vezor SDK - GitOps-native secrets management

A Python SDK for interacting with the Vezor secrets management platform.

Quick Start:
    from vezor import VezorClient

    client = VezorClient(
        base_url="https://api.vezor.io",
        token="your-api-token",
        organization_id="your-org-uuid"
    )

    # List all secrets
    secrets = client.list_secrets()

    # Get a specific secret by name
    secret = client.get_secret_by_name("DATABASE_URL", tags={"env": "prod"})

    # Create a new secret
    client.create_secret(
        key_name="API_KEY",
        value="secret-value",
        tags={"env": "prod", "app": "api"}
    )

For full documentation, see: https://github.com/vezor/vezor-python
"""

__version__ = "2.0.0"
__author__ = "Vezor Team"

from .client import VezorClient, VezorAPIClient
from .exceptions import (
    VezorError,
    VezorAuthError,
    VezorNotFoundError,
    VezorValidationError,
    VezorPermissionError,
    VezorAPIError,
)

__all__ = [
    # Main client
    "VezorClient",
    "VezorAPIClient",  # Backwards compatibility alias
    # Exceptions
    "VezorError",
    "VezorAuthError",
    "VezorNotFoundError",
    "VezorValidationError",
    "VezorPermissionError",
    "VezorAPIError",
    # Metadata
    "__version__",
]
