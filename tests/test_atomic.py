from pathlib import Path
import typing as t

import pytest
from pytest import param

import shelmet as sh

from .utils import FakeDir, FakeFile, patch_os_fsync


parametrize = pytest.mark.parametrize


@parametrize(
    "opts",
    [
        param({}),
        param({"overwrite": False}),
        param({"skip_sync": True}),
        param({"overwrite": False, "skip_sync": True}),
    ],
)
def test_atomicdir(tmp_path: Path, opts: t.Dict[str, t.Any]):
    dir = FakeDir(tmp_path / "test")
    files = [
        FakeFile("1.txt", text="1"),
        FakeFile("2.txt", text="2"),
        FakeFile("3.txt", text="3"),
        FakeFile("a/a.txt", text="a"),
        FakeFile("b/b.txt", text="b"),
        FakeFile("c/c.txt", text="c"),
    ]

    with sh.atomicdir(dir.path, **opts) as tmp_path:
        assert tmp_path.exists()
        assert not dir.path.exists()

        FakeDir(tmp_path).mkdir(files=files)

        assert not dir.path.exists()

    assert dir.path.exists()
    for file in files:
        file_path = dir.path / file.path
        assert file_path.exists()
        assert file_path.read_text() == file.text


def test_atomicdir__syncs_dir(tmp_path: Path):
    dir = tmp_path / "test"

    with patch_os_fsync() as mocked_os_fsync:
        with sh.atomicdir(dir):
            pass

    assert mocked_os_fsync.called
    assert mocked_os_fsync.call_count == 2


def test_atomicdir__skips_sync_when_disabled(tmp_path: Path):
    dir = tmp_path / "test"

    with patch_os_fsync() as mocked_os_fsync:
        with sh.atomicdir(dir, skip_sync=True):
            pass

    assert not mocked_os_fsync.called


def test_atomicdir__overwrites_when_enabled(tmp_path: Path):
    dir = FakeDir(tmp_path / "test", files=[FakeFile("1"), FakeFile("2"), FakeFile("3")])
    dir.mkdir()

    assert list(dir.path.iterdir())

    with sh.atomicdir(dir.path):
        pass

    assert not list(dir.path.iterdir())


def test_atomicdir__does_not_overwrite_when_disabled(tmp_path: Path):
    dir = FakeDir(tmp_path / "test", files=[FakeFile("1"), FakeFile("2"), FakeFile("3")])
    dir.mkdir()

    with pytest.raises(FileExistsError):
        with sh.atomicdir(dir.path, overwrite=False):
            pass


def test_atomicdir__fails_if_path_is_file(tmp_path: Path):
    already_exists_file = tmp_path / "test"
    already_exists_file.write_text("")

    with pytest.raises(FileExistsError):
        with sh.atomicdir(already_exists_file):
            pass


@parametrize(
    "opts",
    [
        param({}),
        param({"overwrite": False}),
        param({"skip_sync": True}),
        param({"overwrite": False, "skip_sync": True}),
    ],
)
def test_atomicfile(tmp_path: Path, opts: t.Dict[str, t.Any]):
    file = tmp_path / "test.txt"
    text = "test"

    with sh.atomicfile(file, **opts) as fp:
        assert not file.exists()
        fp.write(text)
        assert not file.exists()

    assert file.exists()
    assert file.read_text() == text


def test_atomicfile__syncs_new_file_and_dir(tmp_path: Path):
    file = tmp_path / "test.txt"

    with patch_os_fsync() as mocked_os_fsync:
        with sh.atomicfile(file) as fp:
            fp.write("test")

    assert mocked_os_fsync.called
    assert mocked_os_fsync.call_count == 2


def test_atomicfile__skips_sync_when_disabled(tmp_path: Path):
    file = tmp_path / "test.txt"

    with patch_os_fsync() as mocked_os_fsync:
        with sh.atomicfile(file, skip_sync=True) as fp:
            fp.write("test")

    assert not mocked_os_fsync.called


def test_atomicfile__does_not_overwrite_when_disabled(tmp_path: Path):
    file = tmp_path / "test.txt"
    file.write_text("")

    with pytest.raises(FileExistsError):
        with sh.atomicfile(file, overwrite=False):
            pass


def test_atomicfile__fails_if_path_is_dir(tmp_path: Path):
    already_exists_dir = tmp_path
    with pytest.raises(IsADirectoryError):
        with sh.atomicfile(already_exists_dir):
            pass

    will_exist_dir = tmp_path / "test"
    with pytest.raises(IsADirectoryError):
        with sh.atomicfile(will_exist_dir) as fp:
            will_exist_dir.mkdir()
            fp.write("test")


@parametrize(
    "mode",
    [
        param("r"),
        param("r+"),
        param("rb"),
        param("rb+"),
        param("a"),
        param("a+"),
        param("ab"),
        param("ab+"),
        param("x"),
        param("x+"),
        param(True),
    ],
)
def test_atomicfile__raises_when_mode_invalid(tmp_path: Path, mode: t.Any):
    with pytest.raises(ValueError):
        with sh.atomicfile(tmp_path / "test.txt", mode):
            pass
