from pathlib import Path
import stat
import typing as t

import pytest
from pytest import param

import shelmet as sh

from .utils import Dir, File


parametrize = pytest.mark.parametrize


@pytest.fixture()
def test_file(tmp_path: Path) -> Path:
    test_file = tmp_path / "test_file.txt"
    test_file.touch()
    return test_file


@pytest.fixture()
def test_dir(tmp_path: Path) -> Path:
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()
    return test_dir


@parametrize(
    "starting_mode, desired_mode, expected_mode",
    [
        param(None, 0o777, "-rwxrwxrwx"),
        param(None, 0o666, "-rw-rw-rw-"),
        param(None, "777", "-rwxrwxrwx"),
        param(None, "666", "-rw-rw-rw-"),
        param(None, "+rwx", "-rwxrwxrwx"),
        param(None, "u+rw,go-rwx", "-rw-------"),
        param(None, "=rw", "-rw-rw-rw-"),
        param(None, "a=rw", "-rw-rw-rw-"),
        param(None, "ug=rw,o=r", "-rw-rw-r--"),
        param(None, "u=rwx,g=rw,o=r", "-rwxrw-r--"),
        param(None, "=rw,o+t", "-rw-rw-rwT"),
        param(None, "=rw,a+t", "-rw-rw-rwT"),
        param(None, "=rw,+t", "-rw-rw-rwT"),
        param(None, "=rw,+x,o+t", "-rwxrwxrwt"),
        param(None, "=rw,+x,a+t", "-rwxrwxrwt"),
        param(None, "=rw,+x,+t", "-rwxrwxrwt"),
        param(None, "+rw,u+s", "-rwSrw-rw-"),
        param(None, "+rw,u+x,u+s", "-rwsrw-rw-"),
        param(None, "+rw,g+s", "-rw-rwSrw-"),
        param(None, "+rw,g+x,g+s", "-rw-rwsrw-"),
        param(0o777, "u=rwx,g=rw,o=r", "-rwxrw-r--"),
        param(0, "u=rwx,g=rw,o=r", "-rwxrw-r--"),
        param(0o600, "g=u", "-rw-rw----"),
        param(0o740, "g+u", "-rwxrwx---"),
        param(0o700, "o=u", "-rwx---rwx"),
        param(0o604, "o+u", "-rw----rw-"),
        param(0o060, "u=g", "-rw-rw----"),
        param(0o470, "u+g", "-rwxrwx---"),
        param(0o070, "o=g", "----rwxrwx"),
        param(0o064, "o+g", "----rw-rw-"),
        param(0o006, "u=o", "-rw----rw-"),
        param(0o407, "u+o", "-rwx---rwx"),
        param(0o007, "g=o", "----rwxrwx"),
        param(0o046, "g+o", "----rw-rw-"),
        param(0o600, "go=u", "-rw-rw-rw-"),
        param(0o060, "uo=g", "-rw-rw-rw-"),
        param(0o006, "ug=o", "-rw-rw-rw-"),
        param(0o600, "a=u", "-rw-rw-rw-"),
        param(0o060, "a=g", "-rw-rw-rw-"),
        param(0o006, "a=o", "-rw-rw-rw-"),
        param(0o777, "o=", "-rwxrwx---"),
    ],
)
def test_chmod__sets_file_mode(
    test_file: Path,
    starting_mode: t.Optional[int],
    desired_mode: t.Union[int, str],
    expected_mode: str,
):
    if starting_mode is not None:
        test_file.chmod(starting_mode)

    sh.chmod(test_file, desired_mode)

    filemode = stat.filemode(test_file.stat().st_mode)
    assert filemode == expected_mode


def test_chmod__sets_dir_mode(test_dir: Path):
    sh.chmod(test_dir, "+rw")

    filemode = stat.filemode(test_dir.stat().st_mode)
    assert filemode == "drwxrwxrwx"


def test_chmod__accepts_fileno(test_file: Path):
    with test_file.open() as fp:
        fd = fp.fileno()
        sh.chmod(fd, "+rwx")

    filemode = stat.filemode(test_file.stat().st_mode)
    assert filemode == "-rwxrwxrwx"


@parametrize(
    "items, mode, expected_file_mode, expected_dir_mode",
    [
        param(
            [
                Dir("a", File("1.txt"), File("2.txt"), File("3.txt")),
                Dir(
                    "b",
                    Dir("c", File("4.txt"), Dir("d", File("5.txt"))),
                    File("6.txt"),
                    File("7.txt"),
                    File("8.txt"),
                ),
                File("9.txt"),
                File("10.txt"),
            ],
            "766",
            "-rwxrw-rw-",
            "drwxrw-rw-",
        ),
        param(
            [
                Dir("a", File("1.txt"), File("2.txt"), File("3.txt")),
                Dir(
                    "b",
                    Dir("c", File("4.txt"), Dir("d", File("5.txt"))),
                    File("6.txt"),
                    File("7.txt"),
                    File("8.txt"),
                ),
                File("9.txt"),
                File("10.txt"),
            ],
            "go-rwx",
            "-rw-------",
            "drwx------",
        ),
    ],
)
def test_chmod__recursively_sets_mode(
    tmp_path: Path,
    items: t.List[t.Union[Dir, File]],
    mode: t.Union[int, str],
    expected_file_mode: int,
    expected_dir_mode: int,
):
    test_dir = Dir(tmp_path / "test_dir", *items)
    test_dir.mkdir()

    sh.chmod(test_dir.path, mode, recursive=True)

    for path in (test_dir.path, *sh.walk(test_dir.path)):
        expected_mode = expected_dir_mode if path.is_dir() else expected_file_mode
        path_mode = stat.filemode(path.stat().st_mode)

        assert (
            path_mode == expected_mode
        ), f"Expected mode of {path} to be {expected_mode!r}, not {path_mode!r}"


@parametrize(
    "mode, exception",
    [
        param(None, TypeError),
        param("", ValueError),
        param("u=Z", ValueError),
        param("u=rwxg", ValueError),
        param("rw", ValueError),
        param("u=t", ValueError),
    ],
)
def test_chmod__raises_when_mode_invalid(
    test_file: Path, mode: t.Any, exception: t.Type[Exception]
):
    with pytest.raises(exception):
        sh.chmod(test_file, mode)
