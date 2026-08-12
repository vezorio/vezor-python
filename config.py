import os
import keyring
from pathlib import Path


class CLIConfig:
    """Configuration management for Vezor CLI"""

    SERVICE_NAME = 'vezor'
    # Long-lived Clerk client token (__client JWT) -- the persisted
    # credential. Clerk session JWTs expire after 60 seconds, so a fresh one
    # is minted per request instead of being stored.
    CLIENT_TOKEN_KEY = 'clerk_client_token'
    # Legacy keyring entry from the Supabase era; cleared on logout.
    LEGACY_TOKEN_KEY = 'api_token'
    URL_KEY = 'api_url'

    # Hardcoded Clerk configuration (publishable key / frontend API domain
    # are public, not sensitive).
    # PLACEHOLDERS: replace once the Clerk vezor application exists. The
    # frontend API domain can be derived from the publishable key
    # (pk_live_<base64-of-domain>) -- see clerk_client.derive_frontend_api.
    DEFAULT_CLERK_PUBLISHABLE_KEY = 'CLERK_VEZOR_PUBLISHABLE_KEY'
    DEFAULT_CLERK_FRONTEND_API = 'CLERK_VEZOR_FRONTEND_API'
    DEFAULT_API_URL = 'https://api.vezor.io'
    CONFIG_FILE = Path.home() / '.vezor' / 'config'

    @classmethod
    def get_client_token(cls) -> str:
        """Get stored Clerk client token from keychain"""
        try:
            return keyring.get_password(cls.SERVICE_NAME, cls.CLIENT_TOKEN_KEY)
        except Exception:
            return None

    @classmethod
    def set_client_token(cls, token: str):
        """Store Clerk client token in keychain"""
        try:
            keyring.set_password(cls.SERVICE_NAME, cls.CLIENT_TOKEN_KEY, token)
        except Exception as e:
            raise RuntimeError(f"Failed to store token in keychain: {str(e)}")

    @classmethod
    def delete_client_token(cls):
        """Delete Clerk client token (and any legacy token) from keychain"""
        for key in (cls.CLIENT_TOKEN_KEY, cls.LEGACY_TOKEN_KEY):
            try:
                keyring.delete_password(cls.SERVICE_NAME, key)
            except Exception:
                pass

    @classmethod
    def get_session_id(cls) -> str:
        """Get stored Clerk session ID"""
        return cls._get_config_value('clerk_session_id')

    @classmethod
    def set_session_id(cls, session_id: str):
        """Store Clerk session ID in config file"""
        cls._set_config_value('clerk_session_id', session_id)

    @classmethod
    def clear_session_id(cls):
        """Remove stored Clerk session ID"""
        if cls.CONFIG_FILE.exists():
            with open(cls.CONFIG_FILE, 'r') as f:
                lines = [line for line in f if not line.startswith('clerk_session_id=')]
            with open(cls.CONFIG_FILE, 'w') as f:
                f.writelines(lines)

    @classmethod
    def get_clerk_publishable_key(cls) -> str:
        """Get Clerk publishable key from environment or config"""
        # Check environment variable first
        env_key = os.environ.get('CLERK_PUBLISHABLE_KEY')
        if env_key:
            return env_key

        # Check config file
        config_value = cls._get_config_value('clerk_publishable_key')
        if config_value:
            return config_value

        # Return hardcoded default
        return cls.DEFAULT_CLERK_PUBLISHABLE_KEY

    @classmethod
    def set_clerk_publishable_key(cls, key: str):
        """Store Clerk publishable key in config file"""
        cls._set_config_value('clerk_publishable_key', key)

    @classmethod
    def get_clerk_frontend_api(cls) -> str:
        """Get the Clerk Frontend API domain.

        Resolution order: CLERK_FRONTEND_API env var, config file, derivation
        from the publishable key, hardcoded default.
        """
        env_domain = os.environ.get('CLERK_FRONTEND_API')
        if env_domain:
            return env_domain

        config_value = cls._get_config_value('clerk_frontend_api')
        if config_value:
            return config_value

        # Derive from the publishable key when a real one is available
        publishable_key = cls.get_clerk_publishable_key()
        if publishable_key.startswith('pk_'):
            from clerk_client import derive_frontend_api
            try:
                return derive_frontend_api(publishable_key)
            except ValueError:
                pass

        return cls.DEFAULT_CLERK_FRONTEND_API

    @classmethod
    def set_clerk_frontend_api(cls, domain: str):
        """Store Clerk Frontend API domain in config file"""
        cls._set_config_value('clerk_frontend_api', domain)

    @classmethod
    def get_api_url(cls) -> str:
        """Get API URL from config file or environment"""
        # Check environment variable first
        env_url = os.environ.get('VEZOR_API_URL')
        if env_url:
            return env_url

        # Check config file
        value = cls._get_config_value('api_url')
        return value if value else cls.DEFAULT_API_URL

    @classmethod
    def set_api_url(cls, url: str):
        """Store API URL in config file"""
        cls._set_config_value('api_url', url)

    @classmethod
    def _get_config_value(cls, key: str) -> str:
        """Get a value from config file"""
        if cls.CONFIG_FILE.exists():
            try:
                with open(cls.CONFIG_FILE, 'r') as f:
                    for line in f:
                        if line.startswith(f'{key}='):
                            return line.split('=', 1)[1].strip()
            except Exception:
                pass
        return None

    @classmethod
    def _set_config_value(cls, key: str, value: str):
        """Set a value in config file"""
        cls.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Read existing config
        lines = []
        if cls.CONFIG_FILE.exists():
            with open(cls.CONFIG_FILE, 'r') as f:
                lines = [line for line in f if not line.startswith(f'{key}=')]

        # Add new value
        lines.append(f'{key}={value}\n')

        # Write config
        with open(cls.CONFIG_FILE, 'w') as f:
            f.writelines(lines)

    @classmethod
    def is_authenticated(cls) -> bool:
        """Check if user is authenticated"""
        return cls.get_client_token() is not None and cls.get_session_id() is not None

    @classmethod
    def get_organization_id(cls) -> str:
        """Get current organization ID"""
        return cls._get_config_value('organization_id')

    @classmethod
    def set_organization_id(cls, org_id: str):
        """Set current organization ID"""
        cls._set_config_value('organization_id', org_id)

    @classmethod
    def get_organization_name(cls) -> str:
        """Get current organization name (for display)"""
        return cls._get_config_value('organization_name')

    @classmethod
    def set_organization_name(cls, name: str):
        """Set current organization name"""
        cls._set_config_value('organization_name', name)

    @classmethod
    def clear_organization(cls):
        """Clear organization context"""
        # Remove org lines from config
        if cls.CONFIG_FILE.exists():
            with open(cls.CONFIG_FILE, 'r') as f:
                lines = [line for line in f if not line.startswith('organization_')]
            with open(cls.CONFIG_FILE, 'w') as f:
                f.writelines(lines)
