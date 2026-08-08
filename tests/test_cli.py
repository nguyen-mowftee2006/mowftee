"""Unit tests for minimal terminal CLI runner."""

from __future__ import annotations

import io
from collections.abc import Iterator

import pytest

from mowftee.cli import main, run_interactive_chat
from mowftee.conversation import ConversationManager
from mowftee.llm.base import (
    ChatMessage,
    LLMMetrics,
    LLMProvider,
    LLMResponse,
    LLMResponseError,
    LLMStreamChunk,
)


class DummyCLIProvider(LLMProvider):
    """Dummy provider for CLI unit tests."""

    def __init__(self, healthy: bool = True) -> None:
        self._healthy = healthy

    def health_check(self) -> bool:
        return self._healthy

    def chat(self, messages: list[ChatMessage], request_id: str | None = None) -> LLMResponse:
        return LLMResponse(content="CLI reply", model="m")

    def stream_chat(self, messages: list[ChatMessage], request_id: str | None = None) -> Iterator[LLMStreamChunk]:
        yield LLMStreamChunk(delta="CLI ", done=False, model="m", request_id=request_id or "dummy")
        yield LLMStreamChunk(delta="reply", done=True, model="m", request_id=request_id or "dummy")

    def cancel(self, request_id: str) -> bool:
        return True

    def get_metrics(self) -> LLMMetrics:
        return LLMMetrics()


def test_cli_runner_exit_command() -> None:
    provider = DummyCLIProvider()
    manager = ConversationManager(provider)
    out = io.StringIO()

    inputs = iter(["/exit"])
    run_interactive_chat(manager, input_fn=lambda: next(inputs), output_stream=out)

    output = out.getvalue()
    assert "Mowftee Terminal Chat" in output
    assert "[Thoát ứng dụng]" in output


def test_cli_runner_clear_and_chat_flow() -> None:
    provider = DummyCLIProvider()
    manager = ConversationManager(provider)
    out = io.StringIO()

    inputs = iter(["Chào bạn", "/clear", "/quit"])
    run_interactive_chat(manager, input_fn=lambda: next(inputs), output_stream=out)

    output = out.getvalue()
    assert "CLI reply" in output
    assert "[Đã xoá lịch sử hội thoại]" in output
    assert len(manager.get_history()) == 0


def test_cli_runner_handles_error() -> None:
    class FailingProvider(DummyCLIProvider):
        def stream_chat(self, messages: list[ChatMessage], request_id: str | None = None) -> Iterator[LLMStreamChunk]:
            raise LLMResponseError("Service error")

    provider = FailingProvider()
    manager = ConversationManager(provider)
    out = io.StringIO()

    inputs = iter(["Test error", "/exit"])
    run_interactive_chat(manager, input_fn=lambda: next(inputs), output_stream=out)

    output = out.getvalue()
    assert "[Lỗi hội thoại: Service error]" in output


def test_main_cli_health_check_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("mowftee.cli.OllamaLLMProvider", lambda cfg: DummyCLIProvider(healthy=False))
    err_out = io.StringIO()
    monkeypatch.setattr("sys.stderr", err_out)

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    assert "health_check = False" in err_out.getvalue()
