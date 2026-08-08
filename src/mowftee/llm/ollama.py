"""Ollama LLM Provider implementation for Mowftee."""

from __future__ import annotations

import contextlib
import dataclasses
import json
import socket
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator, Mapping
from typing import Any

from mowftee.llm.base import (
    ChatMessage,
    LLMCancelledError,
    LLMConnectionError,
    LLMMetrics,
    LLMResponse,
    LLMResponseError,
    LLMStreamChunk,
    LLMTimeoutError,
)
from mowftee.logging_setup import (
    generate_request_id,
    get_logger,
    get_request_id,
    request_context,
)

_app_logger = get_logger(channel="app")
_perf_logger = get_logger(channel="performance")
_audit_logger = get_logger(channel="audit")


def _parse_non_negative_int(data: dict[str, Any], field_name: str) -> int:
    value = data.get(field_name)
    if value is None:
        return 0
    if type(value) is not int or isinstance(value, bool) or value < 0:
        raise LLMResponseError(
            f"Field '{field_name}' in Ollama response must be a non-negative integer"
        )
    return value


class OllamaLLMProvider:
    """LLM Provider communicating with a local Ollama instance via HTTP REST API."""

    def __init__(self, config: Mapping[str, Any]) -> None:
        llm_config = config.get("llm", {})
        if not isinstance(llm_config, Mapping):
            raise TypeError("llm configuration section must be a mapping")

        self._model = str(llm_config.get("model", "qwen3:4b-instruct")).strip()
        base_url = str(llm_config.get("base_url", "http://127.0.0.1:11434")).strip()
        self._base_url = base_url.rstrip("/")
        self._timeout = float(llm_config.get("timeout", 30.0))
        self._health_timeout = float(llm_config.get("health_timeout", 2.0))

        self._metrics_lock = threading.Lock()
        self._metrics = LLMMetrics()

        self._registry_lock = threading.Lock()
        self._active_requests: dict[str, Any] = {}
        self._cancelled_requests: set[str] = set()

    def health_check(self) -> bool:
        """Check availability of Ollama service via GET /api/version."""

        url = f"{self._base_url}/api/version"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self._health_timeout) as response:
                if response.status != 200:
                    return False
                payload = json.loads(response.read().decode("utf-8"))
                return (
                    isinstance(payload, dict)
                    and "version" in payload
                    and bool(str(payload["version"]).strip())
                )
        except (
            OSError,
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            ValueError,
            json.JSONDecodeError,
        ):
            return False

    def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        options: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> LLMResponse:
        """Execute a non-streaming chat request against Ollama POST /api/chat."""

        if not messages:
            raise ValueError("messages must not be empty")

        for idx, msg in enumerate(messages):
            if not isinstance(msg.role, str) or not msg.role.strip():
                raise ValueError(f"Message at index {idx} has invalid role")
            if not isinstance(msg.content, str):
                raise TypeError(f"Message at index {idx} has non-string content")

        effective_model = model.strip() if model and model.strip() else self._model
        if not effective_model:
            raise ValueError("Effective model must not be empty")

        effective_request_id = request_id or get_request_id() or generate_request_id()

        with request_context(effective_request_id):
            start_time = time.perf_counter()
            _audit_logger.info(
                "llm_chat_start",
                extra={
                    "event": "llm_chat",
                    "metadata": {
                        "provider": "ollama",
                        "model": effective_model,
                        "request_id": effective_request_id,
                    },
                },
            )

            payload: dict[str, Any] = {
                "model": effective_model,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "stream": False,
            }
            if options is not None:
                payload["options"] = options

            url = f"{self._base_url}/api/chat"
            encoded_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=encoded_data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            response: Any = None
            success = False
            cancelled = False

            try:
                try:
                    response = urllib.request.urlopen(req, timeout=self._timeout)
                except TimeoutError as exc:
                    raise LLMTimeoutError("Ollama chat request timed out") from exc
                except urllib.error.HTTPError as exc:
                    raise LLMResponseError(f"Ollama returned HTTP error {exc.code}") from exc
                except urllib.error.URLError as exc:
                    if (
                        isinstance(exc.reason, (socket.timeout, TimeoutError))
                        or "timed out" in str(exc.reason).lower()
                    ):
                        raise LLMTimeoutError("Ollama chat request timed out") from exc
                    raise LLMConnectionError("Failed to connect to Ollama service") from exc

                self._register_response(effective_request_id, response)

                try:
                    raw_bytes = response.read()
                    data = json.loads(raw_bytes.decode("utf-8"))
                except (UnicodeError, json.JSONDecodeError) as err:
                    with self._registry_lock:
                        if effective_request_id in self._cancelled_requests:
                            cancelled = True
                            raise LLMCancelledError("Request was cancelled") from err
                    raise LLMResponseError("Malformed JSON response from Ollama") from err
                except (OSError, urllib.error.URLError) as err:
                    with self._registry_lock:
                        if effective_request_id in self._cancelled_requests:
                            cancelled = True
                            raise LLMCancelledError("Request was cancelled") from err
                    raise LLMConnectionError("Failed to read from Ollama service") from err

                if not isinstance(data, dict):
                    raise LLMResponseError("Ollama response must be a JSON object")

                resp_message = data.get("message")
                if not isinstance(resp_message, dict):
                    raise LLMResponseError("Missing or invalid 'message' in Ollama response")

                content = resp_message.get("content")
                if not isinstance(content, str):
                    raise LLMResponseError("Missing or invalid 'content' in Ollama message")

                resp_model = data.get("model")
                if not isinstance(resp_model, str) or not resp_model.strip():
                    raise LLMResponseError("Missing or invalid 'model' in Ollama response")

                finish_reason = data.get("done_reason")
                if finish_reason is not None and not isinstance(finish_reason, str):
                    finish_reason = str(finish_reason)

                prompt_eval_count = _parse_non_negative_int(data, "prompt_eval_count")
                eval_count = _parse_non_negative_int(data, "eval_count")
                total_duration_ns = _parse_non_negative_int(data, "total_duration")
                load_duration_ns = _parse_non_negative_int(data, "load_duration")
                prompt_eval_duration_ns = _parse_non_negative_int(data, "prompt_eval_duration")
                eval_duration_ns = _parse_non_negative_int(data, "eval_duration")

                duration_sec = time.perf_counter() - start_time
                tok_per_sec = (
                    eval_count / (eval_duration_ns / 1e9) if eval_duration_ns > 0 else 0.0
                )

                self._record_metrics(
                    success=True,
                    prompt_tokens=prompt_eval_count,
                    eval_tokens=eval_count,
                    tok_per_sec=tok_per_sec,
                )
                success = True

                _perf_logger.info(
                    "llm_chat_performance",
                    extra={
                        "event": "llm_performance",
                        "duration_ms": duration_sec * 1000.0,
                        "metadata": {
                            "prompt_eval_count": prompt_eval_count,
                            "eval_count": eval_count,
                            "tokens_per_second": tok_per_sec,
                        },
                    },
                )
                _app_logger.info("Ollama LLM chat request succeeded")

                return LLMResponse(
                    content=content,
                    model=resp_model,
                    finish_reason=finish_reason,
                    request_id=effective_request_id,
                    prompt_eval_count=prompt_eval_count,
                    eval_count=eval_count,
                    total_duration_ns=total_duration_ns,
                    load_duration_ns=load_duration_ns,
                    prompt_eval_duration_ns=prompt_eval_duration_ns,
                    eval_duration_ns=eval_duration_ns,
                )

            except Exception:
                with self._registry_lock:
                    if effective_request_id in self._cancelled_requests:
                        cancelled = True
                self._record_metrics(success=False)
                if cancelled:
                    _app_logger.info("Ollama LLM chat request cancelled")
                    raise LLMCancelledError("Request was cancelled")
                raise
            finally:
                self._unregister_response(effective_request_id, response)
                _audit_logger.info(
                    "llm_chat_end",
                    extra={
                        "event": "llm_chat_end",
                        "metadata": {
                            "provider": "ollama",
                            "model": effective_model,
                            "request_id": effective_request_id,
                            "success": success,
                            "cancelled": cancelled,
                        },
                    },
                )

    def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        options: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> Iterator[LLMStreamChunk]:
        """Execute a streaming chat request against Ollama POST /api/chat with 'stream': true."""

        if not messages:
            raise ValueError("messages must not be empty")

        for idx, msg in enumerate(messages):
            if not isinstance(msg.role, str) or not msg.role.strip():
                raise ValueError(f"Message at index {idx} has invalid role")
            if not isinstance(msg.content, str):
                raise TypeError(f"Message at index {idx} has non-string content")

        effective_model = model.strip() if model and model.strip() else self._model
        if not effective_model:
            raise ValueError("Effective model must not be empty")

        effective_request_id = request_id or get_request_id() or generate_request_id()

        def _generator() -> Iterator[LLMStreamChunk]:
            with request_context(effective_request_id):
                start_time = time.perf_counter()
                _audit_logger.info(
                    "llm_stream_chat_start",
                    extra={
                        "event": "llm_stream_chat",
                        "metadata": {
                            "provider": "ollama",
                            "model": effective_model,
                            "request_id": effective_request_id,
                        },
                    },
                )

                payload: dict[str, Any] = {
                    "model": effective_model,
                    "messages": [{"role": m.role, "content": m.content} for m in messages],
                    "stream": True,
                }
                if options is not None:
                    payload["options"] = options

                url = f"{self._base_url}/api/chat"
                encoded_data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=encoded_data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )

                response: Any = None
                success = False
                cancelled = False
                stream_model: str | None = None
                first_token_time: float | None = None
                ttft_sec = 0.0

                try:
                    try:
                        response = urllib.request.urlopen(req, timeout=self._timeout)
                    except TimeoutError as exc:
                        raise LLMTimeoutError("Ollama stream request timed out") from exc
                    except urllib.error.HTTPError as exc:
                        raise LLMResponseError(f"Ollama returned HTTP error {exc.code}") from exc
                    except urllib.error.URLError as exc:
                        if (
                            isinstance(exc.reason, (socket.timeout, TimeoutError))
                            or "timed out" in str(exc.reason).lower()
                        ):
                            raise LLMTimeoutError("Ollama stream request timed out") from exc
                        raise LLMConnectionError("Failed to connect to Ollama service") from exc

                    self._register_response(effective_request_id, response)

                    while True:
                        with self._registry_lock:
                            if effective_request_id in self._cancelled_requests:
                                cancelled = True
                                raise LLMCancelledError("Stream request was cancelled")

                        try:
                            line = response.readline()
                        except TimeoutError as exc:
                            with self._registry_lock:
                                if effective_request_id in self._cancelled_requests:
                                    cancelled = True
                                    raise LLMCancelledError("Stream request was cancelled") from exc
                            raise LLMTimeoutError("Ollama stream read timed out") from exc
                        except (OSError, urllib.error.URLError) as exc:
                            with self._registry_lock:
                                if effective_request_id in self._cancelled_requests:
                                    cancelled = True
                                    raise LLMCancelledError("Stream request was cancelled") from exc
                            raise LLMConnectionError("Failed to read from Ollama stream") from exc

                        if not line:
                            raise LLMResponseError(
                                "Ollama stream ended prematurely without completion chunk"
                            )

                        line_str = line.decode("utf-8").strip()
                        if not line_str:
                            continue

                        try:
                            chunk_data = json.loads(line_str)
                        except json.JSONDecodeError as err:
                            raise LLMResponseError("Malformed NDJSON in Ollama stream") from err

                        if not isinstance(chunk_data, dict):
                            raise LLMResponseError("Stream chunk must be a JSON object")

                        chunk_model = chunk_data.get("model")
                        if not isinstance(chunk_model, str) or not chunk_model.strip():
                            raise LLMResponseError("Missing or invalid 'model' in stream chunk")

                        if stream_model is None:
                            stream_model = chunk_model
                        elif chunk_model != stream_model:
                            raise LLMResponseError(
                                f"Model mismatch in stream chunks: expected '{stream_model}', got '{chunk_model}'"
                            )

                        is_done = chunk_data.get("done") is True

                        if not is_done:
                            resp_message = chunk_data.get("message")
                            if not isinstance(resp_message, dict):
                                raise LLMResponseError("Missing or invalid 'message' in stream chunk")
                            delta = resp_message.get("content")
                            if not isinstance(delta, str):
                                raise LLMResponseError("Missing or invalid 'content' in stream message")

                            if delta != "" and first_token_time is None:
                                first_token_time = time.perf_counter()
                                ttft_sec = first_token_time - start_time

                            yield LLMStreamChunk(
                                delta=delta,
                                done=False,
                                model=stream_model,
                                request_id=effective_request_id,
                                finish_reason=None,
                                metrics=None,
                            )
                        else:
                            finish_reason = chunk_data.get("done_reason")
                            if finish_reason is not None and not isinstance(finish_reason, str):
                                finish_reason = str(finish_reason)

                            resp_message = chunk_data.get("message")
                            delta = ""
                            if isinstance(resp_message, dict) and isinstance(resp_message.get("content"), str):
                                delta = resp_message["content"]
                                if delta != "" and first_token_time is None:
                                    first_token_time = time.perf_counter()
                                    ttft_sec = first_token_time - start_time

                            prompt_eval_count = _parse_non_negative_int(chunk_data, "prompt_eval_count")
                            eval_count = _parse_non_negative_int(chunk_data, "eval_count")
                            eval_duration_ns = _parse_non_negative_int(chunk_data, "eval_duration")

                            duration_sec = time.perf_counter() - start_time
                            tok_per_sec = (
                                eval_count / (eval_duration_ns / 1e9) if eval_duration_ns > 0 else 0.0
                            )

                            self._record_metrics(
                                success=True,
                                prompt_tokens=prompt_eval_count,
                                eval_tokens=eval_count,
                                tok_per_sec=tok_per_sec,
                                ttft_sec=ttft_sec,
                            )
                            success = True
                            metrics_snapshot = self.get_metrics()

                            _perf_logger.info(
                                "llm_stream_performance",
                                extra={
                                    "event": "llm_stream_performance",
                                    "duration_ms": duration_sec * 1000.0,
                                    "metadata": {
                                        "ttft_ms": ttft_sec * 1000.0,
                                        "prompt_eval_count": prompt_eval_count,
                                        "eval_count": eval_count,
                                        "tokens_per_second": tok_per_sec,
                                    },
                                },
                            )
                            _app_logger.info("Ollama LLM stream chat request succeeded")

                            yield LLMStreamChunk(
                                delta=delta,
                                done=True,
                                model=stream_model,
                                request_id=effective_request_id,
                                finish_reason=finish_reason,
                                metrics=metrics_snapshot,
                            )
                            return

                except Exception:
                    with self._registry_lock:
                        if effective_request_id in self._cancelled_requests:
                            cancelled = True
                    if not success:
                        self._record_metrics(success=False)
                    if cancelled:
                        _app_logger.info("Ollama LLM stream chat request cancelled")
                        raise LLMCancelledError("Stream request was cancelled")
                    raise
                finally:
                    self._unregister_response(effective_request_id, response)
                    _audit_logger.info(
                        "llm_stream_chat_end",
                        extra={
                            "event": "llm_stream_chat_end",
                            "metadata": {
                                "provider": "ollama",
                                "model": effective_model,
                                "request_id": effective_request_id,
                                "success": success,
                                "cancelled": cancelled,
                                "ttft_seconds": ttft_sec,
                            },
                        },
                    )

        return _generator()

    def cancel(self, request_id: str) -> bool:
        """Cancel an active request by request_id."""

        target_response = None
        with self._registry_lock:
            if request_id in self._active_requests and request_id not in self._cancelled_requests:
                target_response = self._active_requests[request_id]
                self._cancelled_requests.add(request_id)

        if target_response is not None:
            with contextlib.suppress(OSError):
                target_response.close()
            return True
        return False

    def get_metrics(self) -> LLMMetrics:
        """Return a thread-safe snapshot of provider performance metrics."""

        with self._metrics_lock:
            return dataclasses.replace(self._metrics)

    def _register_response(self, request_id: str, response: Any) -> None:
        target_close = None
        exc_to_raise: Exception | None = None

        with self._registry_lock:
            if request_id in self._active_requests:
                target_close = response
                exc_to_raise = LLMResponseError(f"Duplicate active request ID '{request_id}'")
            elif request_id in self._cancelled_requests:
                target_close = response
                exc_to_raise = LLMCancelledError("Request was cancelled prior to execution")
            else:
                self._active_requests[request_id] = response

        if target_close is not None:
            with contextlib.suppress(OSError):
                target_close.close()
        if exc_to_raise is not None:
            raise exc_to_raise

    def _unregister_response(self, request_id: str, response: Any | None = None) -> None:
        target_close = None
        with self._registry_lock:
            active_resp = self._active_requests.pop(request_id, None)
            target_close = response or active_resp
            self._cancelled_requests.discard(request_id)

        if target_close is not None:
            with contextlib.suppress(OSError):
                target_close.close()

    def _record_metrics(
        self,
        *,
        success: bool,
        prompt_tokens: int = 0,
        eval_tokens: int = 0,
        tok_per_sec: float = 0.0,
        ttft_sec: float = 0.0,
    ) -> None:
        with self._metrics_lock:
            self._metrics.total_requests += 1
            if success:
                self._metrics.successful_requests += 1
                self._metrics.total_prompt_tokens += prompt_tokens
                self._metrics.total_eval_tokens += eval_tokens
                self._metrics.last_tokens_per_second = tok_per_sec
                self._metrics.last_ttft_seconds = ttft_sec
            else:
                self._metrics.failed_requests += 1
