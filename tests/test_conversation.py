"""Comprehensive unit tests for Mowftee Conversation Manager."""

from __future__ import annotations

import contextlib
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from mowftee.conversation import (
    ConversationBusyError,
    ConversationError,
    ConversationManager,
)
from mowftee.llm.base import (
    ChatMessage,
    LLMCancelledError,
    LLMError,
    LLMMetrics,
    LLMProvider,
    LLMResponse,
    LLMResponseError,
    LLMStreamChunk,
    LLMTimeoutError,
)


class DummyLLMProvider(LLMProvider):
    """Deterministic dummy provider for testing ConversationManager."""

    def __init__(
        self,
        response_text: str = "Assistant response",
        should_fail: Exception | None = None,
        stream_chunks: list[LLMStreamChunk] | None = None,
    ) -> None:
        self.response_text = response_text
        self.should_fail = should_fail
        self.stream_chunks = stream_chunks
        self.last_received_messages: list[ChatMessage] = []
        self.last_received_request_id: str | None = None
        self.cancelled_request_ids: set[str] = set()
        self.block_event: threading.Event | None = None
        self.unblock_event: threading.Event | None = None

    def health_check(self) -> bool:
        return True

    def chat(
        self,
        messages: list[ChatMessage],
        request_id: str | None = None,
    ) -> LLMResponse:
        self.last_received_messages = list(messages)
        self.last_received_request_id = request_id

        if self.block_event is not None and self.unblock_event is not None:
            self.block_event.set()
            self.unblock_event.wait(timeout=2.0)

        if self.should_fail:
            raise self.should_fail

        return LLMResponse(
            content=self.response_text,
            model="dummy-model",
            request_id=request_id or "dummy-req",
            prompt_eval_count=10,
            eval_count=5,
            total_duration_ns=100000000,
            load_duration_ns=10000000,
            prompt_eval_duration_ns=40000000,
            eval_duration_ns=50000000,
        )

    def stream_chat(
        self,
        messages: list[ChatMessage],
        request_id: str | None = None,
    ) -> Iterator[LLMStreamChunk]:
        self.last_received_messages = list(messages)
        self.last_received_request_id = request_id

        if self.block_event is not None and self.unblock_event is not None:
            self.block_event.set()
            self.unblock_event.wait(timeout=2.0)

        if request_id and request_id in self.cancelled_request_ids:
            raise LLMCancelledError("Stream cancelled")

        if self.should_fail:
            raise self.should_fail

        chunks = self.stream_chunks or [
            LLMStreamChunk(delta="Hello ", done=False, model="dummy-model", request_id=request_id),
            LLMStreamChunk(delta="world!", done=True, model="dummy-model", request_id=request_id),
        ]

        for chunk in chunks:
            if request_id and request_id in self.cancelled_request_ids:
                raise LLMCancelledError("Stream cancelled")
            yield chunk

    def cancel(self, request_id: str) -> bool:
        self.cancelled_request_ids.add(request_id)
        if self.unblock_event:
            self.unblock_event.set()
        return True

    def get_metrics(self) -> LLMMetrics:
        return LLMMetrics()


def test_conversation_exceptions_hierarchy() -> None:
    assert issubclass(ConversationError, Exception)
    assert issubclass(ConversationBusyError, ConversationError)

    err = ConversationBusyError("Conversation turn already active")
    assert isinstance(err, ConversationError)
    assert str(err) == "Conversation turn already active"


def test_constructor_and_default_config() -> None:
    provider = DummyLLMProvider()
    manager = ConversationManager(provider)

    assert isinstance(manager.session_id, str)
    assert len(manager.session_id) > 0
    assert manager.get_history() == []


def test_constructor_validation() -> None:
    with pytest.raises(ValueError, match="Provider must be an LLMProvider"):
        ConversationManager(None)  # type: ignore[arg-type]


def test_session_id_isolation() -> None:
    provider = DummyLLMProvider()
    m1 = ConversationManager(provider)
    m2 = ConversationManager(provider)

    assert m1.session_id != m2.session_id
    sid = m1.session_id
    assert m1.session_id == sid


def test_custom_system_prompt() -> None:
    provider = DummyLLMProvider()
    manager = ConversationManager(
        provider,
        system_prompt="Custom system prompt",
    )
    manager.chat("Hello")
    messages = provider.last_received_messages
    assert messages[0] == ChatMessage(role="system", content="Custom system prompt")


def test_chat_success_and_atomic_history_commit() -> None:
    provider = DummyLLMProvider(response_text="General Kenobi!")
    manager = ConversationManager(provider, system_prompt="SysPrompt")

    reply = manager.chat("Hello there", request_id="req-123")
    assert reply == "General Kenobi!"
    assert provider.last_received_request_id == "req-123"

    history = manager.get_history()
    assert len(history) == 2
    assert history[0] == ChatMessage(role="user", content="Hello there")
    assert history[1] == ChatMessage(role="assistant", content="General Kenobi!")


def test_multi_turn_history() -> None:
    provider = DummyLLMProvider(response_text="Response")
    manager = ConversationManager(provider)

    manager.chat("Turn 1")
    manager.chat("Turn 2")

    history = manager.get_history()
    assert len(history) == 4
    assert history[0].content == "Turn 1"
    assert history[1].content == "Response"
    assert history[2].content == "Turn 2"
    assert history[3].content == "Response"


def test_provider_error_preserves_history_and_raises_exact_exception() -> None:
    exc = LLMTimeoutError("Request timed out")
    provider = DummyLLMProvider(should_fail=exc)
    manager = ConversationManager(provider)

    with pytest.raises(LLMTimeoutError) as exc_info:
        manager.chat("Failing request")

    assert exc_info.value is exc
    assert manager.get_history() == []


def test_blank_or_invalid_user_input_rejected() -> None:
    provider = DummyLLMProvider()
    manager = ConversationManager(provider)

    with pytest.raises(ValueError, match="non-empty string"):
        manager.chat("")

    with pytest.raises(ValueError, match="non-empty string"):
        manager.chat("   \n\t ")

    with pytest.raises(ValueError, match="non-empty string"):
        manager.chat(123)  # type: ignore[arg-type]

    assert manager.get_history() == []


def test_get_history_snapshot_isolation() -> None:
    provider = DummyLLMProvider()
    manager = ConversationManager(provider)
    manager.chat("Hello")

    history1 = manager.get_history()
    history1.clear()

    history2 = manager.get_history()
    assert len(history2) == 2


def test_clear_history_when_idle() -> None:
    provider = DummyLLMProvider()
    manager = ConversationManager(provider, system_prompt="Preserved prompt")
    manager.chat("Hello")

    assert len(manager.get_history()) == 2
    manager.clear_history()
    assert len(manager.get_history()) == 0

    # System prompt remains in assembled messages after clear
    manager.chat("World")
    assert provider.last_received_messages[0] == ChatMessage(role="system", content="Preserved prompt")


def test_concurrency_turn_already_active_and_clear_history_busy() -> None:
    provider = DummyLLMProvider()
    provider.block_event = threading.Event()
    provider.unblock_event = threading.Event()
    manager = ConversationManager(provider)

    # Start blocking chat turn in thread
    t = threading.Thread(target=manager.chat, args=("Block msg",), kwargs={"request_id": "block-req"})
    t.start()

    provider.block_event.wait(timeout=2.0)

    # Simultaneous chat, stream_chat, or clear_history must raise ConversationBusyError
    with pytest.raises(ConversationBusyError, match="turn already active"):
        manager.chat("Concurrent msg")

    with pytest.raises(ConversationBusyError, match="turn already active"):
        gen = manager.stream_chat("Concurrent stream")
        next(gen)

    with pytest.raises(ConversationBusyError, match="turn is active"):
        manager.clear_history()

    # Unblock first turn
    provider.unblock_event.set()
    t.join(timeout=2.0)

    # Active state cleared
    assert len(manager.get_history()) == 2


def test_max_turns_selects_recent_pairs_only() -> None:
    provider = DummyLLMProvider(response_text="ans")
    config = {"conversation": {"default_system_prompt": "Sys", "max_turns": 2, "inject_datetime": False}}
    manager = ConversationManager(provider, config=config)

    for i in range(1, 5):
        manager.chat(f"u{i}")

    # Stored history has 4 pairs (8 messages)
    assert len(manager.get_history()) == 8

    # Context for 5th turn should have Sys + last 2 pairs (u3, ans, u4, ans) + pending u5
    manager.chat("u5")
    sent = provider.last_received_messages
    assert len(sent) == 6  # 1 sys + 4 history + 1 pending user
    assert sent[0] == ChatMessage(role="system", content="Sys")
    assert sent[1] == ChatMessage(role="user", content="u3")
    assert sent[2] == ChatMessage(role="assistant", content="ans")
    assert sent[3] == ChatMessage(role="user", content="u4")
    assert sent[4] == ChatMessage(role="assistant", content="ans")
    assert sent[5] == ChatMessage(role="user", content="u5")


def test_datetime_injection_and_mock_clock() -> None:
    fixed_time = datetime(2026, 8, 8, 14, 30, 0, tzinfo=UTC)
    provider = DummyLLMProvider()
    config = {"conversation": {"default_system_prompt": "Sys", "max_turns": 10, "inject_datetime": True}}
    manager = ConversationManager(provider, config=config, clock_fn=lambda: fixed_time)

    manager.chat("Hello")
    sent = provider.last_received_messages

    assert len(sent) == 3
    assert sent[0] == ChatMessage(role="system", content="Sys")
    assert sent[1] == ChatMessage(role="system", content="Thời gian hiện tại: 2026-08-08T14:30:00+00:00")
    assert sent[2] == ChatMessage(role="user", content="Hello")

    # Datetime is not stored in committed history
    hist = manager.get_history()
    assert len(hist) == 2
    assert hist[0] == ChatMessage(role="user", content="Hello")


def test_inject_datetime_false() -> None:
    provider = DummyLLMProvider()
    config = {"conversation": {"default_system_prompt": "Sys", "max_turns": 10, "inject_datetime": False}}
    manager = ConversationManager(provider, config=config)

    manager.chat("Hello")
    sent = provider.last_received_messages
    assert len(sent) == 2
    assert sent[0] == ChatMessage(role="system", content="Sys")
    assert sent[1] == ChatMessage(role="user", content="Hello")


def test_stream_chat_lazy_execution_and_success_commit() -> None:
    provider = DummyLLMProvider(
        stream_chunks=[
            LLMStreamChunk(delta="A", done=False, model="m", request_id="r1"),
            LLMStreamChunk(delta="B", done=True, model="m", request_id="r1"),
        ]
    )
    manager = ConversationManager(provider)

    # Calling stream_chat returns generator without invoking provider
    gen = manager.stream_chat("Stream user msg", request_id="r1")
    assert provider.last_received_request_id is None
    assert manager.get_history() == []

    # First iteration starts execution
    chunks = list(gen)
    assert len(chunks) == 2
    assert provider.last_received_request_id == "r1"

    # Committed history has atomic user + full assistant
    hist = manager.get_history()
    assert len(hist) == 2
    assert hist[0] == ChatMessage(role="user", content="Stream user msg")
    assert hist[1] == ChatMessage(role="assistant", content="AB")


def test_stream_chat_failure_leaves_history_unchanged() -> None:
    provider = DummyLLMProvider(should_fail=LLMResponseError("Malformed stream"))
    manager = ConversationManager(provider)

    gen = manager.stream_chat("Stream fail")
    with pytest.raises(LLMResponseError, match="Malformed stream"):
        next(gen)

    assert manager.get_history() == []


def test_early_generator_close_calls_cancel_and_clears_active_state() -> None:
    provider = DummyLLMProvider(
        stream_chunks=[
            LLMStreamChunk(delta="Part 1 ", done=False, model="m", request_id="req-close"),
            LLMStreamChunk(delta="Part 2 ", done=False, model="m", request_id="req-close"),
            LLMStreamChunk(delta="Part 3", done=True, model="m", request_id="req-close"),
        ]
    )
    manager = ConversationManager(provider)

    gen = manager.stream_chat("Early close msg", request_id="req-close")
    chunk1 = next(gen)
    assert chunk1.delta == "Part 1 "

    # Close generator early
    gen.close()

    assert "req-close" in provider.cancelled_request_ids
    assert manager.get_history() == []

    # Active state cleared, subsequent chat succeeds
    reply = manager.chat("Next turn")
    assert reply == "Assistant response"


def test_cancel_current_turn_idle_and_active() -> None:
    provider = DummyLLMProvider()
    provider.block_event = threading.Event()
    provider.unblock_event = threading.Event()
    manager = ConversationManager(provider)

    # Idle cancel returns False
    assert manager.cancel_current_turn() is False

    t = threading.Thread(target=manager.chat, args=("Block",), kwargs={"request_id": "block-req-cancel"})
    t.start()

    provider.block_event.wait(timeout=2.0)

    # Active cancel forwards request ID to provider
    assert manager.cancel_current_turn() is True
    assert "block-req-cancel" in provider.cancelled_request_ids

    provider.unblock_event.set()
    t.join(timeout=2.0)


def test_atomic_history_observation_no_half_pair() -> None:
    provider = DummyLLMProvider()
    provider.block_event = threading.Event()
    provider.unblock_event = threading.Event()
    manager = ConversationManager(provider)

    observed_history_lengths: list[int] = []

    def worker() -> None:
        manager.chat("Hello")

    t = threading.Thread(target=worker)
    t.start()

    provider.block_event.wait(timeout=2.0)
    # While provider is running inside chat call, history is read by concurrent thread
    observed_history_lengths.append(len(manager.get_history()))

    provider.unblock_event.set()
    t.join(timeout=2.0)

    observed_history_lengths.append(len(manager.get_history()))

    # At no point during provider call was history length odd (e.g. 1 half-committed message)
    assert observed_history_lengths == [0, 2]


def test_cancellation_no_deadlock_during_active_stream() -> None:
    provider = DummyLLMProvider()
    provider.block_event = threading.Event()
    provider.unblock_event = threading.Event()
    manager = ConversationManager(provider)

    stream_cancelled = threading.Event()

    def stream_worker() -> None:
        gen = manager.stream_chat("Blocked stream user", request_id="stream-deadlock-id")
        try:
            with contextlib.suppress(LLMCancelledError, LLMError):
                for _ in gen:
                    pass
        finally:
            stream_cancelled.set()

    t = threading.Thread(target=stream_worker)
    t.start()

    assert provider.block_event.wait(timeout=2.0) is True

    # Calling cancel_current_turn must return immediately without waiting for provider lock
    start_cancel = time.perf_counter()
    cancel_res = manager.cancel_current_turn()
    cancel_duration = time.perf_counter() - start_cancel

    assert cancel_res is True
    assert cancel_duration < 0.5  # Non-blocking cancel call
    assert "stream-deadlock-id" in provider.cancelled_request_ids

    t.join(timeout=2.0)
    assert stream_cancelled.is_set()
    assert manager.get_history() == []

    # Manager is idle and accepts new chat
    assert manager.chat("Fresh turn") == "Assistant response"
