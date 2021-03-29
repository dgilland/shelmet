from contextlib import ExitStack
from pathlib import Path
import typing as t
from unittest import mock

import pytest
from pytest import param

import shelmet as sh
from shelmet.archiving import ArchiveSource

from .utils import (
    ARCHIVE_EXTENSIONS,
    Dir,
    File,
    create_archive_source,
    extract_archive,
    is_same_dir,
)


parametrize = pytest.mark.parametrize


def _test_archive(
    tmp_path: Path,
    archive_file: Path,
    *sources: t.Union[Dir, File],
    iteratee: t.Callable[[Path], t.Union[str, Path, sh.Ls]] = lambda p: p,
    ext: str = "",
    skip_extraction: bool = False,
):
    src_dir = create_archive_source(tmp_path, *sources)
    sh.archive(archive_file, *(iteratee(source.path) for source in src_dir.items), ext=ext)
    assert archive_file.is_file()

    if skip_extraction:
        return

    dst_path = tmp_path / "dst"
    if len(src_dir.items) > 1:
        extracted_src_path = dst_path / src_dir.path.name
    else:
        extracted_src_path = dst_path

    extract_archive(archive_file, dst_path, ext=ext)

    assert dst_path.is_dir()
    assert extracted_src_path.is_dir()
    assert is_same_dir(src_dir.path, extracted_src_path)


@pytest.fixture(params=ARCHIVE_EXTENSIONS)
def arc_ext(request) -> str:
    """Fixture that yields all archive extensions."""
    return request.param


@pytest.fixture(params=[".tar", ".zip"])
def rep_ext(request) -> str:
    """Fixture that yields a representative sample of archive extensions."""
    return request.param


@parametrize(
    "sources",
    [
        param([File("1.txt", text="1")]),
        param([Dir("a", Dir("b"), File("1.txt", text="1"), File("2.txt", text="2"))]),
        param(
            [
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
                )
            ]
        ),
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
            ]
        ),
    ],
)
def test_archive__archives_path_sources(
    tmp_path: Path, arc_ext: str, sources: t.List[t.Union[Dir, File]]
):
    archive_file = tmp_path / f"archive{arc_ext}"
    _test_archive(tmp_path, archive_file, *sources)


@parametrize(
    "sources",
    [
        param(
            [
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
            ]
        ),
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
            ]
        ),
    ],
)
def test_archive__archives_ls_sources(tmp_path: Path, arc_ext: str, sources: t.List[Dir]):
    archive_file = tmp_path / f"archive{arc_ext}"
    _test_archive(tmp_path, archive_file, *sources, iteratee=sh.walk)


@parametrize(
    "sources, ls_func, expected_listing",
    [
        param(
            [
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
            ],
            sh.ls,
            {
                Path("root"),
                Path("root/a"),
                Path("root/b"),
                Path("root/c"),
                Path("root/d"),
                Path("root/1.txt"),
                Path("root/2.txt"),
                Path("root/3.txt"),
            },
        ),
        param(
            [
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
            ],
            sh.walkfiles,
            {
                Path("root"),
                Path("root/1.txt"),
                Path("root/2.txt"),
                Path("root/3.txt"),
                Path("root/a/a1.txt"),
                Path("root/a/a2.txt"),
                Path("root/a/aa/aa1.txt"),
                Path("root/a/aa/aaa/aaa1.txt"),
            },
        ),
    ],
)
def test_archive__archives_filtered_ls_sources(
    tmp_path: Path,
    arc_ext: str,
    sources: t.List[Dir],
    ls_func: t.Callable[[Path], sh.Ls],
    expected_listing: t.Set[Path],
):
    archive_file = tmp_path / f"archive{arc_ext}"
    _test_archive(tmp_path, archive_file, *sources, iteratee=ls_func, skip_extraction=True)

    listing = set(sh.lsarchive(archive_file))
    assert listing == expected_listing


def test_archive__allows_extra_leading_file_extension_suffixes(tmp_path: Path, arc_ext: str):
    source = Dir("a", Dir("b"), File("1.txt", text="1"), File("2.txt", text="2"))
    archive_file = tmp_path / f"archive.foo.bar.baz{arc_ext}"
    _test_archive(tmp_path, archive_file, source)


def test_archive__archives_with_explicit_extension_format(tmp_path: Path, arc_ext: str):
    source = Dir("a", Dir("b"), File("1.txt", text="1"), File("2.txt", text="2"))
    archive_file = tmp_path / "archive"
    _test_archive(tmp_path, archive_file, source, ext=arc_ext)


@parametrize(
    "source, root, expected_listing",
    [
        param(
            Dir("a", File("1.txt", text="1"), File("2.txt", text="2"), File("3.txt", text="3")),
            Path("a"),
            {Path("1.txt"), Path("2.txt"), Path("3.txt")},
        )
    ],
)
def test_archive__uses_custom_root_path_inside_archive(
    tmp_path: Path,
    rep_ext: str,
    source: t.Union[File, Dir],
    root: Path,
    expected_listing: t.Set[Path],
):
    src_dir = create_archive_source(tmp_path, source)
    root = src_dir.path / root

    archive_file = tmp_path / f"archive{rep_ext}"
    sh.archive(archive_file, *(item.path for item in src_dir.items), root=root)
    assert archive_file.is_file()

    listing = set(sh.lsarchive(archive_file))
    assert listing == expected_listing


@parametrize(
    "sources, paths, root, repath, expected_listing",
    [
        param(
            [Dir("a", File("1.txt"), File("2.txt"), File("3.txt"))],
            ["a"],
            None,
            "abc",
            {Path("abc"), Path("abc/1.txt"), Path("abc/2.txt"), Path("abc/3.txt")},
        ),
        param(
            [Dir("a", File("1.txt"), File("2.txt"), File("3.txt"))],
            ["a"],
            None,
            {"a": "abc"},
            {Path("abc"), Path("abc/1.txt"), Path("abc/2.txt"), Path("abc/3.txt")},
        ),
        param(
            [
                Dir(
                    "a",
                    Dir("aa1", Dir("aaa1", File("aaa1.txt")), Dir("aaa2", File("aaa2.txt"))),
                    Dir("aa2"),
                ),
                Dir("b"),
                Dir("c"),
            ],
            ["a", "b", "c"],
            None,
            {"a": "1", Path("b"): "2"},
            {
                Path("1"),
                Path("1/aa1"),
                Path("1/aa1/aaa1"),
                Path("1/aa1/aaa1/aaa1.txt"),
                Path("1/aa1/aaa2"),
                Path("1/aa1/aaa2/aaa2.txt"),
                Path("1/aa2"),
                Path("2"),
                Path("src/c"),
            },
        ),
        param(
            [
                Dir(
                    "a",
                    Dir("aa1", Dir("aaa1", File("aaa1.txt")), Dir("aaa2", File("aaa2.txt"))),
                    Dir("aa2"),
                ),
                Dir("b"),
                Dir("c"),
            ],
            ["a", "b", "c"],
            ".",
            {"a": "1", Path("b"): "2"},
            {
                Path("1"),
                Path("1/aa1"),
                Path("1/aa1/aaa1"),
                Path("1/aa1/aaa1/aaa1.txt"),
                Path("1/aa1/aaa2"),
                Path("1/aa1/aaa2/aaa2.txt"),
                Path("1/aa2"),
                Path("2"),
                Path("c"),
            },
        ),
        param(
            [
                Dir(
                    "a",
                    Dir("aa1", Dir("aaa1", File("aaa1.txt")), Dir("aaa2", File("aaa2.txt"))),
                    Dir("aa2"),
                ),
                Dir("b"),
                Dir("c"),
            ],
            [Path("a"), sh.ls("b"), sh.walk("c")],
            ".",
            {"a": "1", "b": "2", "c": "3"},
            {
                Path("1"),
                Path("1/aa1"),
                Path("1/aa1/aaa1"),
                Path("1/aa1/aaa1/aaa1.txt"),
                Path("1/aa1/aaa2"),
                Path("1/aa1/aaa2/aaa2.txt"),
                Path("1/aa2"),
                Path("2"),
                Path("3"),
            },
        ),
    ],
)
def test_archive__repaths_paths_inside_archive(
    tmp_path: Path,
    rep_ext: str,
    sources: t.List[t.Union[File, Dir]],
    paths: t.List[t.Union[str, Path, sh.Ls]],
    root: t.Optional[Path],
    repath: t.Optional[t.Union[str, dict]],
    expected_listing: t.Set[Path],
):
    src_dir = create_archive_source(tmp_path, *sources)
    archive_file = tmp_path / f"archive{rep_ext}"

    with sh.cd(src_dir.path):
        sh.archive(archive_file, *paths, root=root, repath=repath)

    assert archive_file.is_file()

    listing = set(sh.lsarchive(archive_file))
    assert listing == expected_listing


@parametrize(
    "source, root, expected_listing",
    [
        param(
            Dir("a", File("1.txt", text="1"), File("2.txt", text="2"), File("3.txt", text="3")),
            None,
            {Path("a"), Path("a/1.txt"), Path("a/2.txt"), Path("a/3.txt")},
        ),
        param(
            Dir("a", File("1.txt", text="1"), File("2.txt", text="2"), File("3.txt", text="3")),
            Path("a"),
            {Path("1.txt"), Path("2.txt"), Path("3.txt")},
        ),
    ],
)
def test_archive__archives_relative_paths(
    tmp_path: Path,
    rep_ext: str,
    source: t.Union[File, Dir],
    root: t.Optional[Path],
    expected_listing: t.Set[Path],
):
    src_dir = create_archive_source(tmp_path, source)
    archive_file = tmp_path / f"archive{rep_ext}"

    with sh.cd(src_dir.path):
        items = [item.path.relative_to(src_dir.path) for item in src_dir.items]
        sh.archive(archive_file, *items, root=root)

    assert archive_file.is_file()

    listing = set(sh.lsarchive(archive_file))
    assert listing == expected_listing


def test_archive__raises_when_sources_are_not_subpaths_of_root_path(tmp_path: Path, rep_ext: str):
    archive_file = tmp_path / f"archive{rep_ext}"
    with pytest.raises(ValueError) as exc_info:
        sh.archive(archive_file, tmp_path, root="bad-root")
    assert "paths must be a subpath of the root" in str(exc_info.value)


def test_archive__raises_when_file_extension_not_supported(tmp_path: Path):
    with pytest.raises(NotImplementedError) as exc_info:
        sh.archive(tmp_path / "test.txt")
    assert "format not supported" in str(exc_info.value)


def test_archive__raises_when_add_fails(tmp_path: Path, rep_ext: str):
    src_dir = create_archive_source(tmp_path, File("1.txt", text="1"))

    with ExitStack() as mock_stack:
        mock_stack.enter_context(mock.patch("tarfile.TarFile.add", side_effect=Exception))
        mock_stack.enter_context(mock.patch("zipfile.ZipFile.write", side_effect=Exception))

        with pytest.raises(sh.ArchiveError):
            sh.archive(tmp_path / f"archive{rep_ext}", src_dir.path)


@parametrize(
    "paths, repath, expected_error",
    [
        param(["a"], True, "repath must be a string or dict"),
        param(
            ["a", "b"],
            "abc",
            "repath must be a dict when there is more than one archive source path",
        ),
    ],
)
def test_archive__raises_when_repath_is_bad_type(
    tmp_path: Path, paths: list, repath: t.Any, expected_error: str
):
    with pytest.raises(TypeError) as exc_info:
        sh.archive(tmp_path / "archive.tar", *paths, repath=repath)
    assert expected_error in str(exc_info.value)


@parametrize(
    "source, expected",
    [
        param(ArchiveSource("a"), f"ArchiveSource(source='a', path='{sh.cwd() / 'a'}')"),
        param(ArchiveSource(Path("a")), f"ArchiveSource(source='a', path='{sh.cwd() / 'a'}')"),
        param(
            ArchiveSource(sh.ls("a")),
            f"ArchiveSource(source=Ls(path='a', recursive=False), path='{sh.cwd() / 'a'}')",
        ),
        param(
            ArchiveSource(Path("a").absolute()),
            f"ArchiveSource(source='{sh.cwd() / 'a'}', path='{sh.cwd() / 'a'}')",
        ),
    ],
)
def test_archive_source__has_repr(source, expected):
    assert repr(source) == expected
