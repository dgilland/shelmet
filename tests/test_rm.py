from pathlib import Path
import typing as t

import pytest
from pytest import param

import shelmet as sh

from .utils import FakeDir, FakeFile


parametrize = pytest.mark.parametrize


@parametrize(
    "sources",
    [
        param([FakeFile("1.txt")], id="one_file"),
        param([FakeFile("1.txt"), FakeFile("2.txt"), FakeFile("3.txt")], id="many_files"),
        param([FakeDir("1")], id="one_dir_with_no_files"),
        param(
            [FakeDir("1", files=[FakeFile("1.txt"), FakeFile("2.txt")])], id="one_dir_with_files"
        ),
        param(
            [FakeDir("1"), FakeDir("2"), FakeDir("3/4"), FakeDir("5/6/7")],
            id="many_dirs_with_no_files",
        ),
        param(
            [
                FakeDir("1", files=[FakeFile("1.txt")]),
                FakeDir("2", files=[FakeFile("2.txt")], dirs=[FakeDir("2.1")]),
                FakeDir("3/4", files=[FakeFile("3.txt"), FakeFile("4.txt")]),
                FakeDir("5/6/7"),
            ],
            id="many_dirs_with_files",
        ),
    ],
)
def test_rm(tmp_path: Path, sources: t.Sequence[FakeFile]):
    base_dir = FakeDir(tmp_path)
    srcs = [base_dir.add(source) for source in sources]

    for src in srcs:
        assert src.path.exists()

    sh.rm(*(src.path for src in srcs))

    for src in srcs:
        assert not src.path.exists()


@parametrize(
    "sources",
    [
        param([FakeDir("1")], id="one_dir_with_no_files"),
        param(
            [FakeDir("1", files=[FakeFile("1.txt"), FakeFile("2.txt")])], id="one_dir_with_files"
        ),
        param(
            [FakeDir("1"), FakeDir("2"), FakeDir("3/4"), FakeDir("5/6/7")],
            id="many_dirs_with_no_files",
        ),
        param(
            [
                FakeDir("1", files=[FakeFile("1.txt")]),
                FakeDir("2", files=[FakeFile("2.txt")], dirs=[FakeDir("2.1")]),
                FakeDir("3/4", files=[FakeFile("3.txt"), FakeFile("4.txt")]),
                FakeDir("5/6/7"),
            ],
            id="many_dirs_with_files",
        ),
    ],
)
def test_rmdir(tmp_path: Path, sources: t.Sequence[FakeFile]):
    base_dir = FakeDir(tmp_path)
    srcs = [base_dir.add(source) for source in sources]

    for src in srcs:
        assert src.path.exists()

    sh.rmdir(*(src.path for src in srcs))

    for src in srcs:
        assert not src.path.exists()


def test_rmdir__raises_on_file(tmp_path: Path):
    path = tmp_path / "test.txt"
    path.touch()

    with pytest.raises(NotADirectoryError):
        sh.rmdir(path)


@parametrize(
    "sources",
    [
        param([FakeFile("1.txt")], id="one_file"),
        param([FakeFile("1.txt"), FakeFile("2.txt"), FakeFile("3.txt")], id="many_files"),
    ],
)
def test_rmfile(tmp_path: Path, sources: t.Sequence[FakeFile]):
    base_dir = FakeDir(tmp_path)
    srcs = [base_dir.add(source) for source in sources]

    for src in srcs:
        assert src.path.exists()

    sh.rmfile(*(src.path for src in srcs))

    for src in srcs:
        assert not src.path.exists()


def test_rmfile__raises_on_dir(tmp_path: Path):
    path = tmp_path / "test"
    path.mkdir()

    with pytest.raises(OSError):
        sh.rmfile(path)


@parametrize(
    "rm_fn",
    [
        param(sh.rm),
        param(sh.rmdir),
        param(sh.rmfile),
    ],
)
def test_rm__ignores_missing_sources(tmp_path: Path, rm_fn: t.Callable):
    rm_fn(tmp_path / "1", tmp_path / "2", tmp_path / "3")
