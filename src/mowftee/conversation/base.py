"""Base exception hierarchy for Mowftee Conversation Manager."""

from __future__ import annotations


class ConversationError(Exception):
    """Base exception for conversation manager errors."""


class ConversationBusyError(ConversationError):
    """Raised when a new turn is attempted while another turn is active."""
