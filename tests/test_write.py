from pathlib import Path
import typing as t

import pytest
from pytest import param

import shelmet as sh


parametrize = pytest.mark.parametrize


@pytest.fixture(
    params=[
        param("r"),
        param("r+"),
        param("rb"),
        param("rb+"),
        param("w+"),
        param("wb+"),
        param("a+"),
        param("ab+"),
    ]
)
def invalid_write_only_mode(request):
    return request.param


@pytest.fixture(
    params=[
        param("r"),
        param("r+"),
        param("rb"),
        param("rb+"),
        param("w+"),
        param("wb+"),
        param("a+"),
        param("ab+"),
        param("w"),
        param("wt"),
        param("a"),
        param("x"),
    ]
)
def invalid_write_only_bin_mode(request):
    return request.param


@pytest.fixture(
    params=[
        param("r"),
        param("r+"),
        param("rb"),
        param("rb+"),
        param("w+"),
        param("wb+"),
        param("a+"),
        param("ab+"),
        param("wb"),
        param("ab"),
        param("xb"),
    ]
)
def invalid_write_only_text_mode(request):
    return request.param


@parametrize(
    "mode, contents",
    [
        param("w", "abcd"),
        param("a", "abcd"),
        param("x", "abcd"),
        param("wb", b"abcd"),
        param("ab", b"abcd"),
        param("xb", b"abcd"),
    ],
)
def test_write(tmp_path: Path, mode: str, contents: t.Union[str, bytes]):
    file = tmp_path / "test_file"
    sh.write(file, contents, mode)

    actual_contents = file.read_bytes()
    if isinstance(contents, str):
        actual_contents = actual_contents.decode()  # type: ignore

    assert contents == actual_contents


def test_write__raises_when_mode_invalid(tmp_path: Path, invalid_write_only_mode: str):
    file = tmp_path / "test_file"
    with pytest.raises(ValueError):
        sh.write(file, "", invalid_write_only_mode)


@parametrize(
    "mode, contents",
    [
        param("wb", b"abcd"),
        param("ab", b"abcd"),
        param("xb", b"abcd"),
    ],
)
def test_writebytes(tmp_path: Path, mode: str, contents: bytes):
    file = tmp_path / "test_file"
    sh.writebytes(file, contents, mode)

    actual_contents = file.read_bytes()
    assert contents == actual_contents


def test_writebytes__raises_when_mode_invalid(tmp_path: Path, invalid_write_only_bin_mode: str):
    file = tmp_path / "test_file"
    with pytest.raises(ValueError):
        sh.writebytes(file, b"", invalid_write_only_bin_mode)


@parametrize(
    "mode, contents",
    [
        param("w", "abcd"),
        param("a", "abcd"),
        param("x", "abcd"),
    ],
)
def test_writetext(tmp_path: Path, mode: str, contents: str):
    file = tmp_path / "test_file"
    sh.writetext(file, contents, mode)

    actual_contents = file.read_text()
    assert contents == actual_contents


def test_writetext__raises_when_mode_invalid(tmp_path: Path, invalid_write_only_text_mode: str):
    file = tmp_path / "test_file"
    with pytest.raises(ValueError):
        sh.writetext(file, "", invalid_write_only_text_mode)


@parametrize(
    "mode, items",
    [
        param("w", ["a", "b", "c"]),
        param("a", ["a", "b", "c"]),
        param("x", ["a", "b", "c"]),
        param("w", ["a", "b", "c"]),
        param("a", ["a", "b", "c"]),
        param("x", ["a", "b", "c"]),
        param("wb", [b"a", b"b", b"c"]),
        param("ab", [b"a", b"b", b"c"]),
        param("xb", [b"a", b"b", b"c"]),
        param("wb", [b"a", b"b", b"c"]),
        param("ab", [b"a", b"b", b"c"]),
        param("xb", [b"a", b"b", b"c"]),
    ],
)
def test_writelines(tmp_path: Path, mode: str, items: t.List[t.AnyStr]):
    file = tmp_path / "test_file"
    sh.writelines(file, items, mode)

    read_mode = "r"
    if "b" in mode:
        read_mode += "b"

    with open(file, read_mode) as fp:
        lines = fp.readlines()

    for i, line in enumerate(lines):
        assert items[i] == line.strip()


@parametrize(
    "mode, items, ending",
    [
        param("w", ["a", "b", "c"], "|"),
        param("a", ["a", "b", "c"], "|"),
        param("x", ["a", "b", "c"], "|"),
        param("w", ["a", "b", "c"], "|"),
        param("a", ["a", "b", "c"], "|"),
        param("x", ["a", "b", "c"], "|"),
        param("wb", [b"a", b"b", b"c"], b"|"),
        param("ab", [b"a", b"b", b"c"], b"|"),
        param("xb", [b"a", b"b", b"c"], b"|"),
        param("wb", [b"a", b"b", b"c"], b"|"),
        param("ab", [b"a", b"b", b"c"], b"|"),
        param("xb", [b"a", b"b", b"c"], b"|"),
    ],
)
def test_writelines__uses_custom_ending(
    tmp_path: Path, mode: str, items: t.List[t.AnyStr], ending: t.AnyStr
):
    file = tmp_path / "test_file"
    sh.writelines(file, items, mode, ending=ending)

    read_mode = "r"
    if "b" in mode:
        read_mode += "b"

    with open(file, read_mode) as fp:
        contents = fp.read()

    actual_items = contents.rstrip(ending).split(ending)
    for i, actual_item in enumerate(actual_items):
        assert items[i] == actual_item


def test_writelines__raises_when_mode_invalid(tmp_path: Path, invalid_write_only_mode: str):
    file = tmp_path / "test_file"
    with pytest.raises(ValueError):
        sh.writelines(file, [], invalid_write_only_mode)
