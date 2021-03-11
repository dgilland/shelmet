import errno
import os
from pathlib import Path
import typing as t
from unittest import mock

import pytest
from pytest import param

import shelmet as sh

from .utils import Dir, File


parametrize = pytest.mark.parametrize


@parametrize(
    "src_file, dst_file, expected",
    [
        param(
            File("src.txt", text="src"),
            File("dst.txt"),
            File("dst.txt", text="src"),
            id="to_new_file",
        ),
        param(
            File("src.txt", text="src"),
            File("dst.txt", text="dst"),
            File("dst.txt", text="src"),
            id="to_overwite_existing_file",
        ),
    ],
)
def test_mv__moves_file_to_file(tmp_path: Path, src_file: File, dst_file: File, expected: File):
    base_dir = Dir(tmp_path, src_file)
    base_dir.mkdir()

    expected_file_path = base_dir.path / expected.path
    expected_file_text = expected.text

    dst_target_path = base_dir.path / dst_file.path
    if dst_file.text:
        dst_target_path.write_text(dst_file.text)

    sh.mv(src_file.path, dst_target_path)

    assert not src_file.path.exists()
    assert expected_file_path.exists()
    assert expected_file_path.read_text() == expected_file_text


@parametrize(
    "src_file, dst_dir, expected",
    [
        param(
            File("src.txt", text="src"),
            Dir("dst"),
            File("dst/src.txt", text="src"),
            id="to_new_file_under_destination",
        ),
    ],
)
def test_mv__moves_file_to_dir(tmp_path: Path, src_file: File, dst_dir: Dir, expected: File):
    base_dir = Dir(tmp_path, src_file)
    base_dir.mkdir()

    expected_file_path = base_dir.path / expected.path
    expected_file_text = expected.text

    dst_target_path = base_dir.path / dst_dir.path
    dst_target_path.mkdir()

    sh.mv(src_file.path, dst_target_path)

    assert not src_file.path.exists()
    assert expected_file_path.exists()
    assert expected_file_path.read_text() == expected_file_text


@parametrize(
    "src_files, dst, expected",
    [
        param([File("1.txt", text="1")], "dst", "dst", id="to_new_dir"),
        param(
            [File("1.txt", text="1")],
            Dir("dst", File("2.txt")),
            "dst/src",
            id="to_new_dir_under_destination",
        ),
        param(
            [File("1.txt", text="1")],
            Dir("dst", Dir("src")),
            "dst/src",
            id="to_new_dir_overwriting_existing_dir_under_destination",
        ),
    ],
)
def test_mv__moves_dir(
    tmp_path: Path, src_files: t.List[File], dst: t.Union[Dir, str], expected: str
):
    src_dir = Dir(tmp_path / "src", *src_files)
    src_dir.mkdir()

    if isinstance(dst, Dir):
        dst_dir = Dir(tmp_path / dst.path, *dst.files)
        dst_dir.mkdir()
    else:
        dst_dir = Dir(tmp_path / dst)

    sh.mv(src_dir.path, dst_dir.path)

    expected_dst_dir = Dir(tmp_path / expected)
    assert not src_dir.path.exists()
    assert expected_dst_dir.path.exists()

    for src_file in src_files:
        dst_file_path = expected_dst_dir.path / src_file.path.name
        assert dst_file_path.read_text() == src_file.text


def test_mv__allows_same_file_as_destination(tmp_path: Path):
    src_file = File(tmp_path / "src.txt", text="src")
    src_file.write()
    sh.mv(src_file.path, src_file.path)
    assert src_file.path.exists()
    assert src_file.path.read_text() == src_file.text


def test_mv__works_across_file_systems(tmp_path: Path):
    src_file = File(tmp_path / "src.txt", text="src")
    src_file.write()

    dst_file = File(tmp_path / "dst.txt")
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
    src_dir = Dir(tmp_path / "src", File("src.txt", text="src"))
    src_dir.mkdir()
    dst_dir = Dir(tmp_path / "dst", File("src/other.txt", text="other"))
    dst_dir.mkdir()

    with pytest.raises(OSError):
        sh.mv(src_dir.path, dst_dir.path)
