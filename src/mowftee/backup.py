"""Encrypted backup and safe restore tooling for Mowftee."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tarfile
import tempfile
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from mowftee import __version__

BACKUP_SCHEMA_VERSION = 1
ARCHIVE_ROOT = PurePosixPath("mowftee-backup")
MANIFEST_PATH = ARCHIVE_ROOT / "manifest.json"
CHECKSUMS_PATH = ARCHIVE_ROOT / "checksums.sha256"
ARCHIVE_FORMAT = "pax-tar"
COMPRESSION = "gzip"
ENCRYPTION = "gpg-symmetric-aes256"
STORAGE_STATUS = "local_staging"
SQLITE_BACKUP_METHOD = "sqlite3.Connection.backup()"

EXIT_CLI = 2
EXIT_PREREQUISITE = 3
EXIT_SOURCE = 4
EXIT_ARCHIVE = 5
EXIT_RESTORE = 6

LOCAL_STAGING_WARNING = (
    "Archive này chỉ là local staging và chưa được coi là backup ngoài máy.\n"
    "Hãy upload lên cloud và thực hiện G0-06B."
)

_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MODE_PATTERN = re.compile(r"^[0-7]{4}$")
_CONTROL_FILE_LIMIT = 16 * 1024 * 1024
_COPY_CHUNK_SIZE = 1024 * 1024
_SOURCE_NAMES = {
    "user_config",
    "custom_persona",
    "memory_sqlite",
    "custom_voices",
    "custom_lora",
    "private_rag",
    "conversation_history",
    "audit_log",
    "important_benchmarks",
}
_EXCLUDED_CATEGORIES = [
    "public_ollama_models",
    "xdg_cache",
    "runtime_logs",
    "temporary_audio",
    "project_virtualenv",
    "git_source",
    "build_artifacts",
]


class BackupToolError(Exception):
    """A sanitized failure with a stable process exit code."""

    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


@dataclass(frozen=True)
class BackupOptions:
    """Options accepted by the production backup command."""

    target: Path
    include_conversations: bool = False
    include_audit: bool = False
    include_benchmarks: bool = False


@dataclass(frozen=True)
class RestoreOptions:
    """Options accepted by the production restore command."""

    archive: Path
    destination: Path


@dataclass(frozen=True)
class BackupResult:
    """Paths published by a successful backup."""

    archive: Path
    sidecar: Path


@dataclass(frozen=True)
class RestoreResult:
    """Destination published by a successful restore."""

    destination: Path


@dataclass(frozen=True)
class _GPGTestContext:
    """Private loopback-only context used by automated tests."""

    homedir: Path
    passphrase_file: Path


@dataclass(frozen=True)
class _SourceSpec:
    name: str
    path: Path
    archive_path: PurePosixPath
    kind: str
    optional: bool = False


@dataclass(frozen=True)
class _StagedFile:
    archive_path: PurePosixPath
    staged_path: Path
    original_mode: int
    size: int
    mtime_ns: int
    sha256: str

    def manifest_entry(self) -> dict[str, object]:
        return {
            "archive_path": self.archive_path.as_posix(),
            "type": "regular",
            "mode": f"{self.original_mode:04o}",
            "size": self.size,
            "mtime_utc": _timestamp_from_ns(self.mtime_ns),
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class _ValidatedManifest:
    document: dict[str, Any]
    files: dict[str, dict[str, Any]]


def _timestamp_from_ns(timestamp_ns: int) -> str:
    return (
        datetime.fromtimestamp(timestamp_ns / 1_000_000_000, UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


def _safe_xdg_base(
    environment: Mapping[str, str], variable: str, fallback: Path
) -> Path:
    configured = environment.get(variable)
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_absolute():
            return candidate
    return fallback


def _resolve_xdg_roots(environment: Mapping[str, str]) -> dict[str, Path]:
    configured_home = environment.get("HOME")
    home = Path(configured_home).expanduser() if configured_home else Path.home()
    if not home.is_absolute():
        home = Path.home()
    return {
        "config": _safe_xdg_base(environment, "XDG_CONFIG_HOME", home / ".config"),
        "data": _safe_xdg_base(
            environment, "XDG_DATA_HOME", home / ".local" / "share"
        ),
        "state": _safe_xdg_base(
            environment, "XDG_STATE_HOME", home / ".local" / "state"
        ),
        "cache": _safe_xdg_base(environment, "XDG_CACHE_HOME", home / ".cache"),
    }


def _source_specs(
    environment: Mapping[str, str], options: BackupOptions
) -> list[_SourceSpec]:
    roots = _resolve_xdg_roots(environment)
    config_root = roots["config"] / "mowftee"
    data_root = roots["data"] / "mowftee"
    state_root = roots["state"] / "mowftee"

    specs = [
        _SourceSpec(
            "user_config",
            config_root / "config.yaml",
            ARCHIVE_ROOT / "config/mowftee/config.yaml",
            "file",
        ),
        _SourceSpec(
            "custom_persona",
            config_root / "persona",
            ARCHIVE_ROOT / "config/mowftee/persona",
            "directory",
        ),
        _SourceSpec(
            "memory_sqlite",
            data_root / "memory/mowftee.sqlite3",
            ARCHIVE_ROOT / "data/mowftee/memory/mowftee.sqlite3",
            "sqlite",
        ),
        _SourceSpec(
            "custom_voices",
            data_root / "artifacts/voices",
            ARCHIVE_ROOT / "data/mowftee/artifacts/voices",
            "directory",
        ),
        _SourceSpec(
            "custom_lora",
            data_root / "artifacts/lora",
            ARCHIVE_ROOT / "data/mowftee/artifacts/lora",
            "directory",
        ),
        _SourceSpec(
            "private_rag",
            data_root / "rag",
            ARCHIVE_ROOT / "data/mowftee/rag",
            "directory",
        ),
    ]
    if options.include_conversations:
        specs.append(
            _SourceSpec(
                "conversation_history",
                data_root / "conversations",
                ARCHIVE_ROOT / "optional/conversations",
                "directory",
                optional=True,
            )
        )
    if options.include_audit:
        specs.append(
            _SourceSpec(
                "audit_log",
                state_root / "audit",
                ARCHIVE_ROOT / "optional/audit",
                "directory",
                optional=True,
            )
        )
    if options.include_benchmarks:
        specs.append(
            _SourceSpec(
                "important_benchmarks",
                state_root / "benchmarks",
                ARCHIVE_ROOT / "optional/benchmarks",
                "directory",
                optional=True,
            )
        )
    return specs


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _paths_overlap(first: Path, second: Path) -> bool:
    return _is_relative_to(first, second) or _is_relative_to(second, first)


def _validate_target(
    target: Path,
    *,
    repository_root: Path,
    environment: Mapping[str, str],
) -> Path:
    try:
        resolved = target.expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        raise BackupToolError("Backup target must already exist", EXIT_PREREQUISITE) from None
    if not resolved.is_dir():
        raise BackupToolError("Backup target must be a directory", EXIT_PREREQUISITE)
    if not os.access(resolved, os.W_OK | os.X_OK):
        raise BackupToolError("Backup target is not writable", EXIT_PREREQUISITE)

    repo = repository_root.resolve()
    if _is_relative_to(resolved, repo):
        raise BackupToolError(
            "Backup target must be outside the repository", EXIT_PREREQUISITE
        )

    roots = _resolve_xdg_roots(environment)
    protected_roots = [
        roots["config"] / "mowftee",
        roots["data"] / "mowftee",
        roots["state"] / "mowftee",
        roots["cache"] / "mowftee",
    ]
    if any(_paths_overlap(resolved, path.resolve(strict=False)) for path in protected_roots):
        raise BackupToolError(
            "Backup target must not overlap Mowftee XDG data", EXIT_PREREQUISITE
        )

    model_root = Path("/srv/mowftee/models").resolve(strict=False)
    if _is_relative_to(resolved, model_root):
        raise BackupToolError(
            "Backup target must be outside the model directory", EXIT_PREREQUISITE
        )
    return resolved


def _validate_component(name: str) -> None:
    if name in {"", ".", ".."} or "\n" in name or "\r" in name:
        raise BackupToolError("Source contains an unsafe file name", EXIT_SOURCE)


def _validate_archive_path(path: PurePosixPath) -> None:
    if path.is_absolute() or not path.parts or path.parts[0] != ARCHIVE_ROOT.name:
        raise BackupToolError("Archive contains an unsafe path", EXIT_RESTORE)
    if any(part in {"", ".", ".."} or "\n" in part or "\r" in part for part in path.parts):
        raise BackupToolError("Archive contains an unsafe path", EXIT_RESTORE)


def _secure_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)


def _open_source_file(path: Path) -> tuple[int, os.stat_result]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        parent_fd = os.open(
            path.parent,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0),
        )
    except OSError:
        raise BackupToolError("Could not open a backup source", EXIT_SOURCE) from None
    try:
        descriptor = os.open(path.name, flags, dir_fd=parent_fd)
    except OSError:
        os.close(parent_fd)
        raise BackupToolError("Backup source is not a safe regular file", EXIT_SOURCE) from None
    os.close(parent_fd)
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode):
        os.close(descriptor)
        raise BackupToolError("Backup source is not a regular file", EXIT_SOURCE)
    return descriptor, info


def _copy_open_file(
    source_fd: int,
    source_before: os.stat_result,
    destination: Path,
    archive_path: PurePosixPath,
    *,
    after_copy_hook: Callable[[PurePosixPath], None] | None,
) -> _StagedFile:
    _validate_archive_path(archive_path)
    _secure_mkdir(destination.parent)
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    digest = hashlib.sha256()
    size = 0
    try:
        destination_fd = os.open(destination, flags, 0o600)
        try:
            with os.fdopen(destination_fd, "wb", closefd=True) as destination_file:
                while True:
                    chunk = os.read(source_fd, _COPY_CHUNK_SIZE)
                    if not chunk:
                        break
                    destination_file.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                destination_file.flush()
                os.fsync(destination_file.fileno())
        except BaseException:
            destination.unlink(missing_ok=True)
            raise

        if after_copy_hook is not None:
            after_copy_hook(archive_path)

        source_after = os.fstat(source_fd)
        stable_fields_before = (
            source_before.st_dev,
            source_before.st_ino,
            source_before.st_size,
            source_before.st_mtime_ns,
            source_before.st_ctime_ns,
        )
        stable_fields_after = (
            source_after.st_dev,
            source_after.st_ino,
            source_after.st_size,
            source_after.st_mtime_ns,
            source_after.st_ctime_ns,
        )
        if stable_fields_before != stable_fields_after or size != source_before.st_size:
            destination.unlink(missing_ok=True)
            raise BackupToolError("Backup source changed while being read", EXIT_SOURCE)

        os.chmod(destination, 0o600)
        os.utime(
            destination,
            ns=(source_before.st_mtime_ns, source_before.st_mtime_ns),
            follow_symlinks=False,
        )
        return _StagedFile(
            archive_path=archive_path,
            staged_path=destination,
            original_mode=stat.S_IMODE(source_before.st_mode),
            size=size,
            mtime_ns=source_before.st_mtime_ns,
            sha256=digest.hexdigest(),
        )
    except BackupToolError:
        raise
    except OSError:
        destination.unlink(missing_ok=True)
        raise BackupToolError("Could not stage a backup source", EXIT_SOURCE) from None


def _stage_regular_file(
    source: Path,
    destination: Path,
    archive_path: PurePosixPath,
    *,
    after_copy_hook: Callable[[PurePosixPath], None] | None,
) -> _StagedFile:
    source_fd, source_before = _open_source_file(source)
    try:
        return _copy_open_file(
            source_fd,
            source_before,
            destination,
            archive_path,
            after_copy_hook=after_copy_hook,
        )
    finally:
        os.close(source_fd)


def _stage_directory(
    source: Path,
    destination_root: Path,
    archive_root: PurePosixPath,
    *,
    after_copy_hook: Callable[[PurePosixPath], None] | None,
) -> list[_StagedFile]:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        root_fd = os.open(source, flags)
    except OSError:
        raise BackupToolError("Backup directory is not safe to read", EXIT_SOURCE) from None
    try:
        if not stat.S_ISDIR(os.fstat(root_fd).st_mode):
            raise BackupToolError("Backup source is not a directory", EXIT_SOURCE)
        return _stage_directory_fd(
            root_fd,
            destination_root,
            archive_root,
            after_copy_hook=after_copy_hook,
        )
    finally:
        os.close(root_fd)


def _stage_directory_fd(
    directory_fd: int,
    destination_root: Path,
    archive_root: PurePosixPath,
    *,
    after_copy_hook: Callable[[PurePosixPath], None] | None,
) -> list[_StagedFile]:
    before = os.fstat(directory_fd)
    try:
        with os.scandir(directory_fd) as iterator:
            names = sorted(entry.name for entry in iterator)
    except OSError:
        raise BackupToolError("Could not enumerate a backup directory", EXIT_SOURCE) from None

    staged: list[_StagedFile] = []
    for name in names:
        _validate_component(name)
        try:
            info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except OSError:
            raise BackupToolError("Backup source changed while being read", EXIT_SOURCE) from None

        archive_path = archive_root / name
        destination = destination_root / name
        if stat.S_ISLNK(info.st_mode):
            raise BackupToolError("Symlinks are not allowed in backup sources", EXIT_SOURCE)
        if stat.S_ISDIR(info.st_mode):
            flags = (
                os.O_RDONLY
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0)
            )
            try:
                child_fd = os.open(name, flags, dir_fd=directory_fd)
            except OSError:
                raise BackupToolError(
                    "Backup source changed while being read", EXIT_SOURCE
                ) from None
            try:
                child_info = os.fstat(child_fd)
                if (child_info.st_dev, child_info.st_ino) != (info.st_dev, info.st_ino):
                    raise BackupToolError(
                        "Backup source changed while being read", EXIT_SOURCE
                    )
                staged.extend(
                    _stage_directory_fd(
                        child_fd,
                        destination,
                        archive_path,
                        after_copy_hook=after_copy_hook,
                    )
                )
            finally:
                os.close(child_fd)
            continue
        if not stat.S_ISREG(info.st_mode):
            raise BackupToolError("Special files are not allowed in backup sources", EXIT_SOURCE)

        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            source_fd = os.open(name, flags, dir_fd=directory_fd)
        except OSError:
            raise BackupToolError("Backup source changed while being read", EXIT_SOURCE) from None
        try:
            opened_info = os.fstat(source_fd)
            if (opened_info.st_dev, opened_info.st_ino) != (info.st_dev, info.st_ino):
                raise BackupToolError("Backup source changed while being read", EXIT_SOURCE)
            staged.append(
                _copy_open_file(
                    source_fd,
                    opened_info,
                    destination,
                    archive_path,
                    after_copy_hook=after_copy_hook,
                )
            )
        finally:
            os.close(source_fd)

    try:
        with os.scandir(directory_fd) as iterator:
            names_after = sorted(entry.name for entry in iterator)
        after = os.fstat(directory_fd)
    except OSError:
        raise BackupToolError("Backup source changed while being read", EXIT_SOURCE) from None
    before_fields = (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_ctime_ns)
    after_fields = (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns)
    if names != names_after or before_fields != after_fields:
        raise BackupToolError("Backup source changed while being read", EXIT_SOURCE)
    return staged


def _stage_sqlite(
    source: Path,
    destination: Path,
    archive_path: PurePosixPath,
) -> _StagedFile:
    try:
        source_info = source.lstat()
    except OSError:
        raise BackupToolError("Could not inspect the SQLite source", EXIT_SOURCE) from None
    if stat.S_ISLNK(source_info.st_mode) or not stat.S_ISREG(source_info.st_mode):
        raise BackupToolError("SQLite source must be a regular file", EXIT_SOURCE)

    _secure_mkdir(destination.parent)
    try:
        descriptor = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0),
            0o600,
        )
        os.close(descriptor)
        source_uri = source.resolve(strict=True).as_uri() + "?mode=ro"
        with sqlite3.connect(source_uri, uri=True, timeout=5.0) as source_db:
            source_db.execute("PRAGMA busy_timeout = 5000")
            with sqlite3.connect(destination, timeout=5.0) as destination_db:
                source_db.backup(destination_db, pages=256, sleep=0.01)
                result = destination_db.execute("PRAGMA quick_check").fetchall()
                if result != [("ok",)]:
                    raise BackupToolError("SQLite snapshot failed its integrity check", EXIT_SOURCE)
        os.chmod(destination, 0o600)
        staged_info = destination.stat()
        digest = _hash_path(destination)
        return _StagedFile(
            archive_path=archive_path,
            staged_path=destination,
            original_mode=0o600,
            size=staged_info.st_size,
            mtime_ns=staged_info.st_mtime_ns,
            sha256=digest,
        )
    except BackupToolError:
        destination.unlink(missing_ok=True)
        raise
    except (OSError, sqlite3.Error):
        destination.unlink(missing_ok=True)
        raise BackupToolError("Could not create a consistent SQLite snapshot", EXIT_SOURCE) from None


def _hash_file(file_object: BinaryIO) -> str:
    digest = hashlib.sha256()
    while True:
        chunk = file_object.read(_COPY_CHUNK_SIZE)
        if not chunk:
            break
        digest.update(chunk)
    return digest.hexdigest()


def _hash_path(path: Path) -> str:
    try:
        with path.open("rb") as file_object:
            return _hash_file(file_object)
    except OSError:
        raise BackupToolError("Could not hash an artifact", EXIT_ARCHIVE) from None


def _json_bytes(document: Mapping[str, object]) -> bytes:
    return (
        json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _checksums_bytes(manifest_bytes: bytes, files: Sequence[_StagedFile]) -> bytes:
    lines = [f"{hashlib.sha256(manifest_bytes).hexdigest()}  {MANIFEST_PATH.as_posix()}"]
    lines.extend(
        f"{item.sha256}  {item.archive_path.as_posix()}"
        for item in sorted(files, key=lambda entry: entry.archive_path.as_posix())
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


def _tar_info(name: PurePosixPath, size: int, mtime: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name.as_posix())
    info.type = tarfile.REGTYPE
    info.size = size
    info.mode = 0o600
    info.mtime = mtime
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    return info


def _write_plain_archive(
    destination: Path,
    *,
    manifest_bytes: bytes,
    checksums_bytes: bytes,
    files: Sequence[_StagedFile],
    created_at: datetime,
) -> None:
    descriptor = os.open(
        destination,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as raw_file, gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=raw_file,
                mtime=int(created_at.timestamp()),
            ) as gzip_file, tarfile.open(
                fileobj=gzip_file,
                mode="w|",
                format=tarfile.PAX_FORMAT,
            ) as archive:
            control_mtime = int(created_at.timestamp())
            archive.addfile(
                _tar_info(MANIFEST_PATH, len(manifest_bytes), control_mtime),
                _BytesReader(manifest_bytes),
            )
            archive.addfile(
                _tar_info(CHECKSUMS_PATH, len(checksums_bytes), control_mtime),
                _BytesReader(checksums_bytes),
            )
            for item in sorted(files, key=lambda entry: entry.archive_path.as_posix()):
                with item.staged_path.open("rb") as source_file:
                    archive.addfile(
                        _tar_info(
                            item.archive_path,
                            item.size,
                            item.mtime_ns // 1_000_000_000,
                        ),
                        source_file,
                    )
            raw_file.flush()
            os.fsync(raw_file.fileno())
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    os.chmod(destination, 0o600)


class _BytesReader:
    def __init__(self, content: bytes) -> None:
        self._content = content
        self._position = 0

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._content) - self._position
        start = self._position
        end = min(len(self._content), start + size)
        self._position = end
        return self._content[start:end]


def _gpg_environment(test_context: _GPGTestContext | None) -> dict[str, str]:
    environment = dict(os.environ)
    if test_context is not None:
        environment["GNUPGHOME"] = str(test_context.homedir)
    return environment


def _gpg_common_test_args(test_context: _GPGTestContext | None) -> list[str]:
    if test_context is None:
        return ["--pinentry-mode", "ask"]
    return [
        "--batch",
        "--yes",
        "--pinentry-mode",
        "loopback",
        "--passphrase-file",
        str(test_context.passphrase_file),
    ]


def _require_gpg() -> str:
    executable = shutil.which("gpg")
    if executable is None:
        raise BackupToolError("GPG is required", EXIT_PREREQUISITE)
    return executable


def _run_gpg_encrypt(
    plaintext: Path,
    encrypted_output: BinaryIO,
    *,
    test_context: _GPGTestContext | None,
) -> None:
    executable = _require_gpg()
    command = [
        executable,
        "--quiet",
        "--no-symkey-cache",
        *_gpg_common_test_args(test_context),
        "--symmetric",
        "--cipher-algo",
        "AES256",
        "--s2k-mode",
        "3",
        "--compress-algo",
        "none",
        "--set-filename",
        "mowftee-backup.tar.gz",
        "--output",
        "-",
    ]
    try:
        with plaintext.open("rb") as plaintext_file:
            result = subprocess.run(
                command,
                stdin=plaintext_file,
                stdout=encrypted_output,
                stderr=subprocess.PIPE,
                env=_gpg_environment(test_context),
                check=False,
            )
    except OSError:
        raise BackupToolError("Could not start GPG encryption", EXIT_ARCHIVE) from None
    if result.returncode != 0:
        raise BackupToolError("GPG encryption failed", EXIT_ARCHIVE)


def _run_gpg_decrypt(
    encrypted_input: BinaryIO,
    plaintext_output: BinaryIO,
    *,
    test_context: _GPGTestContext | None,
) -> None:
    executable = _require_gpg()
    command = [
        executable,
        "--quiet",
        "--no-symkey-cache",
        *_gpg_common_test_args(test_context),
        "--decrypt",
        "--output",
        "-",
    ]
    try:
        result = subprocess.run(
            command,
            stdin=encrypted_input,
            stdout=plaintext_output,
            stderr=subprocess.PIPE,
            env=_gpg_environment(test_context),
            check=False,
        )
    except OSError:
        raise BackupToolError("Could not start GPG decryption", EXIT_ARCHIVE) from None
    if result.returncode != 0:
        raise BackupToolError("GPG decryption failed", EXIT_ARCHIVE)


def _secure_create(path: Path) -> BinaryIO:
    descriptor = os.open(
        path,
        os.O_RDWR
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    return os.fdopen(descriptor, "w+b", closefd=True)


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _publish_archive(
    plaintext: Path,
    *,
    target: Path,
    archive_name: str,
    test_context: _GPGTestContext | None,
) -> BackupResult:
    archive = target / archive_name
    sidecar = Path(f"{archive}.sha256")
    archive_partial = target / f"{archive_name}.partial"
    sidecar_partial = target / f"{archive_name}.sha256.partial"
    if any(path.exists() or path.is_symlink() for path in (archive, sidecar)):
        raise BackupToolError("Backup artifact name already exists", EXIT_ARCHIVE)

    archive_published = False
    try:
        with _secure_create(archive_partial) as encrypted_file:
            _run_gpg_encrypt(
                plaintext,
                encrypted_file,
                test_context=test_context,
            )
            encrypted_file.flush()
            os.fsync(encrypted_file.fileno())
            encrypted_file.seek(0)
            outer_hash = _hash_file(encrypted_file)

        sidecar_content = f"{outer_hash}  {archive.name}\n".encode("ascii")
        with _secure_create(sidecar_partial) as sidecar_file:
            sidecar_file.write(sidecar_content)
            sidecar_file.flush()
            os.fsync(sidecar_file.fileno())

        if archive.exists() or sidecar.exists():
            raise BackupToolError("Backup artifact name already exists", EXIT_ARCHIVE)
        os.rename(archive_partial, archive)
        archive_published = True
        _fsync_directory(target)
        os.rename(sidecar_partial, sidecar)
        _fsync_directory(target)
        return BackupResult(archive=archive, sidecar=sidecar)
    except BackupToolError:
        if archive_published and not sidecar.exists():
            archive.unlink(missing_ok=True)
        raise
    except OSError:
        if archive_published and not sidecar.exists():
            archive.unlink(missing_ok=True)
        raise BackupToolError("Could not publish backup artifacts", EXIT_ARCHIVE) from None
    finally:
        archive_partial.unlink(missing_ok=True)
        sidecar_partial.unlink(missing_ok=True)


def create_backup(
    options: BackupOptions,
    *,
    environment: Mapping[str, str] | None = None,
    repository_root: Path | None = None,
    _test_gpg_context: _GPGTestContext | None = None,
    _now: Callable[[], datetime] = _utc_now,
    _id_factory: Callable[[], str] = _short_id,
    _after_copy_hook: Callable[[PurePosixPath], None] | None = None,
) -> BackupResult:
    """Create one encrypted local-staging archive."""

    env = os.environ if environment is None else environment
    repo = repository_root or _find_repository_root()
    target = _validate_target(options.target, repository_root=repo, environment=env)
    print(LOCAL_STAGING_WARNING, file=sys.stderr)

    created_at = _now().astimezone(UTC)
    short_identifier = _id_factory()
    if not re.fullmatch(r"[0-9A-Za-z]{4,32}", short_identifier):
        raise BackupToolError("Generated backup identifier is invalid", EXIT_ARCHIVE)
    archive_name = (
        f"mowftee-backup-{created_at.strftime('%Y%m%dT%H%M%SZ')}-"
        f"{short_identifier}.tar.gz.gpg"
    )

    previous_umask = os.umask(0o077)
    try:
        with tempfile.TemporaryDirectory(prefix="mowftee-backup-") as temporary:
            staging_root = Path(temporary)
            os.chmod(staging_root, 0o700)
            payload_root = staging_root / "payload"
            _secure_mkdir(payload_root)

            included_sources: list[str] = []
            missing_sources: list[str] = []
            staged_files: list[_StagedFile] = []

            for spec in _source_specs(env, options):
                try:
                    source_info = spec.path.lstat()
                except FileNotFoundError:
                    missing_sources.append(spec.name)
                    continue
                except OSError:
                    raise BackupToolError("Could not inspect a backup source", EXIT_SOURCE) from None
                if stat.S_ISLNK(source_info.st_mode):
                    raise BackupToolError("Symlinks are not allowed in backup sources", EXIT_SOURCE)

                included_sources.append(spec.name)
                relative_archive = spec.archive_path.relative_to(ARCHIVE_ROOT)
                staged_destination = payload_root.joinpath(*relative_archive.parts)
                if spec.kind == "file":
                    if not stat.S_ISREG(source_info.st_mode):
                        raise BackupToolError("Backup source has an unexpected type", EXIT_SOURCE)
                    staged_files.append(
                        _stage_regular_file(
                            spec.path,
                            staged_destination,
                            spec.archive_path,
                            after_copy_hook=_after_copy_hook,
                        )
                    )
                elif spec.kind == "directory":
                    if not stat.S_ISDIR(source_info.st_mode):
                        raise BackupToolError("Backup source has an unexpected type", EXIT_SOURCE)
                    staged_files.extend(
                        _stage_directory(
                            spec.path,
                            staged_destination,
                            spec.archive_path,
                            after_copy_hook=_after_copy_hook,
                        )
                    )
                elif spec.kind == "sqlite":
                    staged_files.append(
                        _stage_sqlite(spec.path, staged_destination, spec.archive_path)
                    )
                else:
                    raise BackupToolError("Unknown backup source type", EXIT_SOURCE)

            required_paths = {
                spec.archive_path
                for spec in _source_specs(env, options)
                if not spec.optional
            }
            has_required_payload = any(
                any(
                    file.archive_path == required or required in file.archive_path.parents
                    for required in required_paths
                )
                for file in staged_files
            )
            if not has_required_payload:
                raise BackupToolError(
                    "No required Mowftee data exists to back up", EXIT_SOURCE
                )

            archive_paths = [item.archive_path.as_posix() for item in staged_files]
            if len(archive_paths) != len(set(archive_paths)):
                raise BackupToolError("Backup sources map to duplicate archive paths", EXIT_SOURCE)

            manifest = {
                "backup_schema_version": BACKUP_SCHEMA_VERSION,
                "created_at_utc": created_at.isoformat(timespec="seconds").replace(
                    "+00:00", "Z"
                ),
                "mowftee_version": __version__,
                "python_version": ".".join(str(part) for part in sys.version_info[:3]),
                "sqlite_version": sqlite3.sqlite_version,
                "archive_format": ARCHIVE_FORMAT,
                "compression": COMPRESSION,
                "encryption": ENCRYPTION,
                "storage_status": STORAGE_STATUS,
                "sqlite_backup_method": SQLITE_BACKUP_METHOD,
                "included_sources": sorted(included_sources),
                "missing_sources": sorted(missing_sources),
                "excluded_categories": list(_EXCLUDED_CATEGORIES),
                "files": [
                    item.manifest_entry()
                    for item in sorted(
                        staged_files, key=lambda entry: entry.archive_path.as_posix()
                    )
                ],
            }
            manifest_bytes = _json_bytes(manifest)
            checksums_bytes = _checksums_bytes(manifest_bytes, staged_files)
            plaintext = staging_root / "mowftee-backup.tar.gz"
            try:
                _write_plain_archive(
                    plaintext,
                    manifest_bytes=manifest_bytes,
                    checksums_bytes=checksums_bytes,
                    files=staged_files,
                    created_at=created_at,
                )
                return _publish_archive(
                    plaintext,
                    target=target,
                    archive_name=archive_name,
                    test_context=_test_gpg_context,
                )
            except BackupToolError:
                raise
            except (OSError, tarfile.TarError):
                raise BackupToolError("Could not construct backup archive", EXIT_ARCHIVE) from None
    finally:
        os.umask(previous_umask)


def _read_outer_sidecar(archive: Path, sidecar: Path) -> str:
    try:
        sidecar_info = sidecar.lstat()
        if stat.S_ISLNK(sidecar_info.st_mode) or not stat.S_ISREG(sidecar_info.st_mode):
            raise BackupToolError("Backup checksum sidecar is unsafe", EXIT_RESTORE)
        if sidecar_info.st_size > 1024:
            raise BackupToolError("Backup checksum sidecar is invalid", EXIT_RESTORE)
        content = sidecar.read_text(encoding="ascii")
    except FileNotFoundError:
        raise BackupToolError("Backup checksum sidecar is missing", EXIT_RESTORE) from None
    except UnicodeError:
        raise BackupToolError("Backup checksum sidecar is invalid", EXIT_RESTORE) from None
    except OSError:
        raise BackupToolError("Could not read backup checksum sidecar", EXIT_RESTORE) from None
    match = re.fullmatch(r"([0-9a-f]{64})  ([^\r\n]+)\n", content)
    if match is None or match.group(2) != archive.name:
        raise BackupToolError("Backup checksum sidecar is invalid", EXIT_RESTORE)
    return match.group(1)


def _open_and_verify_archive(archive: Path, expected_hash: str) -> BinaryIO:
    try:
        archive_info = archive.lstat()
    except FileNotFoundError:
        raise BackupToolError("Backup archive is missing", EXIT_RESTORE) from None
    except OSError:
        raise BackupToolError("Could not inspect backup archive", EXIT_RESTORE) from None
    if stat.S_ISLNK(archive_info.st_mode) or not stat.S_ISREG(archive_info.st_mode):
        raise BackupToolError("Backup archive is unsafe", EXIT_RESTORE)

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(archive, flags)
        file_object = os.fdopen(descriptor, "rb", closefd=True)
        opened_before = os.fstat(file_object.fileno())
        actual_hash = _hash_file(file_object)
        opened_after = os.fstat(file_object.fileno())
        stable_before = (
            opened_before.st_dev,
            opened_before.st_ino,
            opened_before.st_size,
            opened_before.st_mtime_ns,
            opened_before.st_ctime_ns,
        )
        stable_after = (
            opened_after.st_dev,
            opened_after.st_ino,
            opened_after.st_size,
            opened_after.st_mtime_ns,
            opened_after.st_ctime_ns,
        )
        if stable_before != stable_after or actual_hash != expected_hash:
            file_object.close()
            raise BackupToolError("Backup archive checksum does not match", EXIT_RESTORE)
        file_object.seek(0)
        return file_object
    except BackupToolError:
        raise
    except OSError:
        raise BackupToolError("Could not verify backup archive", EXIT_RESTORE) from None


def _parse_json_document(content: bytes) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        document: dict[str, Any] = {}
        for key, value in pairs:
            if key in document:
                raise ValueError("duplicate JSON key")
            document[key] = value
        return document

    try:
        parsed = json.loads(content.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except (UnicodeError, ValueError, json.JSONDecodeError):
        raise BackupToolError("Backup manifest is invalid", EXIT_RESTORE) from None
    if not isinstance(parsed, dict):
        raise BackupToolError("Backup manifest is invalid", EXIT_RESTORE)
    return parsed


def _parse_utc_timestamp(value: object) -> int:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise BackupToolError("Backup manifest timestamp is invalid", EXIT_RESTORE)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise BackupToolError("Backup manifest timestamp is invalid", EXIT_RESTORE) from None
    if parsed.utcoffset() != UTC.utcoffset(parsed):
        raise BackupToolError("Backup manifest timestamp is invalid", EXIT_RESTORE)
    return int(parsed.timestamp() * 1_000_000_000)


def _validate_manifest(document: dict[str, Any]) -> _ValidatedManifest:
    required_keys = {
        "backup_schema_version",
        "created_at_utc",
        "mowftee_version",
        "python_version",
        "sqlite_version",
        "archive_format",
        "compression",
        "encryption",
        "storage_status",
        "sqlite_backup_method",
        "included_sources",
        "missing_sources",
        "excluded_categories",
        "files",
    }
    if set(document) != required_keys:
        raise BackupToolError("Backup manifest fields are invalid", EXIT_RESTORE)
    expected_values = {
        "backup_schema_version": BACKUP_SCHEMA_VERSION,
        "archive_format": ARCHIVE_FORMAT,
        "compression": COMPRESSION,
        "encryption": ENCRYPTION,
        "storage_status": STORAGE_STATUS,
        "sqlite_backup_method": SQLITE_BACKUP_METHOD,
    }
    if any(document.get(key) != value for key, value in expected_values.items()):
        raise BackupToolError("Backup manifest policy is unsupported", EXIT_RESTORE)
    _parse_utc_timestamp(document["created_at_utc"])
    for key in ("mowftee_version", "python_version", "sqlite_version"):
        if not isinstance(document[key], str) or not document[key]:
            raise BackupToolError("Backup manifest version metadata is invalid", EXIT_RESTORE)
    for key in ("included_sources", "missing_sources", "excluded_categories"):
        value = document[key]
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise BackupToolError("Backup manifest source metadata is invalid", EXIT_RESTORE)
        if len(value) != len(set(value)):
            raise BackupToolError("Backup manifest source metadata is invalid", EXIT_RESTORE)
    if not set(document["included_sources"]).issubset(_SOURCE_NAMES):
        raise BackupToolError("Backup manifest source metadata is invalid", EXIT_RESTORE)
    if not set(document["missing_sources"]).issubset(_SOURCE_NAMES):
        raise BackupToolError("Backup manifest source metadata is invalid", EXIT_RESTORE)
    if document["excluded_categories"] != _EXCLUDED_CATEGORIES:
        raise BackupToolError("Backup manifest exclusion policy is invalid", EXIT_RESTORE)

    raw_files = document["files"]
    if not isinstance(raw_files, list) or not raw_files:
        raise BackupToolError("Backup manifest has no payload files", EXIT_RESTORE)
    files: dict[str, dict[str, Any]] = {}
    for entry in raw_files:
        if not isinstance(entry, dict) or set(entry) != {
            "archive_path",
            "type",
            "mode",
            "size",
            "mtime_utc",
            "sha256",
        }:
            raise BackupToolError("Backup file metadata is invalid", EXIT_RESTORE)
        path_value = entry["archive_path"]
        if not isinstance(path_value, str):
            raise BackupToolError("Backup file path is invalid", EXIT_RESTORE)
        path = PurePosixPath(path_value)
        _validate_archive_path(path)
        if path in {MANIFEST_PATH, CHECKSUMS_PATH} or path_value in files:
            raise BackupToolError("Backup file path is duplicated", EXIT_RESTORE)
        if entry["type"] != "regular":
            raise BackupToolError("Backup file type is unsupported", EXIT_RESTORE)
        if not isinstance(entry["mode"], str) or _MODE_PATTERN.fullmatch(entry["mode"]) is None:
            raise BackupToolError("Backup file mode is invalid", EXIT_RESTORE)
        if type(entry["size"]) is not int or entry["size"] < 0:
            raise BackupToolError("Backup file size is invalid", EXIT_RESTORE)
        _parse_utc_timestamp(entry["mtime_utc"])
        if not isinstance(entry["sha256"], str) or _HASH_PATTERN.fullmatch(entry["sha256"]) is None:
            raise BackupToolError("Backup file checksum is invalid", EXIT_RESTORE)
        files[path_value] = entry

    file_paths = [PurePosixPath(path) for path in files]
    for path in file_paths:
        if any(parent.as_posix() in files for parent in path.parents):
            raise BackupToolError("Backup file paths conflict", EXIT_RESTORE)
    return _ValidatedManifest(document=document, files=files)


def _parse_internal_checksums(content: bytes) -> dict[str, str]:
    try:
        text = content.decode("utf-8")
    except UnicodeError:
        raise BackupToolError("Internal checksum file is invalid", EXIT_RESTORE) from None
    checksums: dict[str, str] = {}
    for line in text.splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\r\n]+)", line)
        if match is None:
            raise BackupToolError("Internal checksum file is invalid", EXIT_RESTORE)
        path = PurePosixPath(match.group(2))
        _validate_archive_path(path)
        path_value = path.as_posix()
        if path_value in checksums:
            raise BackupToolError("Internal checksum path is duplicated", EXIT_RESTORE)
        checksums[path_value] = match.group(1)
    if not checksums:
        raise BackupToolError("Internal checksum file is empty", EXIT_RESTORE)
    return checksums


def _read_tar_member(archive: tarfile.TarFile, member: tarfile.TarInfo, limit: int) -> bytes:
    if member.size > limit:
        raise BackupToolError("Archive control file is too large", EXIT_RESTORE)
    extracted = archive.extractfile(member)
    if extracted is None:
        raise BackupToolError("Archive control file is unreadable", EXIT_RESTORE)
    content = extracted.read(limit + 1)
    if len(content) != member.size or len(content) > limit:
        raise BackupToolError("Archive control file is invalid", EXIT_RESTORE)
    return content


def _preflight_archive(
    plaintext: Path,
) -> tuple[tarfile.TarFile, _ValidatedManifest, dict[str, str], dict[str, tarfile.TarInfo]]:
    try:
        archive = tarfile.open(plaintext, mode="r:gz")  # noqa: SIM115
        members = archive.getmembers()
    except (OSError, tarfile.TarError):
        raise BackupToolError("Decrypted archive is invalid", EXIT_RESTORE) from None
    try:
        by_name: dict[str, tarfile.TarInfo] = {}
        for member in members:
            path = PurePosixPath(member.name)
            _validate_archive_path(path)
            if member.name in by_name:
                raise BackupToolError("Archive member is duplicated", EXIT_RESTORE)
            if not member.isreg():
                raise BackupToolError("Archive contains an unsupported member", EXIT_RESTORE)
            by_name[member.name] = member

        manifest_member = by_name.get(MANIFEST_PATH.as_posix())
        checksums_member = by_name.get(CHECKSUMS_PATH.as_posix())
        if manifest_member is None or checksums_member is None:
            raise BackupToolError("Archive control files are missing", EXIT_RESTORE)
        manifest_bytes = _read_tar_member(archive, manifest_member, _CONTROL_FILE_LIMIT)
        checksums_bytes = _read_tar_member(archive, checksums_member, _CONTROL_FILE_LIMIT)
        validated = _validate_manifest(_parse_json_document(manifest_bytes))
        checksums = _parse_internal_checksums(checksums_bytes)

        expected_members = {
            MANIFEST_PATH.as_posix(),
            CHECKSUMS_PATH.as_posix(),
            *validated.files,
        }
        if set(by_name) != expected_members:
            raise BackupToolError("Archive contains a member outside its manifest", EXIT_RESTORE)
        expected_checksums = {MANIFEST_PATH.as_posix(), *validated.files}
        if set(checksums) != expected_checksums:
            raise BackupToolError("Internal checksum coverage is invalid", EXIT_RESTORE)
        if checksums[MANIFEST_PATH.as_posix()] != hashlib.sha256(manifest_bytes).hexdigest():
            raise BackupToolError("Backup manifest checksum does not match", EXIT_RESTORE)

        for path, metadata in validated.files.items():
            member = by_name[path]
            if member.size != metadata["size"]:
                raise BackupToolError("Backup member size does not match manifest", EXIT_RESTORE)
            if checksums[path] != metadata["sha256"]:
                raise BackupToolError("Backup file checksum metadata conflicts", EXIT_RESTORE)
        return archive, validated, checksums, by_name
    except BaseException:
        archive.close()
        raise


def _validate_destination(
    destination: Path,
    *,
    repository_root: Path,
    environment: Mapping[str, str],
) -> Path:
    expanded = destination.expanduser()
    if expanded.exists() or expanded.is_symlink():
        raise BackupToolError("Restore destination must not already exist", EXIT_RESTORE)
    try:
        parent = expanded.parent.resolve(strict=True)
    except (OSError, RuntimeError):
        raise BackupToolError("Restore destination parent must exist", EXIT_RESTORE) from None
    if not parent.is_dir() or not os.access(parent, os.W_OK | os.X_OK):
        raise BackupToolError("Restore destination parent is not writable", EXIT_RESTORE)
    resolved = parent / expanded.name
    if resolved == Path("/"):
        raise BackupToolError("Restore destination is unsafe", EXIT_RESTORE)

    repo = repository_root.resolve()
    if _is_relative_to(resolved, repo):
        raise BackupToolError("Restore destination must be outside the repository", EXIT_RESTORE)
    roots = _resolve_xdg_roots(environment)
    live_roots = [
        roots["config"] / "mowftee",
        roots["data"] / "mowftee",
        roots["state"] / "mowftee",
        roots["cache"] / "mowftee",
    ]
    if any(_paths_overlap(resolved, path.resolve(strict=False)) for path in live_roots):
        raise BackupToolError("Restore destination must not be a live XDG path", EXIT_RESTORE)
    return resolved


def _extract_validated_archive(
    archive: tarfile.TarFile,
    validated: _ValidatedManifest,
    checksums: Mapping[str, str],
    members: Mapping[str, tarfile.TarInfo],
    publish_root: Path,
) -> None:
    total_size = sum(int(metadata["size"]) for metadata in validated.files.values())
    if total_size > shutil.disk_usage(publish_root.parent).free:
        raise BackupToolError("Not enough space for restored data", EXIT_RESTORE)

    root_directory = publish_root / ARCHIVE_ROOT.name
    _secure_mkdir(root_directory)
    for path_value in sorted(validated.files):
        metadata = validated.files[path_value]
        archive_path = PurePosixPath(path_value)
        relative = archive_path.relative_to(ARCHIVE_ROOT)
        destination = root_directory.joinpath(*relative.parts)
        _secure_mkdir(destination.parent)
        member_file = archive.extractfile(members[path_value])
        if member_file is None:
            raise BackupToolError("Archive member is unreadable", EXIT_RESTORE)
        descriptor = os.open(
            destination,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        digest = hashlib.sha256()
        size = 0
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as output:
                while True:
                    chunk = member_file.read(_COPY_CHUNK_SIZE)
                    if not chunk:
                        break
                    output.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                output.flush()
                os.fsync(output.fileno())
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
        if size != metadata["size"] or digest.hexdigest() != checksums[path_value]:
            destination.unlink(missing_ok=True)
            raise BackupToolError("Restored file checksum does not match", EXIT_RESTORE)

        declared_mode = int(metadata["mode"], 8)
        os.chmod(destination, declared_mode & 0o600)
        timestamp_ns = _parse_utc_timestamp(metadata["mtime_utc"])
        os.utime(
            destination,
            ns=(timestamp_ns, timestamp_ns),
            follow_symlinks=False,
        )

    for directory in sorted(
        (path for path in publish_root.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        os.chmod(directory, 0o700)
    os.chmod(publish_root, 0o700)


def restore_backup(
    options: RestoreOptions,
    *,
    environment: Mapping[str, str] | None = None,
    repository_root: Path | None = None,
    _test_gpg_context: _GPGTestContext | None = None,
) -> RestoreResult:
    """Verify, decrypt, and safely publish one restored tree."""

    env = os.environ if environment is None else environment
    repo = repository_root or _find_repository_root()
    destination = _validate_destination(
        options.destination,
        repository_root=repo,
        environment=env,
    )
    archive_path = options.archive.expanduser().resolve(strict=False)
    sidecar_path = Path(f"{archive_path}.sha256")
    expected_hash = _read_outer_sidecar(archive_path, sidecar_path)
    archive_file = _open_and_verify_archive(archive_path, expected_hash)

    previous_umask = os.umask(0o077)
    publish_directory: Path | None = None
    try:
        with archive_file:
            with tempfile.TemporaryDirectory(
                prefix=".mowftee-restore-work-", dir=destination.parent
            ) as temporary:
                work_root = Path(temporary)
                os.chmod(work_root, 0o700)
                plaintext = work_root / "mowftee-backup.tar.gz"
                with _secure_create(plaintext) as plaintext_file:
                    _run_gpg_decrypt(
                        archive_file,
                        plaintext_file,
                        test_context=_test_gpg_context,
                    )
                    plaintext_file.flush()
                    os.fsync(plaintext_file.fileno())

                archive, validated, checksums, members = _preflight_archive(plaintext)
                try:
                    publish_directory = Path(
                        tempfile.mkdtemp(
                            prefix=f".{destination.name}.partial-",
                            dir=destination.parent,
                        )
                    )
                    os.chmod(publish_directory, 0o700)
                    _extract_validated_archive(
                        archive,
                        validated,
                        checksums,
                        members,
                        publish_directory,
                    )
                finally:
                    archive.close()

            if destination.exists() or destination.is_symlink():
                raise BackupToolError("Restore destination appeared during restore", EXIT_RESTORE)
            if publish_directory is None:
                raise BackupToolError("Restore staging was not created", EXIT_RESTORE)
            os.rename(publish_directory, destination)
            publish_directory = None
            _fsync_directory(destination.parent)
            return RestoreResult(destination=destination)
    except BackupToolError:
        raise
    except OSError:
        raise BackupToolError("Could not safely publish restored data", EXIT_RESTORE) from None
    finally:
        if publish_directory is not None:
            shutil.rmtree(publish_directory, ignore_errors=True)
        os.umask(previous_umask)


def _find_repository_root() -> Path:
    candidates = [Path(__file__).resolve(), Path.cwd().resolve()]
    for candidate in candidates:
        for parent in (candidate, *candidate.parents):
            if (parent / "pyproject.toml").is_file() and (parent / "uv.lock").is_file():
                return parent
    raise BackupToolError("Could not locate the Mowftee repository", EXIT_PREREQUISITE)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m mowftee.backup",
        description="Create and safely restore encrypted Mowftee backups.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup_parser = subparsers.add_parser("backup", help="create an encrypted backup")
    backup_parser.add_argument("--target", type=Path, required=True)
    backup_parser.add_argument("--include-conversations", action="store_true")
    backup_parser.add_argument("--include-audit", action="store_true")
    backup_parser.add_argument("--include-benchmarks", action="store_true")

    restore_parser = subparsers.add_parser("restore", help="restore an encrypted backup")
    restore_parser.add_argument("--archive", type=Path, required=True)
    restore_parser.add_argument("--destination", type=Path, required=True)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    _gpg_test_context: _GPGTestContext | None = None,
    _environment: Mapping[str, str] | None = None,
    _repository_root: Path | None = None,
) -> int:
    """CLI entry point with stable exit codes."""

    parser = _parser()
    args = parser.parse_args(argv)
    if os.geteuid() == 0:
        print("Mowftee backup tooling must not run as root.", file=sys.stderr)
        return EXIT_PREREQUISITE
    try:
        if args.command == "backup":
            result = create_backup(
                BackupOptions(
                    target=args.target,
                    include_conversations=args.include_conversations,
                    include_audit=args.include_audit,
                    include_benchmarks=args.include_benchmarks,
                ),
                environment=_environment,
                repository_root=_repository_root,
                _test_gpg_context=_gpg_test_context,
            )
            print(result.archive)
            return 0
        if args.command == "restore":
            result = restore_backup(
                RestoreOptions(archive=args.archive, destination=args.destination),
                environment=_environment,
                repository_root=_repository_root,
                _test_gpg_context=_gpg_test_context,
            )
            print(result.destination)
            return 0
        parser.error("unknown command")
    except BackupToolError as error:
        print(f"Mowftee backup: {error}", file=sys.stderr)
        return error.exit_code
    return EXIT_CLI


if __name__ == "__main__":
    raise SystemExit(main())
