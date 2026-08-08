"""Base types, exceptions, and protocol for Mowftee LLM Providers."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


class LLMError(Exception):
    """Base exception for LLM provider errors."""


class LLMConnectionError(LLMError):
    """Raised when connection to LLM service fails."""


class LLMTimeoutError(LLMError):
    """Raised when an LLM request or stream read times out."""


class LLMResponseError(LLMError):
    """Raised when LLM service returns an HTTP error or malformed payload."""


class LLMCancelledError(LLMError):
    """Raised when an LLM request is cancelled by caller."""


@dataclass(frozen=True)
class ChatMessage:
    """Represents a single conversation message."""

    role: str
    content: str


@dataclass
class LLMMetrics:
    """Cumulative performance metrics for an LLM provider instance."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_prompt_tokens: int = 0
    total_eval_tokens: int = 0
    last_ttft_seconds: float = 0.0
    last_tokens_per_second: float = 0.0


@dataclass(frozen=True)
class LLMResponse:
    """Complete response returned by non-streaming chat."""

    content: str
    model: str
    finish_reason: str | None = None
    request_id: str = ""
    prompt_eval_count: int = 0
    eval_count: int = 0
    total_duration_ns: int = 0
    load_duration_ns: int = 0
    prompt_eval_duration_ns: int = 0
    eval_duration_ns: int = 0


@dataclass(frozen=True)
class LLMStreamChunk:
    """Incremental chunk yielded during streaming chat."""

    delta: str
    done: bool
    model: str
    request_id: str
    finish_reason: str | None = None
    metrics: LLMMetrics | None = None


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol defining the required public capability for LLM Providers."""

    def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        options: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> LLMResponse:
        ...

    def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        options: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> Iterator[LLMStreamChunk]:
        ...

    def health_check(self) -> bool:
        ...

    def get_metrics(self) -> LLMMetrics:
        ...

    def cancel(self, request_id: str) -> bool:
        ...
