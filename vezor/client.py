"""
Vezor SDK Client

A Python client for interacting with the Vezor secrets management API.

Example:
    from vezor import VezorClient

    client = VezorClient(
        base_url="https://api.vezor.io",
        token="your-api-token",
        organization_id="your-org-id"
    )

    # List secrets
    secrets = client.list_secrets(tags={"env": "prod"})

    # Get a specific secret
    secret = client.get_secret("secret-uuid")
    print(secret["value"])

    # Create a new secret
    client.create_secret(
        key_name="DATABASE_URL",
        value="postgres://...",
        tags={"env": "prod", "app": "api"}
    )
"""

import requests
from typing import Optional, Dict, Any, List
from urllib.parse import quote

from .exceptions import raise_for_status, VezorError

# SDK version for User-Agent header
SDK_VERSION = "2.0.0"
USER_AGENT = f"vezor-python/{SDK_VERSION}"


class VezorClient:
    """
    Client for interacting with the Vezor API.

    Args:
        base_url: Base URL of the Vezor API (e.g., "https://api.vezor.io")
        token: API authentication token (Supabase JWT or API key)
        organization_id: Organization UUID for multi-tenant operations

    Example:
        >>> client = VezorClient("https://api.vezor.io", token="...", organization_id="...")
        >>> secrets = client.list_secrets()
    """

    def __init__(
        self,
        base_url: str,
        token: Optional[str] = None,
        organization_id: Optional[str] = None
    ):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.organization_id = organization_id
        self.session = requests.Session()

        # Always set User-Agent for SDK tracking
        self.session.headers.update({'User-Agent': USER_AGENT})

        if token:
            self.session.headers.update({'Authorization': f'Bearer {token}'})
        if organization_id:
            self.session.headers.update({'X-Organization-Id': organization_id})

    def set_token(self, token: str) -> None:
        """
        Set or update the authentication token.

        Args:
            token: API authentication token
        """
        self.token = token
        self.session.headers.update({'Authorization': f'Bearer {token}'})

    def set_organization(self, organization_id: str) -> None:
        """
        Set or update the organization context.

        Args:
            organization_id: Organization UUID
        """
        self.organization_id = organization_id
        self.session.headers.update({'X-Organization-Id': organization_id})

    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Make an API request with error handling.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            **kwargs: Additional arguments passed to requests

        Returns:
            requests.Response object

        Raises:
            VezorAuthError: If authentication fails
            VezorNotFoundError: If resource not found
            VezorAPIError: For other API errors
        """
        url = f'{self.base_url}{endpoint}'
        response = self.session.request(method, url, **kwargs)
        raise_for_status(response)
        return response

    # ============ Health ============

    def health(self) -> Dict[str, Any]:
        """
        Check API health status.

        Returns:
            Dict with health status information
        """
        return self._request('GET', '/api/v1/health').json()

    # ============ Organizations ============

    def list_organizations(self) -> Dict[str, Any]:
        """
        List organizations the authenticated user belongs to.

        Returns:
            Dict with 'organizations' list
        """
        return self._request('GET', '/api/v1/organizations').json()

    def get_organization(self, org_id: str) -> Dict[str, Any]:
        """
        Get organization details by ID.

        Args:
            org_id: Organization UUID

        Returns:
            Dict with organization details
        """
        return self._request('GET', f'/api/v1/organizations/{org_id}').json()

    def create_organization(self, name: str, description: str = '') -> Dict[str, Any]:
        """
        Create a new organization.

        Args:
            name: Organization name
            description: Optional description

        Returns:
            Dict with created organization details
        """
        return self._request('POST', '/api/v1/organizations', json={
            'name': name,
            'description': description
        }).json()

    # ============ Secrets ============

    def list_secrets(
        self,
        tags: Optional[Dict[str, str]] = None,
        search: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        List secrets with optional filtering, search, and pagination.

        Args:
            tags: Filter by tags (e.g., {"env": "prod", "app": "api"})
            search: Search query for key_name (case-insensitive)
            limit: Maximum number of results to return
            offset: Pagination offset

        Returns:
            Dict with:
                - secrets: List of secret objects
                - count: Number of secrets in this page
                - total: Total matching secrets
                - limit: Applied limit
                - offset: Applied offset

        Example:
            >>> # Get all production secrets
            >>> result = client.list_secrets(tags={"env": "prod"})
            >>> for secret in result["secrets"]:
            ...     print(secret["key_name"])
        """
        params = {}
        if tags:
            params.update(tags)
        if search:
            params['search'] = search
        if limit:
            params['limit'] = limit
        params['offset'] = offset

        return self._request('GET', '/api/v1/secrets', params=params).json()

    def get_secret(self, secret_id: str, version: Optional[int] = None) -> Dict[str, Any]:
        """
        Get a secret by ID, optionally at a specific version.

        Args:
            secret_id: Secret UUID
            version: Optional version number (defaults to latest)

        Returns:
            Dict with secret details including:
                - id: Secret UUID
                - key_name: Secret key name
                - value: Decrypted secret value
                - version: Current version number
                - tags: Dict of tags
                - description: Optional description

        Example:
            >>> secret = client.get_secret("abc-123")
            >>> print(secret["value"])

            >>> # Get a specific version
            >>> old_secret = client.get_secret("abc-123", version=2)
        """
        params = {}
        if version is not None:
            params['version'] = version
        return self._request('GET', f'/api/v1/secrets/{secret_id}', params=params).json()

    def get_secret_by_name(
        self,
        key_name: str,
        tags: Optional[Dict[str, str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get a secret by key name and optional tags.

        This is a convenience method that searches for a secret by name
        and returns the first match.

        Args:
            key_name: Secret key name (e.g., "DATABASE_URL")
            tags: Optional tag filters to narrow search

        Returns:
            Secret dict if found, None otherwise

        Example:
            >>> secret = client.get_secret_by_name("DATABASE_URL", tags={"env": "prod"})
            >>> if secret:
            ...     print(secret["value"])
        """
        result = self.list_secrets(tags=tags, search=key_name, limit=100)
        for secret in result.get('secrets', []):
            if secret['key_name'].lower() == key_name.lower():
                return self.get_secret(secret['id'])
        return None

    def create_secret(
        self,
        key_name: str,
        value: str,
        tags: Dict[str, str],
        description: str = '',
        value_type: str = 'string',
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Create a new secret.

        Args:
            key_name: Secret key name (e.g., "DATABASE_URL")
            value: Secret value
            tags: Required tags dict (should include 'env' and 'app')
            description: Optional human-readable description
            value_type: Type hint - "string", "password", "url", "connection_string"
            metadata: Optional metadata dict

        Returns:
            Dict with created secret details

        Example:
            >>> client.create_secret(
            ...     key_name="DATABASE_URL",
            ...     value="postgres://user:pass@host:5432/db",
            ...     tags={"env": "prod", "app": "api"},
            ...     description="Main PostgreSQL database connection"
            ... )
        """
        data = {
            'key_name': key_name,
            'value': value,
            'tags': tags,
            'path': key_name.lower(),
        }
        if description:
            data['description'] = description
        if value_type:
            data['value_type'] = value_type
        if metadata:
            data['metadata'] = metadata

        return self._request('POST', '/api/v1/secrets', json=data).json()

    def update_secret(
        self,
        secret_id: str,
        value: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Update an existing secret.

        Updating the value creates a new version. Previous versions are
        preserved and can be retrieved using get_secret(id, version=N).

        Args:
            secret_id: Secret UUID
            value: New secret value (creates new version)
            description: New description
            tags: New tags dict

        Returns:
            Dict with updated secret details

        Example:
            >>> client.update_secret("abc-123", value="new-password")
        """
        data = {}
        if value is not None:
            data['value'] = value
        if description is not None:
            data['description'] = description
        if tags is not None:
            data['tags'] = tags

        return self._request('PUT', f'/api/v1/secrets/{secret_id}', json=data).json()

    def delete_secret(self, secret_id: str) -> Dict[str, Any]:
        """
        Delete a secret and all its versions.

        Args:
            secret_id: Secret UUID

        Returns:
            Dict with deletion confirmation
        """
        return self._request('DELETE', f'/api/v1/secrets/{secret_id}').json()

    def get_secret_versions(self, secret_id: str) -> Dict[str, Any]:
        """
        Get version history for a secret.

        Args:
            secret_id: Secret UUID

        Returns:
            Dict with 'versions' list containing version metadata

        Example:
            >>> versions = client.get_secret_versions("abc-123")
            >>> for v in versions["versions"]:
            ...     print(f"v{v['version']} by {v['created_by']} at {v['created_at']}")
        """
        return self._request('GET', f'/api/v1/secrets/{secret_id}/versions').json()

    # ============ Tags ============

    def get_tags(self) -> Dict[str, Any]:
        """
        Get available tags grouped by key.

        Returns:
            Dict with tag keys as keys and list of values as values

        Example:
            >>> tags = client.get_tags()
            >>> print(tags)
            {"env": ["dev", "staging", "prod"], "app": ["api", "web"]}
        """
        return self._request('GET', '/api/v1/tags').json()

    # ============ Import/Export ============

    def export_env(self, tags: Optional[Dict[str, str]] = None) -> str:
        """
        Export secrets as .env format.

        Args:
            tags: Optional tag filters

        Returns:
            String in .env format (KEY=value lines)

        Example:
            >>> env_content = client.export_env(tags={"env": "prod", "app": "api"})
            >>> with open(".env", "w") as f:
            ...     f.write(env_content)
        """
        params = tags if tags else {}
        response = self._request('GET', '/api/v1/export', params=params)
        return response.text

    def import_env(self, environment: str, env_content: str) -> Dict[str, Any]:
        """
        Import secrets from .env format.

        Args:
            environment: Target environment (e.g., "development")
            env_content: .env file content as string

        Returns:
            Dict with import results

        Example:
            >>> with open(".env") as f:
            ...     content = f.read()
            >>> client.import_env("development", content)
        """
        response = self._request(
            'POST',
            f'/api/v1/import/{environment}',
            data=env_content,
            headers={'Content-Type': 'text/plain'}
        )
        return response.json()

    # ============ Groups ============

    def list_groups(self) -> Dict[str, Any]:
        """
        List all secret groups in the organization.

        Groups are predefined tag combinations for organizing secrets.

        Returns:
            Dict with 'groups' list
        """
        return self._request('GET', '/api/v1/groups').json()

    def get_group(self, name: str) -> Dict[str, Any]:
        """
        Get a group by name.

        Args:
            name: Group name

        Returns:
            Dict with group details including tags
        """
        return self._request('GET', f'/api/v1/groups/{quote(name, safe="")}').json()

    def get_group_secret_count(self, name: str) -> Dict[str, Any]:
        """
        Get count of secrets matching a group's tags.

        Args:
            name: Group name

        Returns:
            Dict with 'count' field
        """
        return self._request('GET', f'/api/v1/groups/{quote(name, safe="")}/count').json()

    def pull_group_secrets(self, name: str, format: str = 'json') -> Any:
        """
        Pull all secrets matching a group's tags.

        Args:
            name: Group name
            format: Output format - "json", "env", or "export"

        Returns:
            For "json": Dict with group name, tags, secrets, and count
            For "env"/"export": String in .env format

        Example:
            >>> # Get as dict
            >>> secrets = client.pull_group_secrets("production-api")
            >>> for key, value in secrets["secrets"].items():
            ...     print(f"{key}={value}")

            >>> # Get as .env string
            >>> env_content = client.pull_group_secrets("production-api", format="env")
        """
        response = self._request(
            'GET',
            f'/api/v1/groups/{quote(name, safe="")}/secrets',
            params={'format': format}
        )
        if format in ('env', 'export'):
            return response.text
        return response.json()

    # ============ Validation ============

    def validate_schema(self, schema_content: str, environment: str = 'development') -> Dict[str, Any]:
        """
        Validate a schema against stored secrets.

        Args:
            schema_content: YAML schema content as string
            environment: Environment to validate against

        Returns:
            Dict with validation results including any missing secrets
        """
        return self._request('POST', '/api/v1/validate', json={
            'schema': schema_content,
            'environment': environment
        }).json()

    # ============ Audit ============

    def get_audit_log(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """
        Get audit log entries.

        Args:
            limit: Maximum entries to return
            offset: Pagination offset

        Returns:
            Dict with 'entries' list containing audit records
        """
        return self._request('GET', '/api/v1/audit', params={
            'limit': limit,
            'offset': offset
        }).json()


# Backwards compatibility alias
VezorAPIClient = VezorClient
