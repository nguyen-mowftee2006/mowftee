from __future__ import annotations

import copy
import traceback
from pathlib import Path

import pytest

from mowftee import config as config_module
from mowftee.config import (
    ConfigError,
    ConfigValidationError,
    apply_environment_overrides,
    deep_merge,
    load_config,
    resolve_config_path,
    validate_config,
)


def isolated_environment(tmp_path: Path, **overrides: str) -> dict[str, str]:
    environment = {"XDG_CONFIG_HOME": str(tmp_path / "config")}
    environment.update(overrides)
    return environment


def write_yaml(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def valid_config() -> dict[str, object]:
    return load_config(environment={"XDG_CONFIG_HOME": "/does/not/exist"})


def test_load_default_config(tmp_path: Path) -> None:
    config = load_config(environment=isolated_environment(tmp_path))

    assert config["config_schema_version"] == 1
    assert config["logging"]["level"] == "INFO"  # type: ignore[index]
    assert config["privacy"]["log_prompts"] is False  # type: ignore[index]


def test_missing_optional_user_config(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.yaml"

    config = load_config(
        config_path=missing_path,
        environment=isolated_environment(tmp_path),
    )

    assert config["paths"]["model_dir"] == "/srv/mowftee/models/ollama"  # type: ignore[index]


def test_user_config_nested_override_preserves_siblings(tmp_path: Path) -> None:
    user_config = write_yaml(
        tmp_path / "config.yaml",
        "logging:\n  level: WARNING\nprivacy:\n  log_prompts: true\n",
    )

    config = load_config(
        config_path=user_config,
        environment=isolated_environment(tmp_path),
    )

    assert config["logging"]["level"] == "WARNING"  # type: ignore[index]
    assert config["logging"]["console"] is True  # type: ignore[index]
    assert config["privacy"]["log_prompts"] is True  # type: ignore[index]
    assert config["privacy"]["log_conversations"] is False  # type: ignore[index]


def test_precedence_cli_over_environment_user_and_default(tmp_path: Path) -> None:
    user_config = write_yaml(tmp_path / "config.yaml", "logging:\n  level: WARNING\n")
    environment = isolated_environment(
        tmp_path,
        MOWFTEE_LOGGING__LEVEL="ERROR",
    )

    config = load_config(
        {"logging": {"level": "CRITICAL"}},
        config_path=user_config,
        environment=environment,
    )

    assert config["logging"]["level"] == "CRITICAL"  # type: ignore[index]


def test_environment_override_parses_scalar_types() -> None:
    base = {
        "logging": {"console": True, "max_bytes": 1},
        "extra": {},
    }
    environment = {
        "MOWFTEE_LOGGING__CONSOLE": "FaLsE",
        "MOWFTEE_LOGGING__MAX_BYTES": "2048",
        "MOWFTEE_EXTRA__RATIO": "1.25",
        "MOWFTEE_EXTRA__EMPTY": "null",
        "MOWFTEE_EXTRA__LABEL": "development",
    }

    result = apply_environment_overrides(base, environment)

    assert result["logging"] == {"console": False, "max_bytes": 2048}
    assert result["extra"] == {
        "ratio": 1.25,
        "empty": None,
        "label": "development",
    }


def test_resolve_config_path_uses_xdg_and_default_home(
    tmp_path: Path,
) -> None:
    assert resolve_config_path({"XDG_CONFIG_HOME": str(tmp_path)}) == (
        tmp_path / "mowftee" / "config.yaml"
    )

    assert resolve_config_path({"HOME": str(tmp_path / "home")}) == (
        tmp_path / "home" / ".config" / "mowftee" / "config.yaml"
    )
    assert resolve_config_path(
        {
            "HOME": str(tmp_path / "home"),
            "XDG_CONFIG_HOME": "relative/config",
        }
    ) == (tmp_path / "home" / ".config" / "mowftee" / "config.yaml")


def test_malformed_yaml_is_not_silently_ignored(tmp_path: Path) -> None:
    user_config = write_yaml(tmp_path / "config.yaml", "logging: [\n")

    with pytest.raises(ConfigError, match="valid YAML"):
        load_config(
            config_path=user_config,
            environment=isolated_environment(tmp_path),
        )


def test_malformed_yaml_traceback_does_not_retain_file_contents(tmp_path: Path) -> None:
    private_marker = "synthetic-private-marker"
    user_config = write_yaml(
        tmp_path / "config.yaml",
        f"logging: [{private_marker}\n",
    )

    try:
        load_config(
            config_path=user_config,
            environment=isolated_environment(tmp_path),
        )
    except ConfigError as error:
        rendered_traceback = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        assert error.__cause__ is None
        assert private_marker not in rendered_traceback
    else:
        pytest.fail("Malformed YAML must raise ConfigError")


def test_duplicate_yaml_key_is_rejected(tmp_path: Path) -> None:
    user_config = write_yaml(
        tmp_path / "config.yaml",
        "logging:\n  level: INFO\n  level: DEBUG\n",
    )

    with pytest.raises(ConfigError, match="valid YAML"):
        load_config(
            config_path=user_config,
            environment=isolated_environment(tmp_path),
        )


def test_missing_required_default_config(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="Required configuration file is missing"):
        load_config(
            default_path=tmp_path / "absent.yaml",
            environment=isolated_environment(tmp_path),
        )


def test_default_config_falls_back_to_packaged_resource(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packaged_directory = tmp_path / "packaged"
    packaged_directory.mkdir()
    (packaged_directory / "default.yaml").write_text(
        config_module.DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(config_module, "DEFAULT_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.setattr(config_module.resources, "files", lambda package: packaged_directory)

    config = load_config(environment=isolated_environment(tmp_path))

    assert config["config_schema_version"] == 1


@pytest.mark.parametrize(
    ("update", "field_name"),
    [
        ({"config_schema_version": 2}, "config_schema_version"),
        ({"logging": {"level": "TRACE"}}, "logging.level"),
        ({"logging": {"max_bytes": 0}}, "logging.max_bytes"),
        ({"logging": {"backup_count": -1}}, "logging.backup_count"),
        ({"privacy": {"log_prompts": "yes"}}, "privacy.log_prompts"),
        ({"paths": {"model_dir": "  "}}, "paths.model_dir"),
        ({"llm": "invalid"}, "llm"),
        ({"llm": {"provider": ""}}, "llm.provider"),
        ({"llm": {"provider": 123}}, "llm.provider"),
        ({"llm": {"model": "  "}}, "llm.model"),
        ({"llm": {"base_url": "ftp://localhost"}}, "llm.base_url"),
        ({"llm": {"base_url": "http://"}}, "llm.base_url"),
        ({"llm": {"timeout": 0}}, "llm.timeout"),
        ({"llm": {"timeout": -5.0}}, "llm.timeout"),
        ({"llm": {"timeout": True}}, "llm.timeout"),
        ({"llm": {"timeout": float("nan")}}, "llm.timeout"),
        ({"llm": {"timeout": float("inf")}}, "llm.timeout"),
        ({"llm": {"timeout": float("-inf")}}, "llm.timeout"),
        ({"llm": {"health_timeout": 0.0}}, "llm.health_timeout"),
        ({"llm": {"health_timeout": False}}, "llm.health_timeout"),
        ({"llm": {"health_timeout": float("nan")}}, "llm.health_timeout"),
        ({"llm": {"health_timeout": float("inf")}}, "llm.health_timeout"),
        ({"llm": {"health_timeout": float("-inf")}}, "llm.health_timeout"),
    ],
)
def test_invalid_values_report_field(update: dict[str, object], field_name: str) -> None:
    config = deep_merge(valid_config(), update)

    with pytest.raises(ConfigValidationError, match=field_name):
        validate_config(config)


def test_default_llm_config_loaded(tmp_path: Path) -> None:
    config = load_config(environment=isolated_environment(tmp_path))

    assert config["llm"]["provider"] == "ollama"  # type: ignore[index]
    assert config["llm"]["model"] == "qwen3:4b-instruct"  # type: ignore[index]
    assert config["llm"]["base_url"] == "http://127.0.0.1:11434"  # type: ignore[index]
    assert config["llm"]["timeout"] == 30.0  # type: ignore[index]
    assert config["llm"]["health_timeout"] == 2.0  # type: ignore[index]


def test_llm_env_overrides(tmp_path: Path) -> None:
    environment = isolated_environment(
        tmp_path,
        MOWFTEE_LLM__MODEL="llama3.2:3b",
        MOWFTEE_LLM__TIMEOUT="45.5",
        MOWFTEE_LLM__HEALTH_TIMEOUT="5",
    )
    config = load_config(environment=environment)

    assert config["llm"]["model"] == "llama3.2:3b"  # type: ignore[index]
    assert config["llm"]["timeout"] == 45.5  # type: ignore[index]
    assert config["llm"]["health_timeout"] == 5  # type: ignore[index]



def test_deep_merge_and_loader_do_not_mutate_inputs(tmp_path: Path) -> None:
    base = {"section": {"items": [1, 2], "keep": True}}
    override = {"section": {"items": [3]}}
    base_before = copy.deepcopy(base)
    override_before = copy.deepcopy(override)

    merged = deep_merge(base, override)
    merged["section"]["items"].append(4)  # type: ignore[index,union-attr]

    assert base == base_before
    assert override == override_before

    cli_overrides = {"logging": {"level": "DEBUG"}}
    cli_before = copy.deepcopy(cli_overrides)
    load_config(
        cli_overrides,
        environment=isolated_environment(tmp_path),
    )
    assert cli_overrides == cli_before


@pytest.mark.parametrize(
    "environment",
    [
        {
            "MOWFTEE_LOGGING": "disabled",
            "MOWFTEE_LOGGING__LEVEL": "DEBUG",
        },
        {
            "MOWFTEE_LOGGING": "null",
            "MOWFTEE_LOGGING__LEVEL": "DEBUG",
        },
        {
            "MOWFTEE_LOGGING__LEVEL": "DEBUG",
            "MOWFTEE_LOGGING": "null",
        },
    ],
)
def test_conflicting_environment_overrides_are_rejected(
    environment: dict[str, str],
) -> None:
    with pytest.raises(ConfigError, match="Conflicting environment override"):
        apply_environment_overrides({}, environment)
