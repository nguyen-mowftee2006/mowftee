from __future__ import annotations

import copy
import json
import logging
import logging.handlers
import stat
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from mowftee import logging_setup
from mowftee.config import load_config
from mowftee.logging_setup import (
    LOG_CHANNELS,
    REDACTED,
    generate_request_id,
    get_logger,
    get_request_id,
    new_request_id,
    redact_sensitive_data,
    request_context,
    setup_logging,
)


@pytest.fixture(autouse=True)
def clean_managed_handlers() -> None:
    def clean() -> None:
        for channel in LOG_CHANNELS:
            logger = logging.getLogger(f"mowftee.{channel}")
            for handler in list(logger.handlers):
                if getattr(handler, "_mowftee_managed", False):
                    logger.removeHandler(handler)
                    handler.close()

    clean()
    yield
    clean()


def make_config(tmp_path: Path, **logging_overrides: Any) -> dict[str, Any]:
    config = load_config(
        environment={"XDG_CONFIG_HOME": str(tmp_path / "config")},
    )
    config["logging"].update(logging_overrides)
    return config


def state_environment(tmp_path: Path) -> dict[str, str]:
    return {"XDG_STATE_HOME": str(tmp_path / "state")}


def read_json_lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_jsonl_record_has_utc_timestamp_and_request_context(tmp_path: Path) -> None:
    config = make_config(tmp_path, console=False)
    setup_logging(config, environment=state_environment(tmp_path))
    logger = get_logger("worker")

    with request_context(session_id="session-safe") as request_id:
        logger.info(
            "request complete",
            extra={
                "event": "request_complete",
                "duration_ms": 12.5,
                "metadata": {"component": "test"},
            },
        )

    record = read_json_lines(tmp_path / "state/mowftee/logs/app.jsonl")[0]
    assert set(record) == {
        "timestamp",
        "level",
        "event",
        "module",
        "request_id",
        "session_id",
        "message",
        "error_type",
        "duration_ms",
        "metadata",
    }
    assert record["timestamp"].endswith("Z")
    parsed_timestamp = datetime.fromisoformat(record["timestamp"])
    assert parsed_timestamp.utcoffset() == timedelta(0)
    assert uuid.UUID(record["request_id"])
    assert record["request_id"] == request_id
    assert record["session_id"] == "session-safe"
    assert record["event"] == "request_complete"
    assert record["duration_ms"] == 12.5


def test_request_context_is_nested_and_restored(tmp_path: Path) -> None:
    config = make_config(tmp_path, console=False)
    setup_logging(config, environment=state_environment(tmp_path))
    logger = get_logger()

    with request_context("outer", session_id="session-outer"):
        logger.info("outer-before")
        with request_context("inner", session_id="session-inner"):
            logger.info("inner")
        logger.info("outer-after")

    records = read_json_lines(tmp_path / "state/mowftee/logs/app.jsonl")
    assert [record["request_id"] for record in records] == ["outer", "inner", "outer"]
    assert [record["session_id"] for record in records] == [
        "session-outer",
        "session-inner",
        "session-outer",
    ]


def test_new_request_id_is_uuid() -> None:
    with request_context("temporary"):
        assert uuid.UUID(new_request_id())


def test_get_request_id_reflects_current_context() -> None:
    assert get_request_id() is None
    with request_context("bound-id"):
        assert get_request_id() == "bound-id"
        with request_context("nested-id"):
            assert get_request_id() == "nested-id"
        assert get_request_id() == "bound-id"
    assert get_request_id() is None


def test_generate_request_id_does_not_mutate_context() -> None:
    with request_context("context-id"):
        generated = generate_request_id()
        assert uuid.UUID(generated)
        assert generated != "context-id"
        assert get_request_id() == "context-id"



def test_redaction_handles_nested_values_urls_and_exceptions_without_mutation() -> None:
    original = {
        "PASSWORD": "password-value",
        "nested": [
            {"Api-Key": "api-key-value"},
            ("token=inline-value", {"authorization": "bearer-value"}),
        ],
        "url": "https://example.invalid/callback?token=query-value&safe=visible",
        "error": RuntimeError("private exception detail"),
        "session_id": "non-sensitive-id",
    }
    before = copy.deepcopy(original)

    sanitized = redact_sensitive_data(original)
    serialized = json.dumps(sanitized)

    assert sanitized["PASSWORD"] == REDACTED
    assert sanitized["nested"][0]["Api-Key"] == REDACTED
    assert "inline-value" not in serialized
    assert "bearer-value" not in serialized
    assert "query-value" not in serialized
    assert "safe=visible" in sanitized["url"]
    assert sanitized["error"] == {"error_type": "RuntimeError", "message": REDACTED}
    assert sanitized["session_id"] == "non-sensitive-id"
    assert original["PASSWORD"] == before["PASSWORD"]
    assert original["nested"] == before["nested"]
    assert str(original["error"]) == str(before["error"])


def test_authorization_and_cookie_headers_are_fully_redacted(tmp_path: Path) -> None:
    config = make_config(tmp_path, console=False)
    setup_logging(config, environment=state_environment(tmp_path))

    get_logger().warning(
        "Authorization: Bearer header-private-value\n"
        "Cookie: sid=cookie-private-value; preference=private\n"
        "Set-Cookie: session=set-cookie-private-value; HttpOnly",
    )

    raw_log = (tmp_path / "state/mowftee/logs/app.jsonl").read_text(encoding="utf-8")
    for private_value in (
        "header-private-value",
        "cookie-private-value",
        "set-cookie-private-value",
        "preference=private",
    ):
        assert private_value not in raw_log
    assert read_json_lines(tmp_path / "state/mowftee/logs/app.jsonl")[0][
        "message"
    ].count(REDACTED) == 3


def test_privacy_defaults_block_prompt_conversation_and_secrets(tmp_path: Path) -> None:
    config = make_config(tmp_path, console=False)
    setup_logging(config, environment=state_environment(tmp_path))

    get_logger().info(
        "processed private data",
        extra={
            "event": "privacy_check",
            "metadata": {
                "prompt": "private-prompt-value",
                "conversation": "private-conversation-value",
                "file_content": "private-file-value",
                "raw_audio": "private-audio-value",
                "secret": "private-secret-value",
                "nested": {"TOKEN": "private-token-value"},
            },
        },
    )

    raw_log = (tmp_path / "state/mowftee/logs/app.jsonl").read_text(encoding="utf-8")
    for private_value in (
        "private-prompt-value",
        "private-conversation-value",
        "private-file-value",
        "private-audio-value",
        "private-secret-value",
        "private-token-value",
    ):
        assert private_value not in raw_log
    metadata = json.loads(raw_log)["metadata"]
    assert metadata["prompt"] == REDACTED
    assert metadata["conversation"] == REDACTED


def test_audio_metadata_flag_never_enables_raw_audio(tmp_path: Path) -> None:
    config = make_config(tmp_path, console=False)
    config["privacy"]["log_audio_metadata"] = True
    setup_logging(config, environment=state_environment(tmp_path))

    get_logger().info(
        "audio processed",
        extra={
            "metadata": {
                "audio_metadata": {"sample_rate": 16_000},
                "raw_audio": "raw-audio-private-value",
                "audio_bytes": "audio-bytes-private-value",
            }
        },
    )

    raw_log = (tmp_path / "state/mowftee/logs/app.jsonl").read_text(encoding="utf-8")
    assert "raw-audio-private-value" not in raw_log
    assert "audio-bytes-private-value" not in raw_log
    metadata = json.loads(raw_log)["metadata"]
    assert metadata["audio_metadata"] == {"sample_rate": 16_000}
    assert metadata["raw_audio"] == REDACTED


def test_private_event_redacts_message_by_default(tmp_path: Path) -> None:
    config = make_config(tmp_path, console=False)
    setup_logging(config, environment=state_environment(tmp_path))

    get_logger().info(
        "prompt-private-message",
        extra={"event": "prompt"},
    )

    raw_log = (tmp_path / "state/mowftee/logs/app.jsonl").read_text(encoding="utf-8")
    assert "prompt-private-message" not in raw_log
    assert json.loads(raw_log)["message"] == REDACTED


def test_channel_files_are_separate_and_secure(tmp_path: Path) -> None:
    config = make_config(tmp_path, console=False)
    setup_logging(config, environment=state_environment(tmp_path))

    get_logger(channel="app").info("application")
    get_logger(channel="performance").info("performance")
    get_logger(channel="audit").info("audit")

    paths = {
        "app": tmp_path / "state/mowftee/logs/app.jsonl",
        "performance": tmp_path / "state/mowftee/logs/performance.jsonl",
        "audit": tmp_path / "state/mowftee/audit/audit.jsonl",
    }
    expected_messages = {
        "app": "application",
        "performance": "performance",
        "audit": "audit",
    }
    for channel, path in paths.items():
        records = read_json_lines(path)
        assert records[0]["message"] == expected_messages[channel]
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE((tmp_path / "state/mowftee").stat().st_mode) == 0o700


def test_state_path_uses_home_when_xdg_state_home_is_unset(tmp_path: Path) -> None:
    config = make_config(tmp_path, console=False)
    home_path = tmp_path / "home"

    setup_logging(config, environment={"HOME": str(home_path)})
    get_logger().info("home fallback")

    assert (home_path / ".local/state/mowftee/logs/app.jsonl").is_file()


def test_relative_xdg_state_home_uses_home_fallback(tmp_path: Path) -> None:
    config = make_config(tmp_path, console=False)
    home_path = tmp_path / "home"

    setup_logging(
        config,
        environment={
            "HOME": str(home_path),
            "XDG_STATE_HOME": "relative/state",
        },
    )
    get_logger().info("relative XDG fallback")

    assert (home_path / ".local/state/mowftee/logs/app.jsonl").is_file()


def test_setup_twice_does_not_duplicate_handlers_or_records(tmp_path: Path) -> None:
    config = make_config(tmp_path, console=False)
    environment = state_environment(tmp_path)

    setup_logging(config, environment=environment)
    setup_logging(config, environment=environment)
    logger = get_logger()
    logger.info("one record")

    managed_handlers = [
        handler
        for handler in logging.getLogger("mowftee.app").handlers
        if getattr(handler, "_mowftee_managed", False)
    ]
    assert len(managed_handlers) == 1
    assert len(read_json_lines(tmp_path / "state/mowftee/logs/app.jsonl")) == 1


def test_rotation_uses_standard_handler_and_keeps_valid_jsonl(tmp_path: Path) -> None:
    config = make_config(
        tmp_path,
        console=False,
        max_bytes=300,
        backup_count=2,
    )
    setup_logging(config, environment=state_environment(tmp_path))

    handler = next(
        handler
        for handler in logging.getLogger("mowftee.app").handlers
        if isinstance(handler, logging.handlers.RotatingFileHandler)
    )
    assert isinstance(handler, logging.handlers.RotatingFileHandler)
    assert handler.maxBytes == 300
    assert handler.backupCount == 2

    logger = get_logger()
    for index in range(12):
        logger.info("rotation payload %s %s", index, "x" * 120)

    paths = sorted((tmp_path / "state/mowftee/logs").glob("app.jsonl*"))
    assert 1 < len(paths) <= 3
    for path in paths:
        read_json_lines(path)
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_file_handler_failure_falls_back_to_console(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = make_config(tmp_path, console=False)

    def fail_file_handler(*args: object, **kwargs: object) -> logging.Handler:
        raise PermissionError("simulated failure")

    monkeypatch.setattr(logging_setup, "_SecureRotatingFileHandler", fail_file_handler)
    setup_logging(config, environment=state_environment(tmp_path))
    get_logger().warning("console fallback", extra={"event": "fallback"})

    stderr = capsys.readouterr().err
    assert "file output unavailable" in stderr
    json_lines = [line for line in stderr.splitlines() if line.startswith("{")]
    assert json.loads(json_lines[-1])["event"] == "fallback"


def test_runtime_file_failure_falls_back_to_console(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = make_config(tmp_path, console=False)
    setup_logging(config, environment=state_environment(tmp_path))
    handler = next(
        handler
        for handler in logging.getLogger("mowftee.app").handlers
        if isinstance(handler, logging.handlers.RotatingFileHandler)
    )

    def fail_rollover(record: logging.LogRecord) -> bool:
        raise OSError("simulated runtime failure")

    monkeypatch.setattr(handler, "shouldRollover", fail_rollover)
    get_logger().error("runtime fallback", extra={"event": "runtime_fallback"})

    stderr = capsys.readouterr().err
    assert stderr.count("file output unavailable for app") == 1
    json_lines = [line for line in stderr.splitlines() if line.startswith("{")]
    assert json.loads(json_lines[-1])["event"] == "runtime_fallback"


def test_setup_does_not_modify_root_logger(tmp_path: Path) -> None:
    root_logger = logging.getLogger()
    handlers_before = list(root_logger.handlers)
    level_before = root_logger.level

    setup_logging(
        make_config(tmp_path, console=False),
        environment=state_environment(tmp_path),
    )

    assert root_logger.handlers == handlers_before
    assert root_logger.level == level_before


def test_unknown_channel_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown logging channel"):
        get_logger(channel="unknown")
