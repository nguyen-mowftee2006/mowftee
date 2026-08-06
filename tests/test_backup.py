from __future__ import annotations

import getpass
import hashlib
import io
import json
import os
import secrets
import shutil
import socket
import sqlite3
import stat
import subprocess
import tarfile
import tempfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import pytest

from mowftee import backup

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class IsolatedLayout:
    root: Path
    environment: dict[str, str]
    target: Path

    @property
    def config_root(self) -> Path:
        return Path(self.environment["XDG_CONFIG_HOME"]) / "mowftee"

    @property
    def data_root(self) -> Path:
        return Path(self.environment["XDG_DATA_HOME"]) / "mowftee"

    @property
    def state_root(self) -> Path:
        return Path(self.environment["XDG_STATE_HOME"]) / "mowftee"

    @property
    def cache_root(self) -> Path:
        return Path(self.environment["XDG_CACHE_HOME"]) / "mowftee"


@pytest.fixture
def layout(tmp_path: Path) -> IsolatedLayout:
    environment = {
        "HOME": str(tmp_path / "home"),
        "XDG_CONFIG_HOME": str(tmp_path / "xdg-config"),
        "XDG_DATA_HOME": str(tmp_path / "xdg-data"),
        "XDG_STATE_HOME": str(tmp_path / "xdg-state"),
        "XDG_CACHE_HOME": str(tmp_path / "xdg-cache"),
    }
    target = tmp_path / "local-staging"
    target.mkdir(mode=0o700)
    return IsolatedLayout(tmp_path, environment, target)


@pytest.fixture(scope="module")
def gpg_context(tmp_path_factory: pytest.TempPathFactory) -> Iterator[backup._GPGTestContext]:
    del tmp_path_factory
    root = Path(tempfile.mkdtemp(prefix="mowftee-gpg-", dir="/tmp"))
    home = root / "home"
    home.mkdir(mode=0o700)
    passphrase_file = root / "passphrase"
    passphrase_file.write_text(secrets.token_urlsafe(32), encoding="utf-8")
    passphrase_file.chmod(0o600)
    context = backup._GPGTestContext(home, passphrase_file)
    yield context
    subprocess.run(
        ["gpgconf", "--homedir", str(home), "--kill", "gpg-agent"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    passphrase_file.unlink(missing_ok=True)
    shutil.rmtree(root, ignore_errors=True)


def write_file(path: Path, content: bytes = b"fixture-data") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(content)
    path.chmod(0o600)
    return path


def add_required_config(layout: IsolatedLayout, content: bytes = b"app:\n  name: test\n") -> Path:
    return write_file(layout.config_root / "config.yaml", content)


def backup_options(layout: IsolatedLayout, **overrides: bool) -> backup.BackupOptions:
    return backup.BackupOptions(target=layout.target, **overrides)


def create_archive(
    layout: IsolatedLayout,
    context: backup._GPGTestContext,
    *,
    options: backup.BackupOptions | None = None,
    after_copy_hook: Callable[[PurePosixPath], None] | None = None,
) -> backup.BackupResult:
    return backup.create_backup(
        options or backup_options(layout),
        environment=layout.environment,
        repository_root=REPOSITORY_ROOT,
        _test_gpg_context=context,
        _after_copy_hook=after_copy_hook,
    )


def decrypt_archive(
    result: backup.BackupResult,
    destination: Path,
    context: backup._GPGTestContext,
) -> Path:
    plaintext = destination / "archive.tar.gz"
    destination.mkdir(parents=True, exist_ok=True)
    with result.archive.open("rb") as encrypted, backup._secure_create(plaintext) as output:
        backup._run_gpg_decrypt(encrypted, output, test_context=context)
    return plaintext


def read_archive(
    result: backup.BackupResult,
    destination: Path,
    context: backup._GPGTestContext,
) -> tuple[dict[str, bytes], list[tarfile.TarInfo]]:
    plaintext = decrypt_archive(result, destination, context)
    content: dict[str, bytes] = {}
    with tarfile.open(plaintext, "r:gz") as archive:
        members = archive.getmembers()
        for member in members:
            extracted = archive.extractfile(member)
            assert extracted is not None
            content[member.name] = extracted.read()
    return content, members


def parsed_manifest(content: dict[str, bytes]) -> dict[str, object]:
    return json.loads(content[backup.MANIFEST_PATH.as_posix()])


def restore_archive(
    layout: IsolatedLayout,
    result: backup.BackupResult,
    context: backup._GPGTestContext,
    *,
    destination: Path | None = None,
) -> backup.RestoreResult:
    return backup.restore_backup(
        backup.RestoreOptions(
            archive=result.archive,
            destination=destination or layout.root / "restored",
        ),
        environment=layout.environment,
        repository_root=REPOSITORY_ROOT,
        _test_gpg_context=context,
    )


def update_outer_sidecar(result: backup.BackupResult) -> None:
    digest = hashlib.sha256(result.archive.read_bytes()).hexdigest()
    result.sidecar.write_text(f"{digest}  {result.archive.name}\n", encoding="ascii")
    result.sidecar.chmod(0o600)


def rewrite_plain_archive(
    plaintext: Path,
    transform: Callable[
        [list[tuple[tarfile.TarInfo, bytes]]], list[tuple[tarfile.TarInfo, bytes]]
    ],
) -> None:
    with tarfile.open(plaintext, "r:gz") as archive:
        records = []
        for member in archive.getmembers():
            extracted = archive.extractfile(member)
            records.append((member, b"" if extracted is None else extracted.read()))
    transformed = transform(records)
    replacement = plaintext.with_suffix(".replacement")
    with tarfile.open(replacement, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        for member, data in transformed:
            archive.addfile(member, io.BytesIO(data) if member.isreg() else None)
    replacement.replace(plaintext)


def reencrypt_plain_archive(
    result: backup.BackupResult,
    plaintext: Path,
    context: backup._GPGTestContext,
) -> None:
    result.archive.unlink()
    with backup._secure_create(result.archive) as encrypted:
        backup._run_gpg_encrypt(plaintext, encrypted, test_context=context)
    update_outer_sidecar(result)


def add_tar_member(
    records: list[tuple[tarfile.TarInfo, bytes]],
    name: str,
    member_type: bytes = tarfile.REGTYPE,
    data: bytes = b"rogue",
    linkname: str = "",
) -> list[tuple[tarfile.TarInfo, bytes]]:
    member = tarfile.TarInfo(name)
    member.type = member_type
    member.linkname = linkname
    member.mode = 0o600
    member.uid = 0
    member.gid = 0
    member.size = len(data) if member_type == tarfile.REGTYPE else 0
    return [*records, (member, data)]


def call_restore(
    layout: IsolatedLayout,
    result: backup.BackupResult,
    context: backup._GPGTestContext,
    destination: Path,
) -> int:
    return backup.main(
        ["restore", "--archive", str(result.archive), "--destination", str(destination)],
        _gpg_test_context=context,
        _environment=layout.environment,
        _repository_root=REPOSITORY_ROOT,
    )


def test_backup_includes_sample_config(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    source = add_required_config(layout, b"private-config-marker")

    result = create_archive(layout, gpg_context)
    content, _ = read_archive(result, layout.root / "inspect", gpg_context)

    assert content["mowftee-backup/config/mowftee/config.yaml"] == source.read_bytes()


def test_backup_includes_persona_tree(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    add_required_config(layout)
    write_file(layout.config_root / "persona/base.md", b"persona-base")
    write_file(layout.config_root / "persona/nested/style.md", b"persona-style")

    content, _ = read_archive(
        create_archive(layout, gpg_context), layout.root / "inspect", gpg_context
    )

    assert content["mowftee-backup/config/mowftee/persona/base.md"] == b"persona-base"
    assert content["mowftee-backup/config/mowftee/persona/nested/style.md"] == b"persona-style"


def test_backup_includes_voice_lora_and_rag(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    add_required_config(layout)
    expected = {
        "mowftee-backup/data/mowftee/artifacts/voices/voice.bin": b"voice-marker",
        "mowftee-backup/data/mowftee/artifacts/lora/adapter.bin": b"lora-marker",
        "mowftee-backup/data/mowftee/rag/private.txt": b"rag-marker",
    }
    write_file(layout.data_root / "artifacts/voices/voice.bin", b"voice-marker")
    write_file(layout.data_root / "artifacts/lora/adapter.bin", b"lora-marker")
    write_file(layout.data_root / "rag/private.txt", b"rag-marker")

    content, _ = read_archive(
        create_archive(layout, gpg_context), layout.root / "inspect", gpg_context
    )

    for path, marker in expected.items():
        assert content[path] == marker


def create_sqlite(path: Path, *, wal: bool = False) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    if wal:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        connection.execute("PRAGMA wal_autocheckpoint=0")
    connection.execute("CREATE TABLE memory (value TEXT NOT NULL)")
    connection.execute("INSERT INTO memory VALUES ('remember-me')")
    connection.commit()
    return connection


def restored_sqlite_path(destination: Path) -> Path:
    return destination / "mowftee-backup/data/mowftee/memory/mowftee.sqlite3"


def test_open_sqlite_database_is_snapshotted(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    database = layout.data_root / "memory/mowftee.sqlite3"
    connection = create_sqlite(database)
    try:
        result = create_archive(layout, gpg_context)
        destination = layout.root / "restored"
        restore_archive(layout, result, gpg_context, destination=destination)
        assert connection.execute("SELECT value FROM memory").fetchall() == [("remember-me",)]
    finally:
        connection.close()

    with sqlite3.connect(restored_sqlite_path(destination)) as restored:
        assert restored.execute("SELECT value FROM memory").fetchall() == [("remember-me",)]
        assert restored.execute("PRAGMA quick_check").fetchall() == [("ok",)]


def test_wal_database_uses_online_backup(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    database = layout.data_root / "memory/mowftee.sqlite3"
    connection = create_sqlite(database, wal=True)
    try:
        assert Path(f"{database}-wal").exists()
        result = create_archive(layout, gpg_context)
        content, _ = read_archive(result, layout.root / "inspect", gpg_context)
        assert not any(path.endswith(("-wal", "-shm")) for path in content)
        destination = layout.root / "restored"
        restore_archive(layout, result, gpg_context, destination=destination)
    finally:
        connection.close()

    restored_path = restored_sqlite_path(destination)
    assert stat.S_IMODE(restored_path.stat().st_mode) == 0o600
    with sqlite3.connect(restored_path) as restored:
        assert restored.execute("SELECT value FROM memory").fetchall() == [("remember-me",)]


def test_restore_succeeds_and_content_matches(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    source = add_required_config(layout, b"round-trip-marker")
    result = create_archive(layout, gpg_context)
    destination = layout.root / "restored"

    restored = restore_archive(layout, result, gpg_context, destination=destination)

    assert restored.destination == destination
    assert destination.is_dir()
    assert (
        destination / "mowftee-backup/config/mowftee/config.yaml"
    ).read_bytes() == source.read_bytes()


def test_manifest_schema_and_local_staging_status(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    add_required_config(layout)
    content, _ = read_archive(
        create_archive(layout, gpg_context), layout.root / "inspect", gpg_context
    )
    manifest = parsed_manifest(content)

    assert set(manifest) == {
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
    assert manifest["backup_schema_version"] == 1
    assert str(manifest["created_at_utc"]).endswith("Z")
    assert manifest["storage_status"] == "local_staging"
    assert manifest["archive_format"] == "pax-tar"
    assert manifest["compression"] == "gzip"
    assert manifest["encryption"] == "gpg-symmetric-aes256"
    file_metadata = manifest["files"][0]  # type: ignore[index]
    assert set(file_metadata) == {
        "archive_path",
        "type",
        "mode",
        "size",
        "mtime_utc",
        "sha256",
    }


def test_internal_checksums_cover_manifest_and_payload(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    add_required_config(layout)
    write_file(layout.config_root / "persona/p.md", b"persona")
    content, _ = read_archive(
        create_archive(layout, gpg_context), layout.root / "inspect", gpg_context
    )
    checksums = backup._parse_internal_checksums(content[backup.CHECKSUMS_PATH.as_posix()])
    manifest = parsed_manifest(content)
    payload_paths = {entry["archive_path"] for entry in manifest["files"]}  # type: ignore[index]

    assert set(checksums) == {backup.MANIFEST_PATH.as_posix(), *payload_paths}
    assert backup.CHECKSUMS_PATH.as_posix() not in checksums
    for path, expected in checksums.items():
        assert hashlib.sha256(content[path]).hexdigest() == expected


def test_outer_sidecar_matches_ciphertext_and_modes_are_secure(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    add_required_config(layout)
    result = create_archive(layout, gpg_context)

    expected = hashlib.sha256(result.archive.read_bytes()).hexdigest()
    assert result.sidecar.read_text(encoding="ascii") == (
        f"{expected}  {result.archive.name}\n"
    )
    assert stat.S_IMODE(result.archive.stat().st_mode) == 0o600
    assert stat.S_IMODE(result.sidecar.stat().st_mode) == 0o600


def test_all_tar_names_are_relative_and_confined(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    add_required_config(layout)
    _, members = read_archive(
        create_archive(layout, gpg_context), layout.root / "inspect", gpg_context
    )

    for member in members:
        path = PurePosixPath(member.name)
        assert not path.is_absolute()
        assert path.parts[0] == "mowftee-backup"
        assert not {"", ".", ".."}.intersection(path.parts)
        assert member.isreg()


def test_metadata_omits_host_identity_and_absolute_sources(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    add_required_config(layout, b"controlled-content")
    content, _ = read_archive(
        create_archive(layout, gpg_context), layout.root / "inspect", gpg_context
    )
    serialized = content[backup.MANIFEST_PATH.as_posix()].decode("utf-8")

    assert getpass.getuser() not in serialized
    assert socket.gethostname() not in serialized
    assert str(layout.root) not in serialized
    assert layout.environment["HOME"] not in serialized
    assert '"uid"' not in serialized
    assert '"gid"' not in serialized


def test_missing_required_sources_are_recorded_without_paths(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    add_required_config(layout)
    content, _ = read_archive(
        create_archive(layout, gpg_context), layout.root / "inspect", gpg_context
    )
    manifest = parsed_manifest(content)

    assert set(manifest["missing_sources"]) == {
        "custom_persona",
        "memory_sqlite",
        "custom_voices",
        "custom_lora",
        "private_rag",
    }
    assert str(layout.root) not in json.dumps(manifest)


def test_models_cache_and_runtime_logs_are_excluded(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    add_required_config(layout)
    write_file(layout.cache_root / "cache-marker", b"cache-private-marker")
    write_file(layout.state_root / "logs/app.jsonl", b"runtime-log-marker")
    content, _ = read_archive(
        create_archive(layout, gpg_context), layout.root / "inspect", gpg_context
    )
    all_content = b"\n".join(content.values())
    manifest = parsed_manifest(content)

    assert b"cache-private-marker" not in all_content
    assert b"runtime-log-marker" not in all_content
    assert not any("ollama" in path for path in content)
    assert {
        "public_ollama_models",
        "xdg_cache",
        "runtime_logs",
    }.issubset(set(manifest["excluded_categories"]))


@pytest.mark.parametrize(
    ("option_name", "source_path", "archive_path"),
    [
        (
            "include_conversations",
            "data:conversations/chat.txt",
            "mowftee-backup/optional/conversations/chat.txt",
        ),
        (
            "include_audit",
            "state:audit/audit.jsonl",
            "mowftee-backup/optional/audit/audit.jsonl",
        ),
        (
            "include_benchmarks",
            "state:benchmarks/result.txt",
            "mowftee-backup/optional/benchmarks/result.txt",
        ),
    ],
)
def test_optional_sources_require_corresponding_flag(
    layout: IsolatedLayout,
    gpg_context: backup._GPGTestContext,
    option_name: str,
    source_path: str,
    archive_path: str,
) -> None:
    add_required_config(layout)
    root_name, relative = source_path.split(":", 1)
    root = layout.data_root if root_name == "data" else layout.state_root
    write_file(root / relative, b"optional-marker")

    default_content, _ = read_archive(
        create_archive(layout, gpg_context), layout.root / "default-inspect", gpg_context
    )
    assert archive_path not in default_content

    enabled_content, _ = read_archive(
        create_archive(
            layout,
            gpg_context,
            options=backup_options(layout, **{option_name: True}),
        ),
        layout.root / "enabled-inspect",
        gpg_context,
    )
    assert enabled_content[archive_path] == b"optional-marker"


def test_corrupted_ciphertext_with_recomputed_outer_hash_is_rejected(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    add_required_config(layout)
    result = create_archive(layout, gpg_context)
    ciphertext = bytearray(result.archive.read_bytes())
    ciphertext[len(ciphertext) // 2] ^= 0xFF
    result.archive.write_bytes(ciphertext)
    update_outer_sidecar(result)

    assert call_restore(layout, result, gpg_context, layout.root / "restored") == 5
    assert not (layout.root / "restored").exists()


def test_wrong_outer_checksum_is_rejected_before_restore(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    add_required_config(layout)
    result = create_archive(layout, gpg_context)
    result.sidecar.write_text(f"{'0' * 64}  {result.archive.name}\n", encoding="ascii")

    assert call_restore(layout, result, gpg_context, layout.root / "restored") == 6
    assert not (layout.root / "restored").exists()


def test_missing_sidecar_is_rejected(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    add_required_config(layout)
    result = create_archive(layout, gpg_context)
    result.sidecar.unlink()

    assert call_restore(layout, result, gpg_context, layout.root / "restored") == 6


@pytest.mark.parametrize(
    ("member_type", "linkname"),
    [
        (tarfile.SYMTYPE, "../../escape"),
        (tarfile.LNKTYPE, "mowftee-backup/config/mowftee/config.yaml"),
        (tarfile.FIFOTYPE, ""),
        (tarfile.CHRTYPE, ""),
        (tarfile.BLKTYPE, ""),
    ],
)
def test_unsafe_tar_member_types_are_rejected(
    layout: IsolatedLayout,
    gpg_context: backup._GPGTestContext,
    member_type: bytes,
    linkname: str,
) -> None:
    add_required_config(layout)
    result = create_archive(layout, gpg_context)
    plaintext = decrypt_archive(result, layout.root / "rewrite", gpg_context)
    rewrite_plain_archive(
        plaintext,
        lambda records: add_tar_member(
            records,
            "mowftee-backup/unsafe-member",
            member_type,
            linkname=linkname,
        ),
    )
    reencrypt_plain_archive(result, plaintext, gpg_context)

    assert call_restore(layout, result, gpg_context, layout.root / "restored") == 6
    assert not (layout.root / "escape").exists()


def test_tar_path_traversal_is_rejected(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    add_required_config(layout)
    result = create_archive(layout, gpg_context)
    plaintext = decrypt_archive(result, layout.root / "rewrite", gpg_context)
    rewrite_plain_archive(
        plaintext,
        lambda records: add_tar_member(records, "mowftee-backup/../../escape"),
    )
    reencrypt_plain_archive(result, plaintext, gpg_context)

    assert call_restore(layout, result, gpg_context, layout.root / "restored") == 6
    assert not (layout.root / "escape").exists()


def test_member_absent_from_manifest_is_rejected(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    add_required_config(layout)
    result = create_archive(layout, gpg_context)
    plaintext = decrypt_archive(result, layout.root / "rewrite", gpg_context)
    rewrite_plain_archive(
        plaintext,
        lambda records: add_tar_member(records, "mowftee-backup/rogue.txt"),
    )
    reencrypt_plain_archive(result, plaintext, gpg_context)

    assert call_restore(layout, result, gpg_context, layout.root / "restored") == 6


@pytest.mark.parametrize("nested", [False, True])
def test_source_symlink_is_rejected(
    layout: IsolatedLayout,
    gpg_context: backup._GPGTestContext,
    nested: bool,
) -> None:
    real_file = write_file(layout.root / "outside.txt", b"outside")
    if nested:
        add_required_config(layout)
        link = layout.config_root / "persona/link"
        link.parent.mkdir(parents=True)
    else:
        link = layout.config_root / "config.yaml"
        link.parent.mkdir(parents=True)
    link.symlink_to(real_file)

    with pytest.raises(backup.BackupToolError) as raised:
        create_archive(layout, gpg_context)
    assert raised.value.exit_code == 4
    assert not list(layout.target.glob("mowftee-backup-*"))


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO is unavailable")
def test_special_source_is_rejected(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    add_required_config(layout)
    fifo = layout.config_root / "persona/fifo"
    fifo.parent.mkdir(parents=True)
    os.mkfifo(fifo)

    with pytest.raises(backup.BackupToolError) as raised:
        create_archive(layout, gpg_context)
    assert raised.value.exit_code == 4


def test_hardlinks_are_materialized_as_regular_files(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    add_required_config(layout)
    first = write_file(layout.config_root / "persona/first.txt", b"shared-inode")
    second = first.with_name("second.txt")
    os.link(first, second)

    _, members = read_archive(
        create_archive(layout, gpg_context), layout.root / "inspect", gpg_context
    )
    matching = [member for member in members if member.name.endswith(("first.txt", "second.txt"))]
    assert len(matching) == 2
    assert all(member.isreg() for member in matching)


def test_source_change_during_copy_aborts_and_cleans_artifacts(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    source = add_required_config(layout, b"before")
    changed = False

    def mutate_source(path: PurePosixPath) -> None:
        nonlocal changed
        if not changed and path.name == "config.yaml":
            changed = True
            source.write_bytes(b"after-change")

    with pytest.raises(backup.BackupToolError) as raised:
        create_archive(layout, gpg_context, after_copy_hook=mutate_source)
    assert raised.value.exit_code == 4
    assert not list(layout.target.glob("*.partial"))
    assert not list(layout.target.glob("mowftee-backup-*"))


def test_target_inside_repository_is_rejected(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    add_required_config(layout)

    with pytest.raises(backup.BackupToolError) as raised:
        create_archive(
            layout,
            gpg_context,
            options=backup.BackupOptions(REPOSITORY_ROOT / "scripts"),
        )
    assert raised.value.exit_code == 3


def test_target_inside_xdg_source_is_rejected(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    add_required_config(layout)
    target = layout.data_root / "staging"
    target.mkdir(parents=True)

    with pytest.raises(backup.BackupToolError) as raised:
        create_archive(
            layout,
            gpg_context,
            options=backup.BackupOptions(target),
        )
    assert raised.value.exit_code == 3
    assert not any(target.iterdir())


def test_existing_destination_is_rejected_without_modification(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    add_required_config(layout)
    result = create_archive(layout, gpg_context)
    destination = layout.root / "restored"
    sentinel = write_file(destination / "sentinel", b"keep-me")

    assert call_restore(layout, result, gpg_context, destination) == 6
    assert sentinel.read_bytes() == b"keep-me"


def test_failed_encryption_removes_partial_artifacts(
    layout: IsolatedLayout,
    gpg_context: backup._GPGTestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    add_required_config(layout)

    def fail_encryption(
        plaintext: Path,
        encrypted_output: io.BufferedRandom,
        *,
        test_context: backup._GPGTestContext | None,
    ) -> None:
        del plaintext, test_context
        encrypted_output.write(b"partial-ciphertext")
        raise backup.BackupToolError("simulated encryption failure", 5)

    monkeypatch.setattr(backup, "_run_gpg_encrypt", fail_encryption)
    with pytest.raises(backup.BackupToolError) as raised:
        create_archive(layout, gpg_context)
    assert raised.value.exit_code == 5
    assert not list(layout.target.glob("*.partial"))
    assert not list(layout.target.glob("*.gpg"))
    assert not list(layout.target.glob("*.sha256"))


def test_launchers_resolve_repository_outside_current_directory(tmp_path: Path) -> None:
    environment = dict(os.environ)
    environment["UV_CACHE_DIR"] = str(tmp_path / "uv-cache")
    for launcher in ("backup.sh", "restore.sh"):
        result = subprocess.run(
            [str(REPOSITORY_ROOT / "scripts" / launcher), "--help"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env=environment,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "usage:" in result.stdout


def test_target_contains_only_ciphertext_and_sidecar(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    add_required_config(layout, b"plaintext-private-marker")
    result = create_archive(layout, gpg_context)

    assert set(layout.target.iterdir()) == {result.archive, result.sidecar}
    assert not result.archive.read_bytes().startswith(b"\x1f\x8b")
    assert b"plaintext-private-marker" not in result.archive.read_bytes()
    with pytest.raises(tarfile.TarError), tarfile.open(result.archive):
        pass


def test_backup_does_not_modify_sources(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    source = add_required_config(layout, b"immutable-source")
    before = source.stat()
    before_bytes = source.read_bytes()

    create_archive(layout, gpg_context)

    after = source.stat()
    assert source.read_bytes() == before_bytes
    assert (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) == (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    )


def test_no_required_data_refuses_empty_archive(
    layout: IsolatedLayout, gpg_context: backup._GPGTestContext
) -> None:
    (layout.data_root / "artifacts/voices").mkdir(parents=True)
    write_file(layout.data_root / "conversations/chat.txt", b"optional-only")

    with pytest.raises(backup.BackupToolError) as raised:
        create_archive(
            layout,
            gpg_context,
            options=backup_options(layout, include_conversations=True),
        )
    assert raised.value.exit_code == 4
    assert not list(layout.target.iterdir())


def test_local_staging_warning_is_unconditional(
    layout: IsolatedLayout,
    gpg_context: backup._GPGTestContext,
    capsys: pytest.CaptureFixture[str],
) -> None:
    add_required_config(layout)

    create_archive(layout, gpg_context)

    assert backup.LOCAL_STAGING_WARNING in capsys.readouterr().err
    parser_help = backup._parser().format_help()
    assert "suppress" not in parser_help


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (["backup"], 2),
        (["backup", "--target", "/definitely/missing/mowftee-target"], 3),
    ],
)
def test_cli_exit_codes_for_cli_and_policy_errors(
    arguments: list[str], expected: int
) -> None:
    if expected == 2:
        with pytest.raises(SystemExit) as raised:
            backup.main(arguments)
        assert raised.value.code == 2
    else:
        assert backup.main(arguments, _repository_root=REPOSITORY_ROOT) == expected


@pytest.mark.parametrize("forbidden_option", ["--passphrase", "--recipient", "--force"])
def test_production_cli_rejects_secret_and_force_options(forbidden_option: str) -> None:
    with pytest.raises(SystemExit) as raised:
        backup.main(["backup", "--target", "/tmp", forbidden_option, "value"])
    assert raised.value.code == 2
