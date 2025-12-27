"""Vezor SDK Exceptions"""

import requests


class VezorError(Exception):
    """Base exception for Vezor SDK errors"""
    pass


class VezorAuthError(VezorError):
    """Authentication failed or token expired"""
    pass


class VezorNotFoundError(VezorError):
    """Resource not found (404)"""
    pass


class VezorValidationError(VezorError):
    """Validation error (400)"""
    pass


class VezorPermissionError(VezorError):
    """Permission denied (403)"""
    pass


class VezorAPIError(VezorError):
    """Generic API error with status code and response details"""

    def __init__(self, message: str, status_code: int = None, response: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


def raise_for_status(response: requests.Response) -> None:
    """
    Raise appropriate VezorError based on HTTP status code.

    Args:
        response: requests.Response object

    Raises:
        VezorAuthError: 401 Unauthorized
        VezorPermissionError: 403 Forbidden
        VezorNotFoundError: 404 Not Found
        VezorValidationError: 400 Bad Request
        VezorAPIError: Other 4xx/5xx errors
    """
    if response.ok:
        return

    try:
        error_data = response.json()
        message = error_data.get('error', error_data.get('message', response.text))
    except Exception:
        message = response.text or f"HTTP {response.status_code}"

    if response.status_code == 401:
        raise VezorAuthError(message)
    elif response.status_code == 403:
        raise VezorPermissionError(message)
    elif response.status_code == 404:
        raise VezorNotFoundError(message)
    elif response.status_code == 400:
        raise VezorValidationError(message)
    else:
        raise VezorAPIError(message, status_code=response.status_code, response=error_data if 'error_data' in dir() else None)
