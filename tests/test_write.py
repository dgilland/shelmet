from pathlib import Path
import typing as t
from unittest import mock

import pytest
from pytest import param

import shelmet as sh


parametrize = pytest.mark.parametrize


@pytest.fixture(
    params=[
        param("w"),
        param("wt"),
        param("tw"),
        param("a"),
        param("at"),
        param("ta"),
        param("x"),
        param("xt"),
        param("tx"),
        param("wb"),
        param("bw"),
        param("ab"),
        param("ba"),
        param("xb"),
        param("bx"),
    ]
)
def valid_write_only_mode(request) -> str:
    return request.param


@pytest.fixture(
    params=[
        param("wb"),
        param("bw"),
        param("ab"),
        param("ba"),
        param("xb"),
        param("bx"),
    ]
)
def valid_write_only_bin_mode(request) -> str:
    return request.param


@pytest.fixture(
    params=[
        param("w"),
        param("wt"),
        param("tw"),
        param("a"),
        param("at"),
        param("ta"),
        param("x"),
        param("xt"),
        param("tx"),
    ]
)
def valid_write_only_text_mode(request) -> str:
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
    ]
)
def invalid_write_only_mode(request) -> str:
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
def invalid_write_only_bin_mode(request) -> str:
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
def invalid_write_only_text_mode(request) -> str:
    return request.param


@pytest.fixture()
def mock_atomicfile():
    with mock.patch("shelmet.filesystem.atomicfile") as _mock_atomicfile:
        yield _mock_atomicfile


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


def test_write__accepts_valid_mode(tmp_path: Path, valid_write_only_mode: str):
    contents: t.Union[str, bytes] = b"" if "b" in valid_write_only_mode else ""
    sh.write(tmp_path / "test_file", contents, valid_write_only_mode)


@parametrize(
    "mode, contents, expected_mode, expected_overwrite",
    [
        param("w", "test", "w", True),
        param("wb", b"test", "wb", True),
        param("x", "test", "w", False),
        param("xb", b"test", "wb", False),
    ],
)
def test_write__can_atomically_create_file(
    tmp_path: Path,
    mock_atomicfile: mock.MagicMock,
    mode: str,
    contents: t.Union[str, bytes],
    expected_mode: str,
    expected_overwrite: bool,
):
    file = tmp_path / "test_file"
    sh.write(file, contents, mode, atomic=True)

    assert mock_atomicfile.called
    assert mock_atomicfile.call_args == mock.call(file, expected_mode, overwrite=expected_overwrite)

    args, kwargs = mock_atomicfile.call_args
    with mock_atomicfile(*args, **kwargs) as fp:
        assert fp.write.called
        assert fp.write.call_args == mock.call(contents)


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


def test_writebytes__accepts_valid_mode(tmp_path: Path, valid_write_only_bin_mode: str):
    sh.write(tmp_path / "test_file", b"", valid_write_only_bin_mode)


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


def test_writetext__accepts_valid_mode(tmp_path: Path, valid_write_only_text_mode: str):
    sh.write(tmp_path / "test_file", "", valid_write_only_text_mode)


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


def test_writelines__accepts_valid_mode(tmp_path: Path, valid_write_only_mode: str):
    contents: t.Union[str, bytes] = b"" if "b" in valid_write_only_mode else ""
    sh.writelines(tmp_path / "test_file", [contents], valid_write_only_mode)  # type: ignore


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


@parametrize(
    "mode, items, expected_mode, expected_overwrite",
    [
        param("w", ["test"], "w", True),
        param("wb", [b"test"], "wb", True),
        param("x", ["test"], "w", False),
        param("xb", [b"test"], "wb", False),
    ],
)
def test_writelines__can_atomically_create_file(
    tmp_path: Path,
    mock_atomicfile: mock.MagicMock,
    mode: str,
    items: t.Union[t.List[str], t.List[bytes]],
    expected_mode: str,
    expected_overwrite: bool,
):
    file = tmp_path / "test_file"
    sh.writelines(file, items, mode, atomic=True)

    assert mock_atomicfile.called
    assert mock_atomicfile.call_args == mock.call(file, expected_mode, overwrite=expected_overwrite)

    args, kwargs = mock_atomicfile.call_args
    with mock_atomicfile(*args, **kwargs) as fp:
        assert fp.writelines.called
        lines = [line.strip() for line in fp.writelines.call_args[0][0]]
        assert items == lines


def test_writelines__raises_when_mode_invalid(tmp_path: Path, invalid_write_only_mode: str):
    file = tmp_path / "test_file"
    with pytest.raises(ValueError):
        sh.writelines(file, [], invalid_write_only_mode)
