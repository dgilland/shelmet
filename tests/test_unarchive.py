from contextlib import ExitStack
from pathlib import Path
import typing as t
from unittest import mock

import pytest
from pytest import param

import shelmet as sh

from .utils import (
    ARCHIVE_EXTENSIONS,
    Dir,
    File,
    create_archive,
    create_archive_source,
    create_unsafe_archive,
    is_same_dir,
)


parametrize = pytest.mark.parametrize


def _test_unarchive(tmp_path: Path, archive_file: Path, source: t.Union[File, Dir], ext: str = ""):
    src_dir = create_archive_source(tmp_path, source)
    create_archive(archive_file, src_dir.path, ext=ext)

    dst_path = tmp_path / "dst"
    sh.unarchive(archive_file, dst_path, ext=ext)

    assert dst_path.is_dir()
    assert is_same_dir(src_dir.path, dst_path / "src")


@pytest.fixture(params=ARCHIVE_EXTENSIONS)
def arc_ext(request) -> str:
    """Fixture that yields all archive extensions."""
    return request.param


@pytest.fixture(params=[".tar", ".zip"])
def rep_ext(request) -> str:
    """Fixture that yields a representative sample of archive extensions."""
    return request.param


@parametrize(
    "source", [param(Dir("a", Dir("b"), File("1.txt", text="1"), File("2.txt", text="2")))]
)
def test_unarchive__unarchives(tmp_path: Path, arc_ext: str, source: t.Union[File, Dir]):
    archive_file = tmp_path / f"archive{arc_ext}"
    _test_unarchive(tmp_path, archive_file, source)


def test_unarchive__unarchives_with_explicit_extension_format(tmp_path: Path, arc_ext: str):
    source = Dir("a", Dir("b"), File("1.txt", text="1"), File("2.txt", text="2"))
    archive_file = tmp_path / "archive"
    _test_unarchive(tmp_path, archive_file, source, ext=arc_ext)


def test_unarchive__raises_when_file_extension_not_supported():
    with pytest.raises(NotImplementedError) as exc_info:
        sh.unarchive("test.txt")
    assert "format not supported" in str(exc_info.value)


def test_unarchive__raises_when_extraction_fails(tmp_path: Path, rep_ext: str):
    archive_file = tmp_path / f"archive{rep_ext}"
    src_dir = create_archive_source(tmp_path, File("1.txt", text="1"))
    create_archive(archive_file, src_dir.path)

    with ExitStack() as mock_stack:
        mock_stack.enter_context(mock.patch("tarfile.TarFile.extractall", side_effect=Exception))
        mock_stack.enter_context(mock.patch("zipfile.ZipFile.extractall", side_effect=Exception))

        with pytest.raises(sh.ArchiveError):
            sh.unarchive(archive_file, tmp_path / "dst")


def test_unarchive__unarchives_trusted_archive_outside_target(tmp_path: Path):
    src_dir = create_archive_source(tmp_path, File("1.txt", text="1"))

    unsafe_archive_file = tmp_path / "unsafe.tar"
    unsafe_dest = tmp_path / "unsafe"
    create_unsafe_archive(unsafe_archive_file, src_dir.path, unsafe_dest)

    dst_path = tmp_path / "dst"
    sh.unarchive(unsafe_archive_file, dst_path, trusted=True)

    assert not dst_path.exists()
    assert unsafe_dest.exists()
    assert is_same_dir(src_dir.path, unsafe_dest / "src")


def test_unarchive__raises_when_untrusted_archive_would_extract_outside_target(
    tmp_path: Path, rep_ext: str
):
    src_dir = create_archive_source(tmp_path, File("1.txt", text="1"))

    unsafe_archive_file = tmp_path / f"unsafe{rep_ext}"
    unsafe_dest = tmp_path / "unsafe"
    create_unsafe_archive(unsafe_archive_file, src_dir.path, unsafe_dest)

    dst_path = tmp_path / "dst"
    with pytest.raises(sh.UnsafeArchiveError) as exc_info:
        sh.unarchive(unsafe_archive_file, dst_path)

    assert "destination is outside the target directory" in str(exc_info.value)
    assert not dst_path.exists()
    assert not unsafe_dest.exists()
