import os
import keyring
from pathlib import Path


class CLIConfig:
    """Configuration management for Vezor CLI"""

    SERVICE_NAME = 'vezor'
    TOKEN_KEY = 'api_token'
    SUPABASE_URL_KEY = 'supabase_url'
    SUPABASE_ANON_KEY_KEY = 'supabase_anon_key'
    URL_KEY = 'api_url'

    # Hardcoded Supabase configuration (anon key is public, not sensitive)
    DEFAULT_SUPABASE_URL = 'https://zdtmkvbyucguhrfcrcac.supabase.co'
    DEFAULT_SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpkdG1rdmJ5dWNndWhyZmNyY2FjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjU1NzY5OTMsImV4cCI6MjA4MTE1Mjk5M30.CnDhOtNrqCdysvOnbSzg1Ch0RQmwj0nXh4Ice9C__zc'
    DEFAULT_API_URL = 'https://api.vezor.io'
    CONFIG_FILE = Path.home() / '.vezor' / 'config'

    @classmethod
    def get_token(cls) -> str:
        """Get stored API token from keychain"""
        try:
            token = keyring.get_password(cls.SERVICE_NAME, cls.TOKEN_KEY)
            return token
        except Exception:
            return None

    @classmethod
    def set_token(cls, token: str):
        """Store API token in keychain"""
        try:
            keyring.set_password(cls.SERVICE_NAME, cls.TOKEN_KEY, token)
        except Exception as e:
            raise RuntimeError(f"Failed to store token in keychain: {str(e)}")

    @classmethod
    def delete_token(cls):
        """Delete API token from keychain"""
        try:
            keyring.delete_password(cls.SERVICE_NAME, cls.TOKEN_KEY)
        except Exception:
            pass

    @classmethod
    def get_supabase_url(cls) -> str:
        """Get Supabase URL from environment or config"""
        # Check environment variable first
        env_url = os.environ.get('SUPABASE_URL')
        if env_url:
            return env_url

        # Check config file
        config_value = cls._get_config_value('supabase_url')
        if config_value:
            return config_value

        # Return hardcoded default
        return cls.DEFAULT_SUPABASE_URL

    @classmethod
    def set_supabase_url(cls, url: str):
        """Store Supabase URL in config file"""
        cls._set_config_value('supabase_url', url)

    @classmethod
    def get_supabase_anon_key(cls) -> str:
        """Get Supabase anon key from environment or config"""
        # Check environment variable first
        env_key = os.environ.get('SUPABASE_ANON_KEY')
        if env_key:
            return env_key

        # Check config file
        config_value = cls._get_config_value('supabase_anon_key')
        if config_value:
            return config_value

        # Return hardcoded default
        return cls.DEFAULT_SUPABASE_ANON_KEY

    @classmethod
    def set_supabase_anon_key(cls, key: str):
        """Store Supabase anon key in config file"""
        cls._set_config_value('supabase_anon_key', key)

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
        return cls.get_token() is not None

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
