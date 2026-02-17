import hmac
import os
from typing import Optional

from fastapi import Header, HTTPException, status


def verify_admin_token(x_admin_token: Optional[str] = Header(None)) -> None:
    """
    Verify admin token for protected endpoints.
    This middleware function checks if the provided admin token matches
    the configured ADMIN_TOKEN environment variable.
    Args:
            x_admin_token: Admin token from X-Admin-Token header
    Raises:
            HTTPException: If authentication fails
    """
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADMIN_TOKEN not configured",
        )
    if not x_admin_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not hmac.compare_digest(x_admin_token, admin_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_admin(x_admin_token: Optional[str] = Header(None)) -> Optional[str]:
    """
    Get current admin user from token.
    Args:
            x_admin_token: Admin token from X-Admin-Token header
    Returns:
            Admin user identifier or None if not authenticated
    Raises:
            HTTPException: If authentication fails
    """
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADMIN_TOKEN not configured",
        )
    if not x_admin_token or not hmac.compare_digest(x_admin_token, admin_token):
        return None
    return "admin"


class AdminAuthMiddleware:
    """
    Middleware class for admin authentication.
    Can be used as a dependency in FastAPI routes.
    """

    def __init__(self):
        self.admin_token = os.getenv("ADMIN_TOKEN")
        if not self.admin_token:
            raise RuntimeError("ADMIN_TOKEN environment variable is required")

    def verify(self, token: Optional[str]) -> bool:
        """
        Verify admin token.
        Args:
                token: Admin token to verify
        Returns:
                True if token is valid, False otherwise
        """
        if not token:
            return False
        return hmac.compare_digest(token, self.admin_token)

    def __call__(self, x_admin_token: Optional[str] = Header(None)) -> None:
        """
        Verify admin token as a callable dependency.
        Args:
                x_admin_token: Admin token from X-Admin-Token header
        Raises:
                HTTPException: If authentication fails
        """
        if not x_admin_token or not self.verify(x_admin_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin token",
                headers={"WWW-Authenticate": "Bearer"},
            )
