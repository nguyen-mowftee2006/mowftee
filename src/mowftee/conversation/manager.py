"""Conversation Manager for Mowftee."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable, Iterator, Mapping
from datetime import datetime
from typing import Any

from mowftee.config import load_config
from mowftee.conversation.base import ConversationBusyError
from mowftee.llm.base import ChatMessage, LLMProvider, LLMStreamChunk
from mowftee.logging_setup import generate_request_id


class ConversationManager:
    """Manages multi-turn conversation sessions, context assembly, and turn lifecycle."""

    def __init__(
        self,
        provider: LLMProvider,
        config: Mapping[str, Any] | None = None,
        system_prompt: str | None = None,
        clock_fn: Callable[[], datetime] | None = None,
    ) -> None:
        if provider is None:
            raise ValueError("Provider must be an LLMProvider instance")

        resolved_config = dict(config) if config is not None else load_config()
        conversation_cfg = resolved_config.get("conversation", {})
        if not isinstance(conversation_cfg, Mapping):
            conversation_cfg = {}

        default_sys_prompt = conversation_cfg.get(
            "default_system_prompt",
            "Bạn là Mowftee, một bạn đồng hành AI bằng tiếng Việt.",
        )
        if system_prompt is not None and isinstance(system_prompt, str) and system_prompt.strip():
            self._system_prompt = system_prompt
        else:
            self._system_prompt = str(default_sys_prompt)

        max_turns_val = conversation_cfg.get("max_turns", 20)
        self._max_turns = int(max_turns_val) if isinstance(max_turns_val, int) and max_turns_val > 0 else 20

        inject_dt = conversation_cfg.get("inject_datetime", True)
        self._inject_datetime = bool(inject_dt)

        self._provider = provider
        self._clock_fn = clock_fn if clock_fn is not None else (lambda: datetime.now().astimezone())

        self._session_id = str(uuid.uuid4())
        self._committed_history: list[ChatMessage] = []
        self._active_request_id: str | None = None
        self._active_lock = threading.Lock()

    @property
    def session_id(self) -> str:
        """Return the unique session ID of this ConversationManager instance."""
        return self._session_id

    def get_history(self) -> list[ChatMessage]:
        """Return a snapshot copy of the committed session history."""
        with self._active_lock:
            return list(self._committed_history)

    def clear_history(self) -> None:
        """Clear all committed user and assistant messages in session history."""
        with self._active_lock:
            if self._active_request_id is not None:
                raise ConversationBusyError("Cannot clear history while a turn is active")
            self._committed_history.clear()

    def cancel_current_turn(self) -> bool:
        """Cancel the active turn if any, forwarding cancellation to the provider."""
        with self._active_lock:
            active_id = self._active_request_id
        if active_id is None:
            return False
        return self._provider.cancel(active_id)

    def _validate_user_message(self, user_message: str) -> None:
        if not isinstance(user_message, str) or not user_message.strip():
            raise ValueError("User message must be a non-empty string")

    def _assemble_messages(self, user_message: str) -> list[ChatMessage]:
        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=self._system_prompt)
        ]

        if self._inject_datetime:
            now_str = self._clock_fn().isoformat()
            messages.append(
                ChatMessage(role="system", content=f"Thời gian hiện tại: {now_str}")
            )

        num_messages = self._max_turns * 2
        with self._active_lock:
            recent_history = list(self._committed_history[-num_messages:]) if num_messages > 0 else []

        messages.extend(recent_history)
        messages.append(ChatMessage(role="user", content=user_message))
        return messages

    def chat(self, user_message: str, request_id: str | None = None) -> str:
        """Execute a non-streaming conversation turn."""
        self._validate_user_message(user_message)
        effective_request_id = request_id or generate_request_id()

        with self._active_lock:
            if self._active_request_id is not None:
                raise ConversationBusyError("Conversation turn already active")
            self._active_request_id = effective_request_id

        try:
            messages = self._assemble_messages(user_message)
            response = self._provider.chat(messages, request_id=effective_request_id)

            with self._active_lock:
                self._committed_history.append(ChatMessage(role="user", content=user_message))
                self._committed_history.append(ChatMessage(role="assistant", content=response.content))

            return response.content
        finally:
            with self._active_lock:
                self._active_request_id = None

    def stream_chat(
        self, user_message: str, request_id: str | None = None
    ) -> Iterator[LLMStreamChunk]:
        """Execute a streaming conversation turn lazily."""
        self._validate_user_message(user_message)
        effective_request_id = request_id or generate_request_id()

        def _generator() -> Iterator[LLMStreamChunk]:
            with self._active_lock:
                if self._active_request_id is not None:
                    raise ConversationBusyError("Conversation turn already active")
                self._active_request_id = effective_request_id

            completed_successfully = False
            accumulated_deltas: list[str] = []

            try:
                messages = self._assemble_messages(user_message)
                stream = self._provider.stream_chat(messages, request_id=effective_request_id)

                for chunk in stream:
                    if chunk.delta:
                        accumulated_deltas.append(chunk.delta)
                    if chunk.done:
                        completed_successfully = True
                        assistant_content = "".join(accumulated_deltas)
                        with self._active_lock:
                            self._committed_history.append(ChatMessage(role="user", content=user_message))
                            self._committed_history.append(ChatMessage(role="assistant", content=assistant_content))
                    yield chunk
            finally:
                if not completed_successfully:
                    self._provider.cancel(effective_request_id)
                with self._active_lock:
                    self._active_request_id = None

        return _generator()
