from __future__ import annotations

from mowftee.llm.base import (
    ChatMessage,
    LLMCancelledError,
    LLMConnectionError,
    LLMError,
    LLMMetrics,
    LLMProvider,
    LLMResponse,
    LLMResponseError,
    LLMStreamChunk,
    LLMTimeoutError,
)


def test_chat_message_dataclass() -> None:
    msg = ChatMessage(role="user", content="Xin chào")
    assert msg.role == "user"
    assert msg.content == "Xin chào"


def test_llm_metrics_default_values() -> None:
    metrics = LLMMetrics()
    assert metrics.total_requests == 0
    assert metrics.successful_requests == 0
    assert metrics.failed_requests == 0
    assert metrics.total_prompt_tokens == 0
    assert metrics.total_eval_tokens == 0
    assert metrics.last_ttft_seconds == 0.0
    assert metrics.last_tokens_per_second == 0.0


def test_llm_response_dataclass() -> None:
    resp = LLMResponse(
        content="Mowftee nè",
        model="qwen3:4b-instruct",
        request_id="req-123",
        eval_count=15,
    )
    assert resp.content == "Mowftee nè"
    assert resp.model == "qwen3:4b-instruct"
    assert resp.request_id == "req-123"
    assert resp.eval_count == 15
    assert resp.finish_reason is None


def test_llm_stream_chunk_dataclass_contains_request_id() -> None:
    chunk = LLMStreamChunk(
        delta="Xin",
        done=False,
        model="qwen3:4b-instruct",
        request_id="req-456",
    )
    assert chunk.delta == "Xin"
    assert chunk.done is False
    assert chunk.model == "qwen3:4b-instruct"
    assert chunk.request_id == "req-456"
    assert chunk.metrics is None


def test_llm_error_hierarchy() -> None:
    assert issubclass(LLMConnectionError, LLMError)
    assert issubclass(LLMTimeoutError, LLMError)
    assert issubclass(LLMResponseError, LLMError)
    assert issubclass(LLMCancelledError, LLMError)


def test_llm_provider_protocol_is_type_checkable() -> None:
    class DummyProvider:
        def chat(
            self,
            messages: list[ChatMessage],
            model: str | None = None,
            options: dict[str, object] | None = None,
            request_id: str | None = None,
        ) -> LLMResponse:
            return LLMResponse(content="", model="")

        def stream_chat(
            self,
            messages: list[ChatMessage],
            model: str | None = None,
            options: dict[str, object] | None = None,
            request_id: str | None = None,
        ):
            yield LLMStreamChunk(delta="", done=True, model="", request_id="")

        def health_check(self) -> bool:
            return True

        def get_metrics(self) -> LLMMetrics:
            return LLMMetrics()

        def cancel(self, request_id: str) -> bool:
            return True

    dummy = DummyProvider()
    assert isinstance(dummy, LLMProvider)
