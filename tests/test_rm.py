from pathlib import Path
import typing as t

import pytest
from pytest import param

import shelmet as sh

from .utils import Dir, File


parametrize = pytest.mark.parametrize


@parametrize(
    "sources",
    [
        param([File("1.txt")], id="one_file"),
        param([File("1.txt"), File("2.txt"), File("3.txt")], id="many_files"),
        param([Dir("1")], id="one_dir_with_no_files"),
        param([Dir("1", File("1.txt"), File("2.txt"))], id="one_dir_with_files"),
        param(
            [Dir("1"), Dir("2"), Dir("3/4"), Dir("5/6/7")],
            id="many_dirs_with_no_files",
        ),
        param(
            [
                Dir("1", File("1.txt")),
                Dir("2", File("2.txt"), Dir("2.1")),
                Dir("3/4", File("3.txt"), File("4.txt")),
                Dir("5/6/7"),
            ],
            id="many_dirs_with_files",
        ),
    ],
)
def test_rm(tmp_path: Path, sources: t.Sequence[File]):
    base_dir = Dir(tmp_path, *sources)
    base_dir.mkdir()

    for src in sources:
        assert src.path.exists()

    sh.rm(*(src.path for src in sources))

    for src in sources:
        assert not src.path.exists()


@parametrize(
    "sources",
    [
        param([Dir("1")], id="one_dir_with_no_files"),
        param([Dir("1", File("1.txt"), File("2.txt"))], id="one_dir_with_files"),
        param(
            [Dir("1"), Dir("2"), Dir("3/4"), Dir("5/6/7")],
            id="many_dirs_with_no_files",
        ),
        param(
            [
                Dir("1", File("1.txt")),
                Dir("2", File("2.txt"), Dir("2.1")),
                Dir("3/4", File("3.txt"), File("4.txt")),
                Dir("5/6/7"),
            ],
            id="many_dirs_with_files",
        ),
    ],
)
def test_rmdir(tmp_path: Path, sources: t.Sequence[File]):
    base_dir = Dir(tmp_path, *sources)
    base_dir.mkdir()

    for src in sources:
        assert src.path.exists()

    sh.rmdir(*(src.path for src in sources))

    for src in sources:
        assert not src.path.exists()


def test_rmdir__raises_on_file(tmp_path: Path):
    path = tmp_path / "test.txt"
    path.touch()

    with pytest.raises(NotADirectoryError):
        sh.rmdir(path)


@parametrize(
    "sources",
    [
        param([File("1.txt")], id="one_file"),
        param([File("1.txt"), File("2.txt"), File("3.txt")], id="many_files"),
    ],
)
def test_rmfile(tmp_path: Path, sources: t.Sequence[File]):
    base_dir = Dir(tmp_path, *sources)
    base_dir.mkdir()

    for src in sources:
        assert src.path.exists()

    sh.rmfile(*(src.path for src in sources))

    for src in sources:
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
