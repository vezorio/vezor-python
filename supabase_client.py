import os
from supabase import create_client, Client


class SupabaseAuthClient:
    """Supabase authentication client for CLI"""

    def __init__(self, url: str = None, anon_key: str = None):
        """
        Initialize Supabase client

        Args:
            url: Supabase project URL
            anon_key: Supabase anon key
        """
        self.url = url or os.getenv('SUPABASE_URL')
        self.anon_key = anon_key or os.getenv('SUPABASE_ANON_KEY')

        if not self.url or not self.anon_key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY are required")

        self.client: Client = create_client(self.url, self.anon_key)

    def sign_in(self, email: str, password: str) -> dict:
        """
        Sign in with email and password

        Args:
            email: User email
            password: User password

        Returns:
            Authentication response with session and user data

        Raises:
            Exception: If sign in fails
        """
        try:
            response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            if response.session:
                return {
                    'session': {
                        'access_token': response.session.access_token,
                        'refresh_token': response.session.refresh_token,
                        'expires_at': response.session.expires_at,
                        'expires_in': response.session.expires_in
                    },
                    'user': {
                        'id': response.user.id,
                        'email': response.user.email,
                        'user_metadata': response.user.user_metadata
                    }
                }
            else:
                raise Exception("No session returned from Supabase")

        except Exception as e:
            raise Exception(f"Sign in failed: {str(e)}")

    def sign_up(self, email: str, password: str, metadata: dict = None) -> dict:
        """
        Sign up with email and password

        Args:
            email: User email
            password: User password
            metadata: Optional user metadata (e.g., role)

        Returns:
            Authentication response

        Raises:
            Exception: If sign up fails
        """
        try:
            options = {}
            if metadata:
                options['data'] = metadata

            response = self.client.auth.sign_up({
                "email": email,
                "password": password,
                **options
            })

            return {
                'user': {
                    'id': response.user.id if response.user else None,
                    'email': response.user.email if response.user else None
                },
                'session': {
                    'access_token': response.session.access_token if response.session else None,
                    'refresh_token': response.session.refresh_token if response.session else None
                } if response.session else None
            }

        except Exception as e:
            raise Exception(f"Sign up failed: {str(e)}")

    def sign_out(self):
        """Sign out current user"""
        try:
            self.client.auth.sign_out()
        except Exception as e:
            raise Exception(f"Sign out failed: {str(e)}")

    def get_session(self) -> dict:
        """
        Get current session

        Returns:
            Current session data or None
        """
        try:
            response = self.client.auth.get_session()
            if response:
                return {
                    'access_token': response.access_token,
                    'refresh_token': response.refresh_token,
                    'expires_at': response.expires_at
                }
            return None
        except Exception:
            return None

    def refresh_session(self, refresh_token: str) -> dict:
        """
        Refresh session using refresh token

        Args:
            refresh_token: Refresh token

        Returns:
            New session data

        Raises:
            Exception: If refresh fails
        """
        try:
            response = self.client.auth.refresh_session(refresh_token)

            if response.session:
                return {
                    'access_token': response.session.access_token,
                    'refresh_token': response.session.refresh_token,
                    'expires_at': response.session.expires_at
                }
            else:
                raise Exception("No session returned from Supabase")

        except Exception as e:
            raise Exception(f"Session refresh failed: {str(e)}")
