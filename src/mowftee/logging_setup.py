"""Structured, privacy-aware logging for Mowftee."""

from __future__ import annotations

import contextlib
import contextvars
import copy
import json
import logging
import logging.handlers
import math
import os
import re
import sys
import threading
import uuid
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, quote_plus, unquote_plus, urlsplit, urlunsplit

REDACTED = "[REDACTED]"
LOGGER_NAMESPACE = "mowftee"
LOG_CHANNELS = ("app", "performance", "audit")

_SENSITIVE_KEYS = {
    "password",
    "passwd",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "set_cookie",
    "session",
}
_PRIVACY_KEYS = {
    "log_prompts": {"prompt", "prompts"},
    "log_conversations": {
        "conversation",
        "conversations",
        "conversation_history",
        "chat_history",
        "messages",
    },
    "log_file_contents": {"file_content", "file_contents"},
    "log_audio_metadata": {"audio_metadata"},
}
_ALWAYS_PRIVATE_KEYS = {
    "audio",
    "audio_bytes",
    "audio_data",
    "audio_samples",
    "raw_audio",
    "waveform",
}
_HEADER_PATTERN = re.compile(
    r"(?im)\b(authorization|cookie|set-cookie)\b(\s*[:=]\s*)[^\r\n]*"
)
_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(password|passwd|secret|token|access_token|refresh_token|api_key|apikey|"
    r"authorization|cookie|set-cookie|session)\b(\s*[:=]\s*)"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;&]+)"
)
_URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)

_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "mowftee_request_id", default=None
)
_session_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "mowftee_session_id", default=None
)
_setup_lock = threading.RLock()


def _normalize_key(key: object) -> str:
    return str(key).casefold().replace("-", "_")


def _is_sensitive_key(key: object) -> bool:
    return _normalize_key(key) in _SENSITIVE_KEYS


def _redact_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return url
    if not parsed.query:
        return url

    redacted_pairs: list[tuple[str, str]] = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        decoded_key = unquote_plus(key)
        redacted_pairs.append((key, REDACTED if _is_sensitive_key(decoded_key) else value))
    query = "&".join(
        f"{quote_plus(key)}={quote_plus(value, safe='[]')}" for key, value in redacted_pairs
    )
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))


def _redact_text(value: str) -> str:
    def redact_header(match: re.Match[str]) -> str:
        return f"{match.group(1)}{match.group(2)}{REDACTED}"

    def redact_assignment(match: re.Match[str]) -> str:
        return f"{match.group(1)}{match.group(2)}{REDACTED}"

    redacted = _HEADER_PATTERN.sub(redact_header, value)
    redacted = _ASSIGNMENT_PATTERN.sub(redact_assignment, redacted)
    return _URL_PATTERN.sub(lambda match: _redact_url(match.group(0)), redacted)


def redact_sensitive_data(value: Any) -> Any:
    """Return a sanitized copy of nested data without modifying the input."""

    return _redact_value(value, seen=set())


def _redact_value(value: Any, *, seen: set[int]) -> Any:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, (Path, uuid.UUID)):
        return str(value)
    if isinstance(value, bytes):
        return REDACTED
    if isinstance(value, BaseException):
        return {"error_type": type(value).__name__, "message": REDACTED}

    value_id = id(value)
    if value_id in seen:
        return REDACTED

    if isinstance(value, Mapping):
        seen.add(value_id)
        sanitized: dict[str, Any] = {}
        try:
            for key, nested_value in value.items():
                key_string = str(key)
                sanitized[key_string] = (
                    REDACTED
                    if _is_sensitive_key(key_string)
                    else _redact_value(nested_value, seen=seen)
                )
        finally:
            seen.remove(value_id)
        return sanitized

    if isinstance(value, list):
        seen.add(value_id)
        try:
            return [_redact_value(item, seen=seen) for item in value]
        finally:
            seen.remove(value_id)

    if isinstance(value, tuple):
        seen.add(value_id)
        try:
            return tuple(_redact_value(item, seen=seen) for item in value)
        finally:
            seen.remove(value_id)

    if isinstance(value, (set, frozenset)):
        seen.add(value_id)
        try:
            return [_redact_value(item, seen=seen) for item in value]
        finally:
            seen.remove(value_id)

    return f"<{type(value).__name__}>"


def _apply_privacy_policy(value: Any, privacy: Mapping[str, Any]) -> Any:
    blocked_keys = set(_ALWAYS_PRIVATE_KEYS)
    for policy_name, keys in _PRIVACY_KEYS.items():
        if privacy.get(policy_name) is not True:
            blocked_keys.update(keys)

    def sanitize(item: Any, *, seen: set[int]) -> Any:
        item_id = id(item)
        if item_id in seen:
            return REDACTED

        if isinstance(item, Mapping):
            seen.add(item_id)
            result: dict[str, Any] = {}
            try:
                for key, nested_value in item.items():
                    key_string = str(key)
                    if _normalize_key(key_string) in blocked_keys:
                        result[key_string] = REDACTED
                    else:
                        result[key_string] = sanitize(nested_value, seen=seen)
                return result
            finally:
                seen.remove(item_id)
        if isinstance(item, list):
            seen.add(item_id)
            try:
                return [sanitize(nested_value, seen=seen) for nested_value in item]
            finally:
                seen.remove(item_id)
        if isinstance(item, tuple):
            seen.add(item_id)
            try:
                return tuple(sanitize(nested_value, seen=seen) for nested_value in item)
            finally:
                seen.remove(item_id)
        if isinstance(item, (set, frozenset)):
            seen.add(item_id)
            try:
                return [sanitize(nested_value, seen=seen) for nested_value in item]
            finally:
                seen.remove(item_id)
        return copy.deepcopy(item)

    return sanitize(value, seen=set())


def _privacy_allows_message(event: object, privacy: Mapping[str, Any]) -> bool:
    normalized_event = _normalize_key(event)
    if normalized_event in _ALWAYS_PRIVATE_KEYS:
        return False
    return all(
        privacy.get(policy_name) is True or normalized_event not in keys
        for policy_name, keys in _PRIVACY_KEYS.items()
    )


class _ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.mowftee_request_id = getattr(record, "request_id", None) or _request_id_var.get()
        record.mowftee_session_id = getattr(record, "session_id", None) or _session_id_var.get()
        return True


class _JsonLineFormatter(logging.Formatter):
    def __init__(self, privacy: Mapping[str, Any]) -> None:
        super().__init__()
        self._privacy = copy.deepcopy(dict(privacy))

    def format(self, record: logging.LogRecord) -> str:
        metadata = getattr(record, "metadata", {})
        privacy_filtered = _apply_privacy_policy(metadata, self._privacy)
        sanitized_metadata = redact_sensitive_data(privacy_filtered)
        event = getattr(record, "event", "log")
        error_type = getattr(record, "error_type", None)
        if error_type is None and record.exc_info and record.exc_info[0]:
            error_type = record.exc_info[0].__name__
        message = record.getMessage() if _privacy_allows_message(event, self._privacy) else REDACTED

        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "event": redact_sensitive_data(event),
            "module": record.name,
            "request_id": getattr(record, "mowftee_request_id", None),
            "session_id": getattr(record, "mowftee_session_id", None),
            "message": redact_sensitive_data(message),
            "error_type": redact_sensitive_data(error_type),
            "duration_ms": redact_sensitive_data(getattr(record, "duration_ms", None)),
            "metadata": sanitized_metadata,
        }
        return json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


class _SecureRotatingFileHandler(logging.handlers.RotatingFileHandler):
    def __init__(
        self,
        filename: Path,
        *,
        max_bytes: int,
        backup_count: int,
        encoding: str,
        fallback_handler: logging.Handler | None,
        channel: str,
    ) -> None:
        self._fallback_handler = fallback_handler
        self._channel = channel
        self._failure_reported = False
        super().__init__(
            filename,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding=encoding,
        )

    def _open(self):  # type: ignore[no-untyped-def]
        file_descriptor = os.open(
            self.baseFilename,
            os.O_APPEND | os.O_CREAT | os.O_WRONLY,
            0o600,
        )
        return open(
            file_descriptor,
            mode=self.mode,
            encoding=self.encoding,
            errors=self.errors,
            closefd=True,
        )

    def handleError(self, record: logging.LogRecord) -> None:
        if self._fallback_handler is not None:
            self._fallback_handler.handle(record)
        if not self._failure_reported:
            self._failure_reported = True
            _report_file_failure(self._channel)

    def close(self) -> None:
        if self._fallback_handler is not None:
            self._fallback_handler.close()
        super().close()


def _resolve_state_home(environment: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environment is None else environment
    configured = env.get("XDG_STATE_HOME")
    if configured:
        configured_path = Path(configured).expanduser()
        if configured_path.is_absolute():
            return configured_path
    home_path = Path(env["HOME"]).expanduser() if env.get("HOME") else Path.home()
    base_path = home_path if home_path.is_absolute() else Path.home()
    return base_path / ".local" / "state"


def _managed_handler(handler: logging.Handler) -> logging.Handler:
    handler._mowftee_managed = True  # type: ignore[attr-defined]
    return handler


def _clear_managed_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        if getattr(handler, "_mowftee_managed", False):
            logger.removeHandler(handler)
            handler.close()


def _console_handler(formatter: logging.Formatter, level: int) -> logging.Handler:
    handler = _managed_handler(logging.StreamHandler())
    handler.setLevel(level)
    handler.setFormatter(formatter)
    handler.addFilter(_ContextFilter())
    return handler


def _report_file_failure(channel: str) -> None:
    print(
        f"Mowftee logging: file output unavailable for {channel}; using console.",
        file=sys.stderr,
    )


def setup_logging(
    config: Mapping[str, Any],
    *,
    environment: Mapping[str, str] | None = None,
) -> None:
    """Configure isolated Mowftee loggers from validated application config."""

    logging_config = config.get("logging", {})
    privacy = config.get("privacy", {})
    if not isinstance(logging_config, Mapping) or not isinstance(privacy, Mapping):
        raise TypeError("Logging and privacy configuration must be mappings")

    level_name = str(logging_config.get("level", "INFO"))
    level = getattr(logging, level_name, logging.INFO)
    console_enabled = logging_config.get("console") is True
    file_enabled = logging_config.get("file") is True
    max_bytes = int(logging_config.get("max_bytes", 5_242_880))
    backup_count = int(logging_config.get("backup_count", 3))
    state_root = _resolve_state_home(environment) / "mowftee"
    channel_paths = {
        "app": state_root / "logs" / "app.jsonl",
        "performance": state_root / "logs" / "performance.jsonl",
        "audit": state_root / "audit" / "audit.jsonl",
    }

    formatter = _JsonLineFormatter(privacy)

    with _setup_lock:
        for channel, log_path in channel_paths.items():
            logger = logging.getLogger(f"{LOGGER_NAMESPACE}.{channel}")
            logger.setLevel(level)
            logger.propagate = False
            logger.disabled = False
            _clear_managed_handlers(logger)

            console_handler: logging.Handler | None = None
            if console_enabled:
                console_handler = _console_handler(formatter, level)
                logger.addHandler(console_handler)

            if not file_enabled:
                continue

            file_handler: _SecureRotatingFileHandler | None = None
            runtime_fallback = None if console_handler is not None else _console_handler(
                formatter, level
            )
            try:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                os.chmod(state_root, 0o700)
                os.chmod(log_path.parent, 0o700)
                file_handler = _SecureRotatingFileHandler(
                    log_path,
                    max_bytes=max_bytes,
                    backup_count=backup_count,
                    encoding="utf-8",
                    fallback_handler=runtime_fallback,
                    channel=channel,
                )
                _managed_handler(file_handler)
                os.chmod(log_path, 0o600)
                file_handler.setLevel(level)
                file_handler.setFormatter(formatter)
                file_handler.addFilter(_ContextFilter())
                logger.addHandler(file_handler)
            except OSError:
                if file_handler is not None:
                    file_handler.close()
                elif runtime_fallback is not None:
                    runtime_fallback.close()
                if console_handler is None:
                    logger.addHandler(_console_handler(formatter, level))
                _report_file_failure(channel)


def get_logger(name: str | None = None, *, channel: str = "app") -> logging.Logger:
    """Return a Mowftee logger for the selected output channel."""

    if channel not in LOG_CHANNELS:
        raise ValueError(f"Unknown logging channel: {channel}")
    logger_name = f"{LOGGER_NAMESPACE}.{channel}"
    if name:
        logger_name = f"{logger_name}.{name}"
    return logging.getLogger(logger_name)


def new_request_id() -> str:
    """Create and activate a new UUID request identifier."""

    request_id = str(uuid.uuid4())
    _request_id_var.set(request_id)
    return request_id


@contextlib.contextmanager
def request_context(
    request_id: str | None = None,
    *,
    session_id: str | None = None,
) -> Iterator[str]:
    """Temporarily bind request/session identifiers to the current context."""

    active_request_id = request_id or str(uuid.uuid4())
    request_token = _request_id_var.set(active_request_id)
    session_token = _session_id_var.set(session_id)
    try:
        yield active_request_id
    finally:
        _session_id_var.reset(session_token)
        _request_id_var.reset(request_token)
