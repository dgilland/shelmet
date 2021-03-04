import os
from pathlib import Path
import typing as t
from uuid import uuid4

import pytest
from pytest import param

import shelmet as sh


parametrize = pytest.mark.parametrize


def lines_as_text(items: t.Iterable) -> t.List[str]:
    lines = os.linesep.join(str(item) for item in items)
    return lines.splitlines(keepends=True)


def lines_as_bytes(items: t.Iterable) -> t.List[bytes]:
    lines = os.linesep.join(str(item) for item in items).encode()
    return lines.splitlines(keepends=True)


def repeat_items(items: t.List[str], times: int) -> t.List[str]:
    return [item * times for item in items]


@pytest.fixture()
def write_text(tmp_path: Path) -> t.Callable[[str], Path]:
    def _write_text(content: str) -> Path:
        filename = tmp_path / uuid4().hex
        filename.write_text(content)
        return filename

    return _write_text


@pytest.fixture()
def write_bytes(tmp_path: Path) -> t.Callable[[bytes], Path]:
    def _write_bytes(content: bytes) -> Path:
        filename = tmp_path / uuid4().hex
        filename.write_bytes(content)
        return filename

    return _write_bytes


@pytest.fixture(
    params=[
        param("r"),
        param("rt"),
        param("tr"),
        param("rb"),
        param("br"),
    ]
)
def valid_read_only_mode(request):
    return request.param


@pytest.fixture(
    params=[
        param("r+"),
        param("rb+"),
        param("w"),
        param("w+"),
        param("wb"),
        param("wb+"),
        param("x"),
        param("a"),
        param("a+"),
    ]
)
def invalid_read_only_mode(request):
    return request.param


def test_read__returns_text_file_contents(write_text: t.Callable[[str], Path]):
    content = "some text"
    test_file = write_text(content)
    assert sh.read(test_file) == content


def test_read__returns_binary_file_contents(write_bytes: t.Callable[[bytes], Path]):
    content = b"some data"
    test_file = write_bytes(content)
    assert sh.read(test_file, "rb") == content


def test_read__accepts_valid_mode(tmp_path: Path, valid_read_only_mode):
    test_file = tmp_path / "test_file"
    test_file.touch()
    sh.read(test_file, valid_read_only_mode)


def test_read__raises_when_mode_invalid(
    write_text: t.Callable[[str], Path], invalid_read_only_mode: str
):
    test_file = write_text("test")
    with pytest.raises(ValueError):
        sh.read(test_file, invalid_read_only_mode)


def test_readtext__returns_text_file_contents(write_text: t.Callable[[str], Path]):
    content = "some text"
    test_file = write_text(content)
    assert sh.readtext(test_file) == content


def test_readbytes__returns_binary_file_contents(write_bytes: t.Callable[[bytes], Path]):
    content = b"some data"
    test_file = write_bytes(content)
    assert sh.readbytes(test_file) == content


@parametrize(
    "chunks, size, sep",
    [
        param(repeat_items(["1", "2", "3", "4"], 1), 1, None),
        param(repeat_items(["1", "2", "3", "4"], 2), 2, None),
        param(repeat_items(["1", "2", "3", "4"], 50), 50, None),
        param(repeat_items(["1", "2", "3", "4"], 1), 1, "|"),
        param(repeat_items(["1", "2", "3", "4"], 1), 4, "|"),
        param(repeat_items(["1", "2", "3", "4"], 2), 1, "|"),
        param(repeat_items(["1", "2", "3", "4"], 2), 2, "|"),
        param(repeat_items(["1", "2", "3", "4"], 2), 4, "|"),
        param(repeat_items(["1", "2", "3", "4"], 50), 1, "|"),
        param(repeat_items(["1", "2", "3", "4"], 50), 5, "|"),
        param(repeat_items(["1", "2", "3", "4"], 50), 25, "|"),
        param(repeat_items(["1", "2", "3", "4"], 50), 1, ";|&"),
        param(repeat_items(["1", "2", "3", "4"], 50), 25, ";|&"),
        param(repeat_items(["1", "2", "3", "4"], 50), 50, ";|&"),
        param(repeat_items(["1", "2", "3", "4"], 50), 100, ";|&"),
    ],
)
def test_readchunks__yields_text_chunks_by_size(
    write_text: t.Callable[[str], Path], chunks: list, size: int, sep: str
):
    content = (sep or "").join(chunks)
    test_file = write_text(content)

    for i, chunk in enumerate(sh.readchunks(test_file, size=size, sep=sep)):
        assert chunk == chunks[i]


@parametrize(
    "chunks, size, sep",
    [
        param(repeat_items(["1", "2", "3", "4"], 1), 1, None),
        param(repeat_items(["1", "2", "3", "4"], 2), 2, None),
        param(repeat_items(["1", "2", "3", "4"], 50), 50, None),
        param(repeat_items(["1", "2", "3", "4"], 1), 1, "|"),
        param(repeat_items(["1", "2", "3", "4"], 1), 4, "|"),
        param(repeat_items(["1", "2", "3", "4"], 2), 1, "|"),
        param(repeat_items(["1", "2", "3", "4"], 2), 2, "|"),
        param(repeat_items(["1", "2", "3", "4"], 2), 4, "|"),
        param(repeat_items(["1", "2", "3", "4"], 50), 1, "|"),
        param(repeat_items(["1", "2", "3", "4"], 50), 5, "|"),
        param(repeat_items(["1", "2", "3", "4"], 50), 25, "|"),
        param(repeat_items(["1", "2", "3", "4"], 50), 1, ";|&"),
        param(repeat_items(["1", "2", "3", "4"], 50), 25, ";|&"),
        param(repeat_items(["1", "2", "3", "4"], 50), 50, ";|&"),
        param(repeat_items(["1", "2", "3", "4"], 50), 100, ";|&"),
    ],
)
def test_readchunks__yields_binary_chunks_by_size(
    write_bytes: t.Callable[[bytes], Path], chunks: list, size: int, sep: str
):
    content = (sep or "").join(chunks)
    test_file = write_bytes(content.encode())
    bin_sep: t.Optional[bytes] = sep.encode() if sep else None

    for i, chunk in enumerate(sh.readchunks(test_file, "rb", size=size, sep=bin_sep)):
        assert chunk.decode() == chunks[i]


def test_readchunks__raises_when_mode_invalid(
    write_text: t.Callable[[str], Path], invalid_read_only_mode: str
):
    test_file = write_text("test")
    with pytest.raises(ValueError):
        sh.readchunks(test_file, invalid_read_only_mode)


def test_readlines__yields_each_line_from_text_file(write_text: t.Callable[[str], Path]):
    lines = lines_as_text(range(10))
    test_file = write_text("".join(lines))

    for i, line in enumerate(sh.readlines(test_file)):
        assert line == lines[i]


def test_readlines__yields_each_line_from_binary_file(write_bytes: t.Callable[[bytes], Path]):
    lines = lines_as_bytes(range(10))
    test_file = write_bytes(b"".join(lines))

    for i, line in enumerate(sh.readlines(test_file, "rb")):
        assert line == lines[i]


def test_readlines__raises_when_mode_invalid(
    write_text: t.Callable[[str], Path], invalid_read_only_mode: str
):
    test_file = write_text("test")
    with pytest.raises(ValueError):
        sh.readlines(test_file, invalid_read_only_mode)
