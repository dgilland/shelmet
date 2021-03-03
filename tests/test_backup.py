from datetime import datetime, timezone
import filecmp
import logging.handlers
from pathlib import Path
import re
import typing as t

import pytest
from pytest import param

import shelmet as sh

from .utils import FakeDir, FakeFile


parametrize = pytest.mark.parametrize


T_WRITE_FILE = t.Callable[[t.Union[str, Path], str], Path]
DEFAULT_TS_PATTERN = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+"
DEFAULT_TS_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"


def is_same_file(file1: Path, file2: Path) -> bool:
    return filecmp.cmp(file1, file2)


def is_same_dir(dir1: Path, dir2: Path) -> bool:
    return _is_same_dir(filecmp.dircmp(dir1, dir2))


def _is_same_dir(dcmp: filecmp.dircmp) -> bool:
    if dcmp.diff_files or dcmp.left_only or dcmp.right_only:
        return False

    for sub_dcmp in dcmp.subdirs.values():
        if not _is_same_dir(sub_dcmp):
            return False

    return True


@pytest.fixture()
def write_file(tmp_path: Path) -> T_WRITE_FILE:
    def _write_file(path, contents):
        file = tmp_path / path
        file.write_text(contents)
        return file

    return _write_file


@pytest.fixture()
def src_file(tmp_path: Path) -> Path:
    src_file = tmp_path / "src_file.txt"
    src_file.write_text("test")
    return src_file


def test_backup__backs_up_file(src_file: Path):
    backup_file = sh.backup(src_file)
    assert backup_file != src_file
    assert backup_file.parent == src_file.parent
    assert is_same_file(src_file, backup_file)


def test_backup__backs_up_directory(tmp_path: Path):
    src_dir = FakeDir(
        tmp_path / "src",
        files=[
            FakeFile("1.txt", text="1"),
            FakeFile("2.txt", text="2"),
            FakeFile("a/a1.txt", text="a1"),
            FakeFile("a/a2.txt", text="a2"),
        ],
    )
    src_dir.mkdir()

    backup_dir = sh.backup(src_dir.path)
    assert is_same_dir(src_dir.path, backup_dir)


def test_backup__customizes_backup_parent_directory(tmp_path: Path, src_file: Path):
    dir = tmp_path / "a" / "b" / "c"
    dir.mkdir(parents=True)
    backup_file = sh.backup(src_file, dir=dir)

    assert backup_file.parent == dir
    assert is_same_file(src_file, backup_file)


def test_backup__can_overwrite_destination(src_file: Path):
    dst = src_file.parent / f"{src_file.name}~"
    dst.touch()

    backup_file = sh.backup(src_file, suffix="~", timestamp=None, overwrite=True)
    assert backup_file == dst
    assert is_same_file(src_file, backup_file)


@pytest.mark.freeze_time
def test_backup__appends_local_timestamp_using_strftime(src_file: Path):
    now = datetime.now()
    expected_name = f"{src_file.name}.{now.strftime(DEFAULT_TS_FORMAT)}~"

    backup_file = sh.backup(src_file)
    assert backup_file.name == expected_name


@pytest.mark.freeze_time
def test_backup__appends_utc_timestamp_using_strftime(freezer, src_file: Path):
    utcnow = datetime.now(timezone.utc)
    expected_name = f"{src_file.name}.{utcnow.strftime(DEFAULT_TS_FORMAT)}~"

    backup_file = sh.backup(src_file, utc=True)
    assert backup_file.name == expected_name


@parametrize(
    "filename, args, pattern",
    [
        param("test.txt", {}, re.compile(rf"test\.txt\.{DEFAULT_TS_PATTERN}~")),
        param("test.txt", {"timestamp": "%Y-%d-%m"}, re.compile(r"test\.txt\.\d{4}-\d{2}-\d{2}~")),
        param("test.txt", {"epoch": True}, re.compile(r"test\.txt\.\d+\.\d+~")),
        param("test.txt", {"timestamp": None}, re.compile(r"test\.txt~")),
        param(
            "test.txt", {"prefix": "bak."}, re.compile(rf"bak\.test\.txt\.{DEFAULT_TS_PATTERN}~")
        ),
        param("test.txt", {"suffix": ".bak"}, re.compile(rf"test\.txt\.{DEFAULT_TS_PATTERN}.bak")),
        param("test.txt", {"suffix": ""}, re.compile(rf"test\.txt\.{DEFAULT_TS_PATTERN}")),
        param("test.txt", {"hidden": True}, re.compile(rf"\.test\.txt\.{DEFAULT_TS_PATTERN}~")),
        param(
            "test.txt",
            {"hidden": True, "prefix": "."},
            re.compile(rf"\.test\.txt\.{DEFAULT_TS_PATTERN}~"),
        ),
        param(
            "test.txt",
            {"hidden": True, "prefix": "BACKUP_", "suffix": ".BAK"},
            re.compile(rf"\.BACKUP_test\.txt\.{DEFAULT_TS_PATTERN}\.BAK"),
        ),
        param(
            "test.txt",
            {"namer": lambda src: src.parent / f"{src.name}.bak"},
            re.compile(r"test\.txt\.bak"),
        ),
    ],
)
def test_backup__customizes_filename(
    write_file: T_WRITE_FILE, filename: str, args: t.Dict[str, t.Any], pattern: t.Pattern
):
    src_file = write_file(filename, "test")
    backup_file = sh.backup(src_file, **args)

    assert pattern.fullmatch(backup_file.name), (
        f"Backup of {src_file.name!r} with name {backup_file.name!r}"
        f" did not match pattern {pattern!r}"
    )


@parametrize(
    "timestamp",
    [
        param(True),
        param(False),
        param(b""),
        param(10),
        param({}),
        param([]),
    ],
)
def test_backup__raises_when_timestamp_is_invalid(src_file: Path, timestamp: t.Any):
    with pytest.raises(ValueError):
        sh.backup(src_file, timestamp=timestamp)


def test_backup__raises_when_destination_is_same_as_source(src_file):
    with pytest.raises(FileExistsError):
        sh.backup(src_file, prefix="", suffix="", timestamp=None)


def test_backup__raises_when_destination_exists(src_file):
    dst = src_file.parent / f"{src_file.name}~"
    dst.touch()
    with pytest.raises(FileExistsError):
        sh.backup(src_file, suffix="~", timestamp=None)
