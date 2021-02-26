import errno
import os
from pathlib import Path
import typing as t
from unittest import mock

import pytest
from pytest import param

import shelmet as sh

from .utils import FakeDir, FakeFile


parametrize = pytest.mark.parametrize


@parametrize(
    "src, dst, expected",
    [
        param(
            FakeFile("src.txt", text="src"),
            FakeFile("dst.txt"),
            FakeFile("dst.txt", text="src"),
            id="to_new_file",
        ),
        param(
            FakeFile("src.txt", text="src"),
            FakeDir("dst"),
            FakeFile("dst/src.txt", text="src"),
            id="to_new_file_under_destination",
        ),
        param(
            FakeFile("src.txt", text="src"),
            FakeFile("dst.txt", text="dst"),
            FakeFile("dst.txt", text="src"),
            id="to_overwite_existing_file",
        ),
    ],
)
def test_mv__moves_file(
    tmp_path: Path, src: FakeFile, dst: t.Union[FakeFile, FakeDir], expected: FakeFile
):
    base_dir = FakeDir(tmp_path)
    src_file = base_dir.add_file(src)
    expected_file = base_dir.new_file(expected)

    dst_target: t.Union[FakeFile, FakeDir]
    if isinstance(dst, FakeFile):
        dst_target = base_dir.new_file(dst)
        if dst_target.text:
            dst_target.write()
    else:
        dst_target = base_dir.add_dir(dst)

    sh.mv(src_file.path, dst_target.path)

    assert not src_file.path.exists()
    assert expected_file.path.exists()
    assert expected_file.path.read_text() == expected_file.text


@parametrize(
    "src_files, dst, expected",
    [
        param([FakeFile("1.txt", text="1")], "dst", "dst", id="to_new_dir"),
        param(
            [FakeFile("1.txt", text="1")],
            FakeDir("dst", files=[FakeFile("2.txt")]),
            "dst/src",
            id="to_new_dir_under_destination",
        ),
        param(
            [FakeFile("1.txt", text="1")],
            FakeDir("dst", dirs=[FakeDir("src")]),
            "dst/src",
            id="to_new_dir_overwriting_existing_dir_under_destination",
        ),
    ],
)
def test_mv__moves_dir(
    tmp_path: Path, src_files: t.List[FakeFile], dst: t.Union[FakeDir, str], expected: str
):
    src_dir = FakeDir(tmp_path / "src", files=src_files)
    src_dir.mkdir()

    if isinstance(dst, FakeDir):
        dst_dir = FakeDir(tmp_path / dst.path, files=dst.files)
        dst_dir.mkdir()
    else:
        dst_dir = FakeDir(tmp_path / dst)

    sh.mv(src_dir.path, dst_dir.path)

    expected_dst_dir = FakeDir(tmp_path / expected)
    assert not src_dir.path.exists()
    assert expected_dst_dir.path.exists()

    for src_file in src_files:
        dst_file = expected_dst_dir.new_file(src_file)
        assert dst_file.path.read_text() == src_file.text


def test_mv__allows_same_file_as_destination(tmp_path: Path):
    src_file = FakeFile(tmp_path / "src.txt", text="src")
    src_file.write()
    sh.mv(src_file.path, src_file.path)
    assert src_file.path.exists()
    assert src_file.path.read_text() == src_file.text


def test_mv__works_across_file_systems(tmp_path: Path):
    src_file = FakeFile(tmp_path / "src.txt", text="src")
    src_file.write()

    dst_file = FakeFile(tmp_path / "dst.txt")
    _os_rename = os.rename

    def mock_os_rename(src, dst):
        if str(src) == str(src_file.path) and str(dst) == str(dst_file.path):
            raise OSError(errno.EXDEV, "mock error from move across file systems")
        return _os_rename(src, dst)

    with mock.patch("os.rename", side_effect=mock_os_rename):
        sh.mv(src_file.path, dst_file.path)

    assert dst_file.path.exists()
    assert dst_file.path.read_text() == src_file.text
    assert not src_file.path.exists()


def test_mv__raises_when_source_dir_exists_in_destination_and_is_not_empty(tmp_path: Path):
    src_dir = FakeDir(tmp_path / "src", files=[FakeFile("src.txt", text="src")])
    src_dir.mkdir()
    dst_dir = FakeDir(tmp_path / "dst", files=[FakeFile("src/other.txt", text="other")])
    dst_dir.mkdir()

    with pytest.raises(OSError):
        sh.mv(src_dir.path, dst_dir.path)
