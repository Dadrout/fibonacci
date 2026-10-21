"""Compatibility import for the application's Supabase access-token verifier."""

from app.api.dependencies import get_current_user

__all__ = ["get_current_user"]
