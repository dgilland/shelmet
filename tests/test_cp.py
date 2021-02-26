from pathlib import Path

import pytest

import shelmet as sh

from .utils import FakeDir, FakeFile


def test_cp__raises_when_copying_dir_to_existing_file(tmp_path: Path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    dst_file = tmp_path / "dst" / "dst.txt"
    dst_file.parent.mkdir()
    dst_file.touch()

    with pytest.raises(FileExistsError):
        sh.cp(src_dir, dst_file)


def test_cp__copies_file_to_file(tmp_path: Path):
    src_dir = FakeDir(tmp_path / "src")
    src_file = src_dir.add_file("test.txt", text="test")

    dst_file = tmp_path / "dst" / "target.txt"
    sh.cp(src_file.path, dst_file)

    assert dst_file.is_file()
    assert dst_file.read_text() == src_file.text


def test_cp__copies_file_to_existing_dir(tmp_path: Path):
    src_dir = FakeDir(tmp_path / "src")
    src_file = src_dir.add_file("test.txt", text="test")

    dst_dir = FakeDir(tmp_path / "dst")
    dst_dir.mkdir()
    sh.cp(src_file.path, dst_dir.path)

    dst_file = dst_dir.path / src_file.path.name
    assert dst_file.is_file()
    assert dst_file.read_text() == src_file.text


def test_cp__copies_dir_to_new_dir(tmp_path: Path):
    src_files = [
        FakeFile("1.txt", text="1"),
        FakeFile("2.txt", text="2"),
        FakeFile("a/a1.txt", text="a1"),
        FakeFile("a/a2.txt", text="a2"),
    ]
    src_dir = FakeDir(tmp_path / "src")
    src_dir.mkdir(files=src_files)

    dst_dir = FakeDir(tmp_path / "dst")
    sh.cp(src_dir.path, dst_dir.path)

    for src_file in src_files:
        dst_file = dst_dir.path / src_file.path
        assert dst_file.is_file()
        assert dst_file.read_text() == src_file.text


def test_cp__copies_and_merge_dir_to_existing_dir(tmp_path: Path):
    src_files = [
        FakeFile("1.txt", text="1"),
        FakeFile("2.txt", text="2"),
        FakeFile("a/a1.txt", text="a1"),
        FakeFile("a/a2.txt", text="a2"),
    ]
    src_dir = FakeDir(tmp_path / "src")
    src_dir.mkdir(files=src_files)

    dst_files = [
        FakeFile("11.txt", text="11"),
        FakeFile("22.txt", text="22"),
        FakeFile("a/b1.txt", text="b1"),
        FakeFile("a/b2.txt", text="b2"),
    ]
    dst_dir = FakeDir(tmp_path / "dst")
    dst_dir.mkdir(files=dst_files)

    sh.cp(src_dir.path, dst_dir.path)

    for file in src_files + dst_files:
        dst_file = dst_dir.path / file.path
        assert dst_file.is_file()
        assert dst_file.read_text() == file.text
