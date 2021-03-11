from pathlib import Path

import pytest

import shelmet as sh

from .utils import Dir, File


def test_cp__raises_when_copying_dir_to_existing_file(tmp_path: Path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    dst_file = tmp_path / "dst" / "dst.txt"
    dst_file.parent.mkdir()
    dst_file.touch()

    with pytest.raises(FileExistsError):
        sh.cp(src_dir, dst_file)


def test_cp__copies_file_to_file(tmp_path: Path):
    src_file = File("test.txt", text="test")
    src_dir = Dir(tmp_path / "src", src_file)
    src_dir.mkdir()

    dst_file = tmp_path / "dst" / "target.txt"
    sh.cp(src_file.path, dst_file)

    assert dst_file.is_file()
    assert dst_file.read_text() == src_file.text


def test_cp__copies_file_to_existing_dir(tmp_path: Path):
    src_file = File("test.txt", text="test")
    src_dir = Dir(tmp_path / "src", src_file)
    src_dir.mkdir()

    dst_dir = Dir(tmp_path / "dst")
    dst_dir.mkdir()
    sh.cp(src_file.path, dst_dir.path)

    dst_file = dst_dir.path / src_file.path.name
    assert dst_file.is_file()
    assert dst_file.read_text() == src_file.text


def test_cp__copies_dir_to_new_dir(tmp_path: Path):
    src_dir = Dir(
        tmp_path / "src",
        File("1.txt", text="1"),
        File("2.txt", text="2"),
        File("a/a1.txt", text="a1"),
        File("a/a2.txt", text="a2"),
    )
    src_dir.mkdir()
    dst_path = tmp_path / "dst"

    sh.cp(src_dir.path, dst_path)

    copied_src_files = src_dir.repath(dst_path).files
    for file in copied_src_files:
        assert file.path.is_file()
        assert file.path.read_text() == file.text


def test_cp__copies_and_merge_dir_to_existing_dir(tmp_path: Path):
    src_dir = Dir(
        tmp_path / "src",
        File("1.txt", text="1"),
        File("2.txt", text="2"),
        File("a/a1.txt", text="a1"),
        File("a/a2.txt", text="a2"),
    )
    src_dir.mkdir()

    dst_dir = Dir(
        tmp_path / "dst",
        File("11.txt", text="11"),
        File("22.txt", text="22"),
        File("a/b1.txt", text="b1"),
        File("a/b2.txt", text="b2"),
    )
    dst_dir.mkdir()

    sh.cp(src_dir.path, dst_dir.path)

    copied_src_files = src_dir.repath(dst_dir.path).files
    all_files = copied_src_files + dst_dir.files

    for file in all_files:
        assert file.path.is_file()
        assert file.path.read_text() == file.text
