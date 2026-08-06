"""Configuration loading and validation for Mowftee."""

from __future__ import annotations

import copy
import os
import re
from collections.abc import Mapping
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

ENVIRONMENT_PREFIX = "MOWFTEE_"
SUPPORTED_SCHEMA_VERSION = 1
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
PRIVACY_FLAGS = (
    "log_prompts",
    "log_conversations",
    "log_file_contents",
    "log_audio_metadata",
)
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "default.yaml"

ConfigMapping = Mapping[str, Any]
ConfigDict = dict[str, Any]

_INTEGER_PATTERN = re.compile(r"^[+-]?\d+$")
_FLOAT_PATTERN = re.compile(
    r"^[+-]?(?:(?:\d+\.\d*)|(?:\d*\.\d+)|(?:\d+))(?:[eE][+-]?\d+)$"
    r"|^[+-]?(?:\d+\.\d*|\d*\.\d+)$"
)


class ConfigError(Exception):
    """Raised when configuration cannot be read or parsed."""


class ConfigValidationError(ConfigError):
    """Raised when configuration values fail schema validation."""


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found a duplicate key",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def resolve_config_path(environment: Mapping[str, str] | None = None) -> Path:
    """Return the effective optional user configuration path."""

    env = os.environ if environment is None else environment
    config_home = env.get("XDG_CONFIG_HOME")
    if config_home:
        configured_path = Path(config_home).expanduser()
        if configured_path.is_absolute():
            return configured_path / "mowftee" / "config.yaml"

    home_path = Path(env["HOME"]).expanduser() if env.get("HOME") else Path.home()
    base_path = home_path if home_path.is_absolute() else Path.home()
    base_path /= ".config"
    return base_path / "mowftee" / "config.yaml"


def deep_merge(base: ConfigMapping, override: ConfigMapping) -> ConfigDict:
    """Recursively merge mappings without mutating either input."""

    result: ConfigDict = copy.deepcopy(dict(base))
    for key, value in override.items():
        existing = result.get(key)
        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            result[key] = deep_merge(existing, value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _parse_environment_value(raw_value: str) -> Any:
    normalized = raw_value.strip()
    lowered = normalized.casefold()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none", "~"}:
        return None
    if _INTEGER_PATTERN.fullmatch(normalized):
        return int(normalized)
    if _FLOAT_PATTERN.fullmatch(normalized):
        return float(normalized)
    return raw_value


def apply_environment_overrides(
    config: ConfigMapping,
    environment: Mapping[str, str] | None = None,
) -> ConfigDict:
    """Apply MOWFTEE_ overrides using double underscores for nested keys."""

    env = os.environ if environment is None else environment
    overrides: ConfigDict = {}

    for variable_name, raw_value in env.items():
        if not variable_name.startswith(ENVIRONMENT_PREFIX):
            continue

        suffix = variable_name[len(ENVIRONMENT_PREFIX) :]
        parts = [part.lower() for part in suffix.split("__")]
        if not suffix or any(not part for part in parts):
            raise ConfigError(f"Invalid environment override name: {variable_name}")

        target = overrides
        for part in parts[:-1]:
            if part not in target:
                child = {}
                target[part] = child
            else:
                child = target[part]
                if not isinstance(child, dict):
                    raise ConfigError(f"Conflicting environment override: {variable_name}")
            target = child
        if isinstance(target.get(parts[-1]), dict):
            raise ConfigError(f"Conflicting environment override: {variable_name}")
        target[parts[-1]] = _parse_environment_value(raw_value)

    return deep_merge(config, overrides)


def _load_yaml_mapping(path: Path, *, required: bool) -> ConfigDict:
    if not path.exists():
        if required:
            raise ConfigError(f"Required configuration file is missing: {path}")
        return {}

    try:
        with path.open("r", encoding="utf-8") as config_file:
            loaded = yaml.load(config_file, Loader=_UniqueKeySafeLoader)
    except (OSError, TypeError, UnicodeError, yaml.YAMLError):
        raise ConfigError(f"Could not read valid YAML configuration from {path}") from None

    if loaded is None:
        return {}
    if not isinstance(loaded, Mapping):
        raise ConfigError(f"Configuration root must be a mapping: {path}")
    return copy.deepcopy(dict(loaded))


def _load_default_config() -> ConfigDict:
    if DEFAULT_CONFIG_PATH.is_file():
        return _load_yaml_mapping(DEFAULT_CONFIG_PATH, required=True)

    try:
        packaged_default = resources.files("mowftee").joinpath("default.yaml")
        with resources.as_file(packaged_default) as packaged_path:
            return _load_yaml_mapping(packaged_path, required=True)
    except (FileNotFoundError, ModuleNotFoundError, TypeError):
        raise ConfigError("Required default configuration is unavailable") from None


def _require_section(config: ConfigMapping, section_name: str) -> ConfigMapping:
    section = config.get(section_name)
    if not isinstance(section, Mapping):
        raise ConfigValidationError(f"Field '{section_name}' must be a mapping")
    return section


def _require_bool(section: ConfigMapping, field_path: str, field_name: str) -> None:
    if not isinstance(section.get(field_name), bool):
        raise ConfigValidationError(f"Field '{field_path}' must be a boolean")


def validate_config(config: ConfigMapping) -> ConfigDict:
    """Validate the initial configuration schema and return a safe copy."""

    validated = copy.deepcopy(dict(config))

    schema_version = validated.get("config_schema_version")
    if type(schema_version) is not int or schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ConfigValidationError("Field 'config_schema_version' must be 1")

    paths = _require_section(validated, "paths")
    model_dir = paths.get("model_dir")
    if not isinstance(model_dir, str) or not model_dir.strip():
        raise ConfigValidationError("Field 'paths.model_dir' must be a non-empty path")

    logging_config = _require_section(validated, "logging")
    level = logging_config.get("level")
    if not isinstance(level, str) or level not in VALID_LOG_LEVELS:
        raise ConfigValidationError(
            "Field 'logging.level' must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL"
        )

    _require_bool(logging_config, "logging.console", "console")
    _require_bool(logging_config, "logging.file", "file")

    max_bytes = logging_config.get("max_bytes")
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ConfigValidationError("Field 'logging.max_bytes' must be an integer greater than 0")

    backup_count = logging_config.get("backup_count")
    if type(backup_count) is not int or backup_count < 0:
        raise ConfigValidationError(
            "Field 'logging.backup_count' must be a non-negative integer"
        )

    privacy = _require_section(validated, "privacy")
    for flag_name in PRIVACY_FLAGS:
        _require_bool(privacy, f"privacy.{flag_name}", flag_name)

    return validated


def load_config(
    cli_overrides: ConfigMapping | None = None,
    *,
    config_path: Path | None = None,
    default_path: Path | None = None,
    environment: Mapping[str, str] | None = None,
) -> ConfigDict:
    """Load, merge, and validate configuration in precedence order."""

    env = os.environ if environment is None else environment
    default_config = (
        _load_yaml_mapping(default_path, required=True)
        if default_path is not None
        else _load_default_config()
    )
    user_config = _load_yaml_mapping(config_path or resolve_config_path(env), required=False)

    merged = deep_merge(default_config, user_config)
    merged = apply_environment_overrides(merged, env)
    if cli_overrides is not None:
        if not isinstance(cli_overrides, Mapping):
            raise ConfigError("CLI overrides must be a mapping")
        merged = deep_merge(merged, cli_overrides)

    return validate_config(merged)
