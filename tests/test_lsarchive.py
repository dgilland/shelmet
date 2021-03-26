from pathlib import Path
import typing as t

import pytest
from pytest import param

import shelmet as sh

from .utils import ARCHIVE_EXTENSIONS, Dir, File, create_archive, create_archive_source


parametrize = pytest.mark.parametrize


@pytest.fixture(params=ARCHIVE_EXTENSIONS)
def arc_ext(request) -> str:
    """Fixture that yields all archive extensions."""
    return request.param


@parametrize(
    "source, expected",
    [
        param(
            Dir(
                "a",
                Dir("b"),
                Dir("c", File("c1", text="c1"), File("c2", text="c2")),
                Dir("d", Dir("e", Dir("f", File("f1", text="f1")), File("e1", text="e1"))),
                File("a1", text="a1"),
                File("a2", text="a2"),
            ),
            {
                Path("a"),
                Path("a/b"),
                Path("a/c"),
                Path("a/c/c1"),
                Path("a/c/c2"),
                Path("a/d"),
                Path("a/d/e"),
                Path("a/d/e/f"),
                Path("a/d/e/f/f1"),
                Path("a/d/e/e1"),
                Path("a/a1"),
                Path("a/a2"),
            },
        )
    ],
)
def test_lsarchive__returns_list_of_archive_members(
    tmp_path: Path, arc_ext: str, source: Dir, expected: t.Set[Path]
):
    archive_file = tmp_path / f"archive{arc_ext}"
    src_dir = create_archive_source(tmp_path, source)
    create_archive(archive_file, src_dir.items[0].path)

    listing = sh.lsarchive(archive_file)
    assert set(listing) == expected


@parametrize(
    "source, expected",
    [
        param(
            Dir(
                "a",
                Dir("b"),
                Dir("c", File("c1", text="c1"), File("c2", text="c2")),
                Dir("d", Dir("e", Dir("f", File("f1", text="f1")), File("e1", text="e1"))),
                File("a1", text="a1"),
                File("a2", text="a2"),
            ),
            {
                Path("a"),
                Path("a/b"),
                Path("a/c"),
                Path("a/c/c1"),
                Path("a/c/c2"),
                Path("a/d"),
                Path("a/d/e"),
                Path("a/d/e/f"),
                Path("a/d/e/f/f1"),
                Path("a/d/e/e1"),
                Path("a/a1"),
                Path("a/a2"),
            },
        )
    ],
)
def test_lsarchive__returns_list_of_archive_members_with_explicit_extension_format(
    tmp_path: Path, arc_ext: str, source: Dir, expected: t.Set[Path]
):
    archive_file = tmp_path / "archive"
    src_dir = create_archive_source(tmp_path, source)
    create_archive(archive_file, src_dir.items[0].path, ext=arc_ext)

    listing = sh.lsarchive(archive_file, ext=arc_ext)
    assert set(listing) == expected
