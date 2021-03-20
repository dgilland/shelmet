from contextlib import ExitStack
from pathlib import Path
import tarfile
import typing as t
from unittest import mock
import zipfile

import pytest
from pytest import param

import shelmet as sh

from .utils import Dir, File, is_same_dir


parametrize = pytest.mark.parametrize


TAR_COMPRESSIONS = {
    ".tar": "",
    ".tar.gz": "gz",
    ".tgz": "gz",
    ".taz": "gz",
    ".tar.bz2": "bz2",
    ".tb2": "bz2",
    ".tbz": "bz2",
    ".tbz2": "bz2",
    ".tz2": "bz2",
    ".tar.xz": "xz",
    ".txz": "xz",
}
TAR_EXTENSIONS = list(TAR_COMPRESSIONS.keys())
ZIP_EXTENSIONS = [
    ".docx",
    ".egg",
    ".jar",
    ".odg",
    ".odp",
    ".ods",
    ".odt",
    ".pptx",
    ".xlsx",
    ".zip",
]


def extract_archive(archive_file: Path, dst: Path, ext: str = "") -> None:
    if not ext:
        ext = "".join(archive_file.suffixes)

    if ext in TAR_EXTENSIONS:
        _extract_tar(archive_file, dst, ext=ext)
    elif ext in ZIP_EXTENSIONS:
        _extract_zip(archive_file, dst)
    else:
        raise ValueError(f"unrecognized archive extension: {ext}")


def create_archive(archive_file: Path, *sources: Path, ext: str = "") -> None:
    if not ext:
        ext = "".join(archive_file.suffixes)

    if ext in TAR_EXTENSIONS:
        _create_tar(archive_file, *sources, ext=ext)
    elif ext in ZIP_EXTENSIONS:
        _create_zip(archive_file, *sources)
    else:
        raise ValueError(f"unrecognized archive extension: {ext}")


def create_unsafe_archive(archive_file: Path, *sources: Path) -> None:
    ext = "".join(archive_file.suffixes)

    if ext in TAR_EXTENSIONS:
        _create_unsafe_tar(archive_file, *sources)
    elif ext in ZIP_EXTENSIONS:
        _create_unsafe_zip(archive_file, *sources)
    else:
        raise ValueError(f"unrecognized archive extension: {ext}")


def _extract_tar(archive_file: Path, dst: Path, ext: str = "") -> None:
    if not ext:
        ext = "".join(archive_file.suffixes)
    compression = TAR_COMPRESSIONS[ext]
    mode = f"r:{compression}"
    with tarfile.open(archive_file, mode) as arc:
        arc.extractall(dst)


def _extract_zip(archive_file: Path, dst: Path) -> None:
    with zipfile.ZipFile(archive_file) as arc:
        arc.extractall(dst)


def _create_tar(archive_file: Path, *sources: Path, ext: str = "") -> None:
    if not ext:
        ext = "".join(archive_file.suffixes)
    compression = TAR_COMPRESSIONS[ext]
    mode = f"w:{compression}"
    with tarfile.open(archive_file, mode) as archive:
        for src in sources:
            archive.add(src, arcname=src.name)


def _create_zip(archive_file: Path, *sources: Path) -> None:
    with zipfile.ZipFile(archive_file, "w") as archive:
        for src in sources:
            with sh.cd(src.parent):
                items = [src.relative_to(src.parent), *sh.walk(src.name)]
                for item in items:
                    archive.write(item)


def _create_unsafe_tar(archive_file: Path, src: Path, parent_path: Path) -> None:
    ext = "".join(archive_file.suffixes)
    compression = TAR_COMPRESSIONS[ext]
    mode = f"w:{compression}"
    with tarfile.open(archive_file, mode) as archive:
        with sh.cd(src.parent):
            items = [src.relative_to(src.parent)] + list(sh.walk(src.name))
            for item in items:
                member = archive.gettarinfo(str(item))
                member.name = str(parent_path / member.name)
                archive.addfile(member)


def _create_unsafe_zip(archive_file: Path, src: Path, parent_path: Path) -> None:
    with zipfile.ZipFile(archive_file, "w") as archive:
        with sh.cd(src.parent):
            items = [src.relative_to(src.parent)] + list(sh.walk(src.name))
            for item in items:
                member = zipfile.ZipInfo.from_file(str(item))
                member.filename = str(parent_path / member.filename)
                data = item.read_text() if item.is_file() else ""
                archive.writestr(member, data=data)


@pytest.fixture(params=TAR_EXTENSIONS + ZIP_EXTENSIONS)
def arc_ext(request) -> str:
    return request.param


@parametrize(
    "source",
    [
        param(File("1.txt", text="1")),
        param(Dir("a", Dir("b"), File("1.txt", text="1"), File("2.txt", text="2"))),
        param(
            Dir(
                "root",
                Dir(
                    "a",
                    Dir(
                        "aa",
                        Dir("aaa", File("aaa1.txt", text="aaa1"), Dir("aaaa")),
                        File("aa1.txt", text="aa1"),
                    ),
                    File("a1.txt", text="a1"),
                    File("a2.txt", text="a2"),
                ),
                Dir("b"),
                Dir("c"),
                Dir("d"),
                File("1.txt", text="1"),
                File("2.txt", text="2"),
                File("3.txt", text="3"),
            ),
        ),
    ],
)
def test_archive__archives_single_source(tmp_path: Path, arc_ext: str, source: t.Union[Dir, File]):
    source = source.clone()
    src_dir = Dir(tmp_path / "src", source)
    src_dir.mkdir()

    archive_file = tmp_path / f"archive{arc_ext}"
    sh.archive(archive_file, source.path)

    assert archive_file.is_file()

    dst_path = tmp_path / "dst"
    extract_archive(archive_file, dst_path)

    assert dst_path.is_dir()
    assert is_same_dir(src_dir.path, dst_path)


@parametrize(
    "sources",
    [
        param(
            [
                Dir(
                    "a",
                    Dir(
                        "aa",
                        Dir("aaa", File("aaa1.txt", text="aaa1"), Dir("aaaa")),
                        File("aa1.txt", text="aa1"),
                    ),
                    File("a1.txt", text="a1"),
                    File("a2.txt", text="a2"),
                ),
                Dir("b"),
                Dir("c"),
                Dir("d"),
                File("1.txt", text="1"),
                File("2.txt", text="2"),
                File("3.txt", text="3"),
            ],
        ),
    ],
)
def test_archive__archives_multiple_sources(
    tmp_path: Path, arc_ext: str, sources: t.List[t.Union[Dir, File]]
):
    sources = [source.clone() for source in sources]
    src_dir = Dir(tmp_path / "src", *sources)
    src_dir.mkdir()

    archive_file = tmp_path / f"archive{arc_ext}"
    sh.archive(archive_file, *(dir.path for dir in sources))

    assert archive_file.is_file()

    dst_path = tmp_path / "dst"
    extracted_src_path = dst_path / src_dir.path.name
    extract_archive(archive_file, dst_path)

    assert dst_path.is_dir()
    assert extracted_src_path.is_dir()
    assert is_same_dir(src_dir.path, extracted_src_path)


def test_archive__archives_with_explicit_extension_format(tmp_path: Path, arc_ext: str):
    sources = [Dir("a", Dir("b"), File("1.txt", text="1"), File("2.txt", text="2"))]
    src_dir = Dir(tmp_path / "src", *sources)
    src_dir.mkdir()

    archive_file = tmp_path / "archive"
    sh.archive(archive_file, *(dir.path for dir in sources), ext=arc_ext)

    assert archive_file.is_file()

    dst_path = tmp_path / "dst"
    extract_archive(archive_file, dst_path, ext=arc_ext)

    assert dst_path.is_dir()
    assert is_same_dir(src_dir.path, dst_path)


def test_archive__raises_when_file_extension_not_supported(tmp_path: Path):
    with pytest.raises(sh.ArchiveError) as exc_info:
        sh.archive(tmp_path / "test.txt")
    assert "format not supported" in str(exc_info.value)


def test_archive__raises_when_add_fails(tmp_path: Path, arc_ext: str):
    src_dir = Dir(tmp_path / "src", File("1.txt", text="1"))
    src_dir.mkdir()

    with ExitStack() as mock_stack:
        mock_stack.enter_context(mock.patch("tarfile.TarFile.add", side_effect=Exception))
        mock_stack.enter_context(mock.patch("zipfile.ZipFile.write", side_effect=Exception))

        with pytest.raises(sh.ArchiveError):
            sh.archive(tmp_path / f"archive{arc_ext}", src_dir.path)


@parametrize(
    "source", [param(Dir("a", Dir("b"), File("1.txt", text="1"), File("2.txt", text="2")))]
)
def test_unarchive__unarchives(tmp_path: Path, arc_ext: str, source: t.Union[File, Dir]):
    source = source.clone()
    src_dir = Dir(tmp_path / "src", source)
    src_dir.mkdir()

    archive_file = tmp_path / f"archive{arc_ext}"
    create_archive(archive_file, src_dir.path)

    dst_path = tmp_path / "dst"
    sh.unarchive(archive_file, dst_path)

    assert dst_path.is_dir()
    assert is_same_dir(src_dir.path, dst_path / "src")


def test_unarchive__unarchives_with_explicit_extension_format(tmp_path: Path, arc_ext: str):
    source = Dir("a", Dir("b"), File("1.txt", text="1"), File("2.txt", text="2"))
    src_dir = Dir(tmp_path / "src", source)
    src_dir.mkdir()

    archive_file = tmp_path / "archive"
    create_archive(archive_file, src_dir.path, ext=arc_ext)

    dst_path = tmp_path / "dst"
    sh.unarchive(archive_file, dst_path, ext=arc_ext)

    assert dst_path.is_dir()
    assert is_same_dir(src_dir.path, dst_path / "src")


def test_unarchive__raises_when_file_extension_not_supported():
    with pytest.raises(sh.ArchiveError) as exc_info:
        sh.unarchive("test.txt")
    assert "format not supported" in str(exc_info.value)


def test_unarchive__raises_when_extraction_fails(tmp_path: Path, arc_ext: str):
    src_dir = Dir(tmp_path / "src", File("1.txt", text="1"))
    src_dir.mkdir()

    archive_file = tmp_path / "archive.tar"
    create_archive(archive_file, src_dir.path)

    with ExitStack() as mock_stack:
        mock_stack.enter_context(mock.patch("tarfile.TarFile.extractall", side_effect=Exception))
        mock_stack.enter_context(mock.patch("zipfile.ZipFile.extractall", side_effect=Exception))

        with pytest.raises(sh.ArchiveError):
            sh.unarchive(archive_file, tmp_path / "dst")


def test_unarchive__unarchives_trusted_archive_outside_target(tmp_path: Path):
    src_dir = Dir(tmp_path / "src", File("1.txt", text="1"))
    src_dir.mkdir()

    unsafe_archive_file = tmp_path / "unsafe.tar"
    unsafe_dest = tmp_path / "unsafe"
    _create_unsafe_tar(unsafe_archive_file, src_dir.path, unsafe_dest)

    dst_path = tmp_path / "dst"
    sh.unarchive(unsafe_archive_file, dst_path, trusted=True)

    assert not dst_path.exists()
    assert unsafe_dest.exists()
    assert is_same_dir(src_dir.path, unsafe_dest / "src")


def test_unarchive__raises_when_untrusted_tar_would_extract_outside_target(
    tmp_path: Path, arc_ext: str
):
    src_dir = Dir(tmp_path / "src", File("1.txt", text="1"))
    src_dir.mkdir()

    unsafe_archive_file = tmp_path / f"unsafe{arc_ext}"
    unsafe_dest = tmp_path / "unsafe"
    create_unsafe_archive(unsafe_archive_file, src_dir.path, unsafe_dest)

    dst_path = tmp_path / "dst"
    with pytest.raises(sh.ArchiveError) as exc_info:
        sh.unarchive(unsafe_archive_file, dst_path)

    assert "destination is outside the target directory" in str(exc_info.value)
    assert not dst_path.exists()
    assert not unsafe_dest.exists()
