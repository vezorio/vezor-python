"""Clerk authentication client for the Vezor CLI/SDK.

Talks to the Clerk Frontend API directly over HTTP (no Clerk SDK), mirroring
the pattern used by the Twickets Flutter app:

  * Sign in:  POST /v1/client/sign_ins  (strategy=password)
      - Clerk may require an email code as a second factor for untrusted
        devices; that is handled via prepare_second_factor /
        attempt_second_factor.
  * Sign up:  POST /v1/client/sign_ups, then prepare_verification /
        attempt_verification with an email code.
  * Tokens:   POST /v1/client/sessions/<session_id>/tokens mints a fresh,
        short-lived (60s) session JWT. The long-lived credential is the
        client token (the __client JWT) returned in the Authorization
        response header -- THAT is what gets persisted, never a session JWT.

Clerk rotates the client token; every response's Authorization header is
captured so callers can re-persist it.
"""

import base64

import requests

CLERK_JS_VERSION = '5'
USER_AGENT = 'vezor-cli/2.0.0'


class ClerkAuthError(Exception):
    """A Clerk Frontend API request failed."""
    pass


class ClerkSessionExpiredError(ClerkAuthError):
    """Clerk definitively rejected the stored session (revoked/expired).

    The user must run 'vezor login' again. Transient network errors are
    raised as plain exceptions, not this.
    """
    pass


def derive_frontend_api(publishable_key: str) -> str:
    """Derive the Frontend API domain from a Clerk publishable key.

    Key format is pk_test_<base64-of-domain$> or pk_live_<base64-of-domain$>.
    """
    if not publishable_key or '_' not in publishable_key:
        raise ValueError(f"Invalid Clerk publishable key: {publishable_key!r}")
    encoded = publishable_key.rsplit('_', 1)[1]
    padded = encoded + '=' * (-len(encoded) % 4)
    try:
        domain = base64.b64decode(padded).decode('utf-8')
    except Exception:
        raise ValueError(f"Invalid Clerk publishable key: {publishable_key!r}")
    return domain.rstrip('$')


class ClerkAuthClient:
    """Clerk authentication client for CLI use.

    Args:
        frontend_api: Clerk Frontend API domain (e.g. 'clerk.vezor.io' or
            'xxxx.clerk.accounts.dev'). May include an https:// prefix.
        publishable_key: Alternative to frontend_api; the domain is derived
            from the key (pk_live_/pk_test_ base64 encoding).
        client_token: Previously persisted Clerk client token (__client JWT),
            if any. Sending it lets Clerk recognize a trusted device and skip
            the second-factor email code.
        session_id: Previously persisted Clerk session id, if any.
    """

    def __init__(self, frontend_api: str = None, publishable_key: str = None,
                 client_token: str = None, session_id: str = None):
        if not frontend_api and publishable_key:
            frontend_api = derive_frontend_api(publishable_key)
        if not frontend_api:
            raise ValueError("A Clerk frontend_api domain or publishable_key is required")
        self.frontend_api = frontend_api.replace('https://', '').replace('http://', '').strip('/')
        self.client_token = client_token
        self.session_id = session_id
        self._sign_in_id = None
        self._sign_up_id = None

    # ------------------------------------------------------------------ #
    # HTTP plumbing
    # ------------------------------------------------------------------ #

    def _post(self, path: str, params: dict = None):
        """POST form-encoded params to the Clerk Frontend API.

        Sends the current client token in the Authorization header and
        captures the (possibly rotated) client token from the response's
        Authorization header.

        Returns:
            (status_code, parsed_json_body)
        """
        url = f'https://{self.frontend_api}/v1{path}'
        headers = {
            'Accept': 'application/json',
            'User-Agent': USER_AGENT,
        }
        if self.client_token:
            headers['Authorization'] = self.client_token

        resp = requests.post(
            url,
            params={'_clerk_js_version': CLERK_JS_VERSION},
            data=params or {},
            headers=headers,
            timeout=30,
        )

        # Clerk rotates the client token; always capture the latest one.
        rotated = resp.headers.get('Authorization')
        if rotated:
            self.client_token = rotated

        try:
            body = resp.json()
        except ValueError:
            body = {}
        return resp.status_code, body

    @staticmethod
    def _clerk_error_message(body: dict, default: str = 'Request failed') -> str:
        errors = body.get('errors') or []
        if errors:
            first = errors[0]
            return first.get('long_message') or first.get('message') or default
        return default

    def _extract_session(self, body: dict) -> dict:
        """Pull the active session out of a completed sign-in/sign-up response.

        The session id and (short-lived) last_active_token JWT live under
        body['client']['sessions'][0].
        """
        client = body.get('client') or {}
        sessions = client.get('sessions') or []
        session = sessions[0] if sessions else None
        if not session or not session.get('id'):
            raise ClerkAuthError('Authentication completed but no session was created')

        self.session_id = session['id']
        jwt = (session.get('last_active_token') or {}).get('jwt')
        user = session.get('user') or {}
        email = None
        for addr in user.get('email_addresses') or []:
            if addr.get('id') == user.get('primary_email_address_id'):
                email = addr.get('email_address')
                break

        return {
            'session_id': self.session_id,
            'client_token': self.client_token,
            'access_token': jwt,  # short-lived (60s) -- do NOT persist
            'user': {
                'id': user.get('id'),
                'email': email,
            },
        }

    # ------------------------------------------------------------------ #
    # Sign in
    # ------------------------------------------------------------------ #

    def sign_in(self, email: str, password: str) -> dict:
        """Sign in with email and password.

        POSTs /v1/client/sign_ins with identifier + strategy=password.
        Clerk may require an email code as a second factor for untrusted
        devices; in that case the code email is triggered here
        (prepare_second_factor) and the caller must follow up with
        verify_email_code().

        Returns:
            {'status': 'needs_second_factor'} when a code is required, or
            {'status': 'complete', 'session': {...}} on full sign-in.

        Raises:
            ClerkAuthError: If sign in fails.
        """
        payload = {
            'identifier': email,
            'strategy': 'password',
            'password': password,
        }
        status_code, body = self._post('/client/sign_ins', payload)

        if status_code != 200 and self.client_token:
            # A stale client token can cause rejection -- drop it and retry.
            self.client_token = None
            status_code, body = self._post('/client/sign_ins', payload)

        if status_code != 200:
            raise ClerkAuthError(f"Sign in failed: {self._clerk_error_message(body)}")

        sign_in = body.get('response') or {}
        if sign_in.get('status') == 'needs_second_factor':
            # Password verified; Clerk wants an email code for this device.
            self._sign_in_id = sign_in.get('id')
            if not self._sign_in_id:
                raise ClerkAuthError('Sign-in response missing ID')

            prep_status, prep_body = self._post(
                f'/client/sign_ins/{self._sign_in_id}/prepare_second_factor',
                {'strategy': 'email_code'},
            )
            if prep_status != 200:
                raise ClerkAuthError(
                    f"Sign in failed: {self._clerk_error_message(prep_body)}")
            return {'status': 'needs_second_factor'}

        session = self._extract_session(body)
        return {'status': 'complete', 'session': session, 'user': session['user']}

    def verify_email_code(self, code: str) -> dict:
        """Complete a pending sign-in with the emailed second-factor code.

        POSTs /v1/client/sign_ins/<id>/attempt_second_factor.

        Returns:
            {'status': 'complete', 'session': {...}}

        Raises:
            ClerkAuthError: If verification fails or no sign-in is pending.
        """
        if not self._sign_in_id:
            raise ClerkAuthError('No pending sign-in to verify')

        status_code, body = self._post(
            f'/client/sign_ins/{self._sign_in_id}/attempt_second_factor',
            {'strategy': 'email_code', 'code': code.strip()},
        )
        if status_code != 200:
            raise ClerkAuthError(
                f"Verification failed: {self._clerk_error_message(body)}")

        self._sign_in_id = None
        session = self._extract_session(body)
        return {'status': 'complete', 'session': session, 'user': session['user']}

    # ------------------------------------------------------------------ #
    # Sign up
    # ------------------------------------------------------------------ #

    def sign_up(self, email: str, password: str, code_prompt=None) -> dict:
        """Sign up with email and password.

        POSTs /v1/client/sign_ups, then handles Clerk's required email
        verification: prepare_verification (strategy=email_code) triggers the
        email, and the code is collected interactively (via code_prompt or
        stdin) and submitted with attempt_verification.

        Args:
            email: User email.
            password: User password.
            code_prompt: Optional zero-arg callable returning the emailed
                verification code. Defaults to interactive input().

        Returns:
            {'user': {...}, 'session': {...}}

        Raises:
            ClerkAuthError: If sign up or verification fails.
        """
        status_code, body = self._post('/client/sign_ups', {
            'email_address': email,
            'password': password,
        })
        if status_code != 200 and self.client_token:
            self.client_token = None
            status_code, body = self._post('/client/sign_ups', {
                'email_address': email,
                'password': password,
            })
        if status_code != 200:
            raise ClerkAuthError(f"Sign up failed: {self._clerk_error_message(body)}")

        sign_up = body.get('response') or {}
        self._sign_up_id = sign_up.get('id')

        if sign_up.get('status') != 'complete':
            if not self._sign_up_id:
                raise ClerkAuthError('Sign-up response missing ID')

            # Trigger the verification email.
            prep_status, prep_body = self._post(
                f'/client/sign_ups/{self._sign_up_id}/prepare_verification',
                {'strategy': 'email_code'},
            )
            if prep_status != 200:
                raise ClerkAuthError(
                    f"Sign up failed: {self._clerk_error_message(prep_body)}")

            if code_prompt is None:
                def code_prompt():
                    return input(f"Enter the verification code sent to {email}: ")
            code = str(code_prompt()).strip()

            status_code, body = self._post(
                f'/client/sign_ups/{self._sign_up_id}/attempt_verification',
                {'strategy': 'email_code', 'code': code},
            )
            if status_code != 200:
                raise ClerkAuthError(
                    f"Email verification failed: {self._clerk_error_message(body)}")

        self._sign_up_id = None
        session = self._extract_session(body)
        return {'user': session['user'], 'session': session}

    # ------------------------------------------------------------------ #
    # Tokens / session
    # ------------------------------------------------------------------ #

    def get_token(self) -> str:
        """Mint a fresh short-lived session JWT for API requests.

        POSTs /v1/client/sessions/<session_id>/tokens authenticated with the
        client token. Clerk session JWTs expire after 60 seconds, so call
        this before every backend request rather than caching long-term.

        Returns:
            The session JWT string.

        Raises:
            ClerkSessionExpiredError: If Clerk rejected the session
                (401/403/404) -- the user must sign in again.
            ClerkAuthError: On other failures.
        """
        if not self.session_id or not self.client_token:
            raise ClerkAuthError('Not signed in (missing session or client token)')

        status_code, body = self._post(
            f'/client/sessions/{self.session_id}/tokens', {})

        if status_code == 200:
            jwt = body.get('jwt')
            if not jwt:
                raise ClerkAuthError('Token response missing JWT')
            return jwt
        if status_code in (401, 403, 404):
            raise ClerkSessionExpiredError(
                f'Session revoked by Clerk (HTTP {status_code})')
        raise ClerkAuthError(
            f"Token refresh failed: {self._clerk_error_message(body)}")

    def get_session(self) -> dict:
        """Get the current session with a freshly minted access token.

        Returns:
            {'access_token': <fresh 60s JWT>, 'session_id': ...,
             'client_token': ...} or None if unavailable.
        """
        try:
            jwt = self.get_token()
        except Exception:
            return None
        return {
            'access_token': jwt,
            'session_id': self.session_id,
            'client_token': self.client_token,
        }

    def sign_out(self):
        """Revoke the current session (POST /v1/client/sessions/<id>/remove).

        The client token is kept so Clerk continues to recognize this device
        and can skip the second-factor email code on the next sign-in.

        Raises:
            ClerkAuthError: If the revoke request fails.
        """
        if not self.session_id or not self.client_token:
            self.session_id = None
            return
        status_code, body = self._post(
            f'/client/sessions/{self.session_id}/remove', {})
        self.session_id = None
        if status_code != 200:
            raise ClerkAuthError(
                f"Sign out failed: {self._clerk_error_message(body)}")
