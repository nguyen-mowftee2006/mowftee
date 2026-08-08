from __future__ import annotations

import json
import socket
import threading
import urllib.error
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mowftee.config import load_config
from mowftee.llm import (
    ChatMessage,
    LLMCancelledError,
    LLMConnectionError,
    LLMProvider,
    LLMResponseError,
    LLMTimeoutError,
    OllamaLLMProvider,
)
from mowftee.logging_setup import get_request_id, request_context, setup_logging


@pytest.fixture
def base_config(tmp_path: Any) -> dict[str, Any]:
    return load_config(environment={"XDG_CONFIG_HOME": str(tmp_path / "config")})


def make_mock_response(status: int = 200, data: dict[str, Any] | str | bytes | None = None) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status = status
    if isinstance(data, (dict, list)):
        payload = json.dumps(data).encode("utf-8")
    elif isinstance(data, str):
        payload = data.encode("utf-8")
    elif isinstance(data, bytes):
        payload = data
    else:
        payload = b"{}"
    mock_resp.read.return_value = payload
    mock_resp.__enter__.return_value = mock_resp
    return mock_resp


def make_streaming_response(lines: list[dict[str, Any] | str | bytes]) -> MagicMock:
    mock_resp = MagicMock()
    raw_lines = []
    for line in lines:
        if isinstance(line, (dict, list)):
            raw_lines.append(json.dumps(line).encode("utf-8") + b"\n")
        elif isinstance(line, str):
            raw_lines.append(line.encode("utf-8") + b"\n")
        elif isinstance(line, bytes):
            raw_lines.append(line if line.endswith(b"\n") else line + b"\n")
    mock_resp.readline.side_effect = raw_lines + [b""]
    mock_resp.__enter__.return_value = mock_resp
    return mock_resp


def test_ollama_provider_implements_protocol(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    assert isinstance(provider, LLMProvider)


def test_health_check_success(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    mock_resp = make_mock_response(200, {"version": "0.32.6"})

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        assert provider.health_check() is True
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://127.0.0.1:11434/api/version"
        assert req.get_method() == "GET"


def test_health_check_connection_error(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        assert provider.health_check() is False


def test_health_check_timeout(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    with patch("urllib.request.urlopen", side_effect=TimeoutError("Timed out")):
        assert provider.health_check() is False


def test_health_check_http_error(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    err = urllib.error.HTTPError("http://127.0.0.1:11434/api/version", 500, "Server error", {}, None)
    with patch("urllib.request.urlopen", side_effect=err):
        assert provider.health_check() is False


def test_health_check_malformed_json(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    mock_resp = make_mock_response(200, b"invalid json{")
    with patch("urllib.request.urlopen", return_value=mock_resp):
        assert provider.health_check() is False


def test_chat_success_parse_and_metrics(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    ollama_resp = {
        "model": "qwen3:4b-instruct",
        "created_at": "2026-08-08T10:00:00Z",
        "message": {"role": "assistant", "content": "Chào bạn, mình là Mowftee!"},
        "done": True,
        "done_reason": "stop",
        "total_duration": 500000000,
        "load_duration": 100000000,
        "prompt_eval_count": 10,
        "prompt_eval_duration": 100000000,
        "eval_count": 20,
        "eval_duration": 300000000,
    }
    mock_resp = make_mock_response(200, ollama_resp)

    messages = [ChatMessage(role="user", content="Xin chào")]

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        response = provider.chat(messages, request_id="req-custom-123")

        assert response.content == "Chào bạn, mình là Mowftee!"
        assert response.model == "qwen3:4b-instruct"
        assert response.finish_reason == "stop"
        assert response.request_id == "req-custom-123"
        assert response.prompt_eval_count == 10
        assert response.eval_count == 20
        assert response.total_duration_ns == 500000000
        assert response.load_duration_ns == 100000000
        assert response.prompt_eval_duration_ns == 100000000
        assert response.eval_duration_ns == 300000000

        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))
        assert payload["model"] == "qwen3:4b-instruct"
        assert payload["messages"] == [{"role": "user", "content": "Xin chào"}]
        assert payload["stream"] is False

    metrics = provider.get_metrics()
    assert metrics.total_requests == 1
    assert metrics.successful_requests == 1
    assert metrics.failed_requests == 0
    assert metrics.total_prompt_tokens == 10
    assert metrics.total_eval_tokens == 20
    assert metrics.last_tokens_per_second > 60.0
    assert metrics.last_ttft_seconds == 0.0


def test_chat_model_override_and_options(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    ollama_resp = {
        "model": "llama3.2:3b",
        "message": {"role": "assistant", "content": "Hi!"},
        "done": True,
    }
    mock_resp = make_mock_response(200, ollama_resp)
    messages = [ChatMessage(role="user", content="Hi")]
    options = {"temperature": 0.7, "num_predict": 100}

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        resp = provider.chat(messages, model="llama3.2:3b", options=options)
        assert resp.model == "llama3.2:3b"

        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))
        assert payload["model"] == "llama3.2:3b"
        assert payload["options"] == {"temperature": 0.7, "num_predict": 100}


def test_chat_request_id_preservation_and_context_reuse(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    mock_resp = make_mock_response(200, {
        "model": "qwen3:4b-instruct",
        "message": {"role": "assistant", "content": "OK"},
    })

    with patch("urllib.request.urlopen", return_value=mock_resp):
        with request_context("active-ctx-id"):
            resp = provider.chat([ChatMessage(role="user", content="Test")])
            assert resp.request_id == "active-ctx-id"
            assert get_request_id() == "active-ctx-id"

        assert get_request_id() is None


def test_chat_generates_id_when_no_context_and_restores(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    mock_resp = make_mock_response(200, {
        "model": "qwen3:4b-instruct",
        "message": {"role": "assistant", "content": "OK"},
    })

    with patch("urllib.request.urlopen", return_value=mock_resp):
        assert get_request_id() is None
        resp = provider.chat([ChatMessage(role="user", content="Test")])
        assert bool(resp.request_id)
        assert get_request_id() is None


def test_chat_invalid_input_raises_value_error(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    with pytest.raises(ValueError, match="messages must not be empty"):
        provider.chat([])

    with pytest.raises(ValueError, match="invalid role"):
        provider.chat([ChatMessage(role="", content="Hello")])

    with pytest.raises(TypeError, match="non-string content"):
        provider.chat([ChatMessage(role="user", content=123)])  # type: ignore[arg-type]


def test_chat_connection_error_mapping(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    err = urllib.error.URLError(reason=socket.gaierror("Name or service not known"))
    with (
        patch("urllib.request.urlopen", side_effect=err),
        pytest.raises(LLMConnectionError, match="Failed to connect"),
    ):
        provider.chat([ChatMessage(role="user", content="Hi")])

    metrics = provider.get_metrics()
    assert metrics.total_requests == 1
    assert metrics.failed_requests == 1


def test_chat_timeout_error_mapping(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    with (
        patch("urllib.request.urlopen", side_effect=TimeoutError("socket timeout")),
        pytest.raises(LLMTimeoutError, match="timed out"),
    ):
        provider.chat([ChatMessage(role="user", content="Hi")])

    metrics = provider.get_metrics()
    assert metrics.total_requests == 1
    assert metrics.failed_requests == 1


def test_chat_http_error_mapping(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    err = urllib.error.HTTPError("http://127.0.0.1:11434/api/chat", 404, "Model not found", {}, None)
    with (
        patch("urllib.request.urlopen", side_effect=err),
        pytest.raises(LLMResponseError, match="HTTP error 404"),
    ):
        provider.chat([ChatMessage(role="user", content="Hi")])


def test_chat_malformed_json_response(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    mock_resp = make_mock_response(200, b"not json")
    with (
        patch("urllib.request.urlopen", return_value=mock_resp),
        pytest.raises(LLMResponseError, match="Malformed JSON"),
    ):
        provider.chat([ChatMessage(role="user", content="Hi")])


def test_chat_malformed_schema_response(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    mock_resp = make_mock_response(200, {"model": "qwen3:4b-instruct"})  # missing message
    with (
        patch("urllib.request.urlopen", return_value=mock_resp),
        pytest.raises(LLMResponseError, match="Missing or invalid 'message'"),
    ):
        provider.chat([ChatMessage(role="user", content="Hi")])


def test_metrics_snapshot_isolation(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    snapshot1 = provider.get_metrics()
    snapshot1.total_requests = 999
    assert provider.get_metrics().total_requests == 0


def test_logs_do_not_contain_prompt_or_response_content(
    base_config: dict[str, Any],
    tmp_path: Any,
) -> None:
    config = load_config(environment={"XDG_CONFIG_HOME": str(tmp_path / "config")})
    setup_logging(config, environment={"XDG_STATE_HOME": str(tmp_path / "state")})

    provider = OllamaLLMProvider(config)
    secret_prompt = "SECRET_USER_PROMPT_12345"
    secret_response = "SECRET_ASSISTANT_RESPONSE_67890"

    mock_resp = make_mock_response(200, {
        "model": "qwen3:4b-instruct",
        "message": {"role": "assistant", "content": secret_response},
    })

    with patch("urllib.request.urlopen", return_value=mock_resp):
        provider.chat([ChatMessage(role="user", content=secret_prompt)])

    log_files = list((tmp_path / "state/mowftee/logs").glob("*.jsonl")) + list((tmp_path / "state/mowftee/audit").glob("*.jsonl"))
    for log_file in log_files:
        content = log_file.read_text(encoding="utf-8")
        assert secret_prompt not in content
        assert secret_response not in content


@pytest.mark.parametrize(
    "invalid_value",
    [
        "10",
        True,
        False,
        10.5,
        -1,
        [10],
        {"val": 10},
    ],
)
def test_chat_invalid_numeric_field_rejected(
    base_config: dict[str, Any],
    invalid_value: Any,
) -> None:
    provider = OllamaLLMProvider(base_config)
    mock_resp = make_mock_response(
        200,
        {
            "model": "qwen3:4b-instruct",
            "message": {"role": "assistant", "content": "Hi"},
            "prompt_eval_count": invalid_value,
        },
    )
    with (
        patch("urllib.request.urlopen", return_value=mock_resp),
        pytest.raises(LLMResponseError, match="must be a non-negative integer"),
    ):
        provider.chat([ChatMessage(role="user", content="Hi")])

    metrics = provider.get_metrics()
    assert metrics.total_requests == 1
    assert metrics.successful_requests == 0
    assert metrics.failed_requests == 1
    assert metrics.total_prompt_tokens == 0
    assert metrics.total_eval_tokens == 0


def test_chat_missing_or_null_numeric_fields_defaults_to_zero(
    base_config: dict[str, Any],
) -> None:
    provider = OllamaLLMProvider(base_config)
    mock_resp = make_mock_response(
        200,
        {
            "model": "qwen3:4b-instruct",
            "message": {"role": "assistant", "content": "Hi"},
            "prompt_eval_count": None,
            "eval_count": None,
        },
    )
    with patch("urllib.request.urlopen", return_value=mock_resp):
        resp = provider.chat([ChatMessage(role="user", content="Hi")])
        assert resp.prompt_eval_count == 0
        assert resp.eval_count == 0
        assert resp.total_duration_ns == 0


def test_context_restored_on_chat_failure(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    with (
        patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")),
        pytest.raises(LLMTimeoutError),
    ):
        assert get_request_id() is None
        provider.chat([ChatMessage(role="user", content="Hi")])

    assert get_request_id() is None


# Checkpoint 3 Streaming & Cancellation Tests


def test_stream_chat_success_and_metrics(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    stream_data = [
        {"model": "qwen3:4b-instruct", "message": {"role": "assistant", "content": "Xin"}, "done": False},
        {"model": "qwen3:4b-instruct", "message": {"role": "assistant", "content": " chào!"}, "done": False},
        {
            "model": "qwen3:4b-instruct",
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 8,
            "eval_count": 16,
            "eval_duration": 200000000,
        },
    ]
    mock_resp = make_streaming_response(stream_data)

    messages = [ChatMessage(role="user", content="Xin chào")]

    with patch("urllib.request.urlopen", return_value=mock_resp):
        chunks = list(provider.stream_chat(messages, request_id="stream-req-1"))

    assert len(chunks) == 3
    assert chunks[0].delta == "Xin"
    assert chunks[0].done is False
    assert chunks[0].request_id == "stream-req-1"

    assert chunks[1].delta == " chào!"
    assert chunks[1].done is False
    assert chunks[1].request_id == "stream-req-1"

    assert chunks[2].done is True
    assert chunks[2].finish_reason == "stop"
    assert chunks[2].request_id == "stream-req-1"
    assert chunks[2].metrics is not None
    assert chunks[2].metrics.successful_requests == 1

    metrics = provider.get_metrics()
    assert metrics.total_requests == 1
    assert metrics.successful_requests == 1
    assert metrics.failed_requests == 0
    assert metrics.total_prompt_tokens == 8
    assert metrics.total_eval_tokens == 16
    assert metrics.last_ttft_seconds >= 0.0


def test_stream_chat_model_override_and_options(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    stream_data = [
        {"model": "llama3.2:3b", "message": {"role": "assistant", "content": "Hello"}, "done": False},
        {"model": "llama3.2:3b", "done": True},
    ]
    mock_resp = make_streaming_response(stream_data)
    options = {"temperature": 0.5}

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        chunks = list(provider.stream_chat([ChatMessage(role="user", content="Hi")], model="llama3.2:3b", options=options))
        assert chunks[0].model == "llama3.2:3b"

        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))
        assert payload["model"] == "llama3.2:3b"
        assert payload["options"] == {"temperature": 0.5}


def test_stream_chat_model_mismatch_raises_error(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    stream_data = [
        {"model": "qwen3:4b-instruct", "message": {"role": "assistant", "content": "A"}, "done": False},
        {"model": "llama3.2:3b", "message": {"role": "assistant", "content": "B"}, "done": False},
    ]
    mock_resp = make_streaming_response(stream_data)

    with (
        patch("urllib.request.urlopen", return_value=mock_resp),
        pytest.raises(LLMResponseError, match="Model mismatch"),
    ):
        list(provider.stream_chat([ChatMessage(role="user", content="Hi")]))


def test_stream_chat_malformed_ndjson(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    mock_resp = make_streaming_response(["{invalid json", ""])
    with (
        patch("urllib.request.urlopen", return_value=mock_resp),
        pytest.raises(LLMResponseError, match="Malformed NDJSON"),
    ):
        list(provider.stream_chat([ChatMessage(role="user", content="Hi")]))


def test_stream_chat_malformed_schema(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    stream_data = [
        {"model": "qwen3:4b-instruct", "done": False},  # missing message
    ]
    mock_resp = make_streaming_response(stream_data)
    with (
        patch("urllib.request.urlopen", return_value=mock_resp),
        pytest.raises(LLMResponseError, match="Missing or invalid 'message'"),
    ):
        list(provider.stream_chat([ChatMessage(role="user", content="Hi")]))


def test_stream_chat_invalid_numeric_final_field(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    stream_data = [
        {"model": "qwen3:4b-instruct", "done": True, "prompt_eval_count": "invalid"},
    ]
    mock_resp = make_streaming_response(stream_data)
    with (
        patch("urllib.request.urlopen", return_value=mock_resp),
        pytest.raises(LLMResponseError, match="must be a non-negative integer"),
    ):
        list(provider.stream_chat([ChatMessage(role="user", content="Hi")]))


def test_stream_chat_no_content_ttft_zero(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    stream_data = [
        {"model": "qwen3:4b-instruct", "message": {"role": "assistant", "content": ""}, "done": False},
        {"model": "qwen3:4b-instruct", "done": True},
    ]
    mock_resp = make_streaming_response(stream_data)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        chunks = list(provider.stream_chat([ChatMessage(role="user", content="Hi")]))
        assert chunks[-1].metrics is not None
        assert chunks[-1].metrics.last_ttft_seconds == 0.0


def test_cancel_active_request_and_cleanup(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)

    mock_resp = MagicMock()
    mock_resp.readline.side_effect = [
        json.dumps({"model": "qwen3:4b-instruct", "message": {"role": "assistant", "content": "Hi"}, "done": False}).encode("utf-8") + b"\n",
        OSError("Socket closed"),
    ]

    with patch("urllib.request.urlopen", return_value=mock_resp):
        gen = provider.stream_chat([ChatMessage(role="user", content="Hi")], request_id="cancel-req-1")
        first_chunk = next(gen)
        assert first_chunk.delta == "Hi"

        # Cancel while active
        assert provider.cancel("cancel-req-1") is True
        mock_resp.close.assert_called_once()

        # Continuing stream raises LLMCancelledError
        with pytest.raises(LLMCancelledError):
            next(gen)

    # Calling cancel again returns False
    assert provider.cancel("cancel-req-1") is False

    # Registry is clean
    assert len(provider._active_requests) == 0
    assert len(provider._cancelled_requests) == 0

    metrics = provider.get_metrics()
    assert metrics.total_requests == 1
    assert metrics.failed_requests == 1
    assert metrics.successful_requests == 0


def test_cancel_unknown_request_returns_false(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    assert provider.cancel("unknown-req-999") is False


def test_duplicate_active_request_id_rejected(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    mock_resp1 = make_streaming_response([
        {"model": "qwen3:4b-instruct", "message": {"role": "assistant", "content": "1"}, "done": False},
    ])
    mock_resp2 = make_streaming_response([
        {"model": "qwen3:4b-instruct", "message": {"role": "assistant", "content": "2"}, "done": False},
    ])

    with patch("urllib.request.urlopen", side_effect=[mock_resp1, mock_resp2]):
        gen1 = provider.stream_chat([ChatMessage(role="user", content="1")], request_id="dup-req-id")
        next(gen1)

        # Second request with same ID fails
        gen2 = provider.stream_chat([ChatMessage(role="user", content="2")], request_id="dup-req-id")
        with pytest.raises(LLMResponseError, match="Duplicate active request ID"):
            next(gen2)

        gen1.close()

    assert len(provider._active_requests) == 0


def test_generator_early_close_cleans_up_registry(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    mock_resp = make_streaming_response([
        {"model": "qwen3:4b-instruct", "message": {"role": "assistant", "content": "Part"}, "done": False},
    ])

    with patch("urllib.request.urlopen", return_value=mock_resp):
        gen = provider.stream_chat([ChatMessage(role="user", content="Hi")], request_id="early-close-id")
        next(gen)
        assert "early-close-id" in provider._active_requests
        gen.close()

    assert len(provider._active_requests) == 0
    assert len(provider._cancelled_requests) == 0


def test_streaming_logs_do_not_contain_chunk_content(
    base_config: dict[str, Any],
    tmp_path: Any,
) -> None:
    config = load_config(environment={"XDG_CONFIG_HOME": str(tmp_path / "config")})
    setup_logging(config, environment={"XDG_STATE_HOME": str(tmp_path / "state")})

    provider = OllamaLLMProvider(config)
    secret_chunk = "SECRET_CHUNK_CONTENT_abc123"

    mock_resp = make_streaming_response([
        {"model": "qwen3:4b-instruct", "message": {"role": "assistant", "content": secret_chunk}, "done": False},
        {"model": "qwen3:4b-instruct", "done": True},
    ])

    with patch("urllib.request.urlopen", return_value=mock_resp):
        list(provider.stream_chat([ChatMessage(role="user", content="Hello")]))

    log_files = list((tmp_path / "state/mowftee/logs").glob("*.jsonl")) + list((tmp_path / "state/mowftee/audit").glob("*.jsonl"))
    for log_file in log_files:
        content = log_file.read_text(encoding="utf-8")
        assert secret_chunk not in content


def test_stream_chat_empty_stream_raises_response_error(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    mock_resp = make_streaming_response([])
    with (
        patch("urllib.request.urlopen", return_value=mock_resp),
        pytest.raises(LLMResponseError, match="ended prematurely"),
    ):
        list(provider.stream_chat([ChatMessage(role="user", content="Hi")]))

    metrics = provider.get_metrics()
    assert metrics.total_requests == 1
    assert metrics.failed_requests == 1
    assert metrics.successful_requests == 0


def test_stream_chat_intermediate_eof_raises_response_error(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    stream_data = [
        {"model": "qwen3:4b-instruct", "message": {"role": "assistant", "content": "Part"}, "done": False},
    ]
    mock_resp = make_streaming_response(stream_data)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        gen = provider.stream_chat([ChatMessage(role="user", content="Hi")])
        assert next(gen).delta == "Part"
        with pytest.raises(LLMResponseError, match="ended prematurely"):
            next(gen)

    metrics = provider.get_metrics()
    assert metrics.total_requests == 1
    assert metrics.failed_requests == 1
    assert metrics.successful_requests == 0


def test_cancel_idempotency_second_call_returns_false(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)
    mock_resp = MagicMock()
    mock_resp.readline.side_effect = [
        json.dumps({"model": "qwen3:4b-instruct", "message": {"role": "assistant", "content": "Hi"}, "done": False}).encode("utf-8") + b"\n",
        OSError("Closed"),
    ]

    with patch("urllib.request.urlopen", return_value=mock_resp):
        gen = provider.stream_chat([ChatMessage(role="user", content="Hi")], request_id="idemp-req-1")
        next(gen)

        # First cancel -> True
        assert provider.cancel("idemp-req-1") is True
        # Second immediate cancel before cleanup -> False
        assert provider.cancel("idemp-req-1") is False

        with pytest.raises(LLMCancelledError):
            next(gen)

    # Post cleanup cancel -> False
    assert provider.cancel("idemp-req-1") is False


def test_stream_chat_blocking_cancellation(base_config: dict[str, Any]) -> None:
    provider = OllamaLLMProvider(base_config)

    unblock_event = threading.Event()

    def blocking_readline() -> bytes:
        unblock_event.wait(timeout=2.0)
        raise OSError("Closed by test cancel")

    mock_resp = MagicMock()
    mock_resp.readline.side_effect = blocking_readline

    caught_exc: Exception | None = None

    def worker() -> None:
        nonlocal caught_exc
        try:
            list(provider.stream_chat([ChatMessage(role="user", content="Hi")], request_id="block-req-1"))
        except LLMCancelledError as exc:
            caught_exc = exc

    with patch("urllib.request.urlopen", return_value=mock_resp):
        t = threading.Thread(target=worker)
        t.start()

        # Wait until registered
        while "block-req-1" not in provider._active_requests:
            t.join(timeout=0.01)

        # Cancel active request
        assert provider.cancel("block-req-1") is True
        unblock_event.set()
        t.join(timeout=2.0)

    assert isinstance(caught_exc, LLMCancelledError)
    assert len(provider._active_requests) == 0
    assert len(provider._cancelled_requests) == 0
