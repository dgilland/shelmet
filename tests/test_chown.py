import grp
import os
from pathlib import Path
import pwd
import typing as t
from unittest import mock
from uuid import uuid4

import pytest

import shelmet as sh

from .utils import Dir, File


parametrize = pytest.mark.parametrize


@pytest.fixture()
def os_user() -> pwd.struct_passwd:
    return pwd.getpwuid(os.getuid())


@pytest.fixture()
def os_group() -> grp.struct_group:
    return grp.getgrgid(os.getgid())


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


@pytest.fixture()
def mock_os_chown() -> t.Generator[mock.MagicMock, None, None]:
    with mock.patch("os.chown") as mocked_os_chown:
        yield mocked_os_chown


def chown_call(
    path: t.Union[str, Path, int], user: int = -1, group: int = -1, follow_symlinks: bool = True
) -> tuple:
    if isinstance(path, str):
        path = Path(path)
    return mock.call(path, user, group, follow_symlinks=follow_symlinks)


def test_chown__changes_ownership_given_uid(tmp_path: Path, mock_os_chown: mock.MagicMock):
    sh.chown(tmp_path, user=1)
    assert mock_os_chown.call_args == chown_call(tmp_path, user=1)


def test_chown__changes_ownership_given_gid(tmp_path: Path, mock_os_chown: mock.MagicMock):
    sh.chown(tmp_path, group=1)
    assert mock_os_chown.call_args == chown_call(tmp_path, group=1)


def test_chown__changes_ownership_given_user_name(
    tmp_path: Path, mock_os_chown: mock.MagicMock, os_user: pwd.struct_passwd
):
    sh.chown(tmp_path, user=os_user.pw_name)
    assert mock_os_chown.call_args == chown_call(tmp_path, user=os_user.pw_uid)


def test_chown__changes_ownership_given_group_name(
    tmp_path: Path, mock_os_chown: mock.MagicMock, os_group: grp.struct_group
):
    sh.chown(tmp_path, group=os_group.gr_name)
    assert mock_os_chown.call_args == chown_call(tmp_path, group=os_group.gr_gid)


def test_chown__changes_ownership_given_file_descriptor(mock_os_chown: mock.MagicMock):
    sh.chown(1, user=2, group=3)
    assert mock_os_chown.call_args == chown_call(1, user=2, group=3)


def test_chown__changes_ownership_without_following_symlinks(
    tmp_path: Path, mock_os_chown: mock.MagicMock
):
    sh.chown(tmp_path, user=1, group=2, follow_symlinks=False)
    assert mock_os_chown.call_args == chown_call(tmp_path, user=1, group=2, follow_symlinks=False)


def test_chown__changes_ownership_recursively(tmp_path: Path, mock_os_chown: mock.MagicMock):
    test_dir = Dir(
        tmp_path,
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
    )
    test_dir.mkdir()

    sh.chown(test_dir.path, user=1, group=2, recursive=True)

    for path in (test_dir.path, *sh.walk(test_dir.path)):
        assert chown_call(path, user=1, group=2) in mock_os_chown.call_args_list


def test_chown__raises_when_missing_user_and_group():
    with pytest.raises(ValueError):
        sh.chown("path")


def test_chown__raises_when_user_name_invalid():
    with pytest.raises(LookupError):
        sh.chown("path", user=uuid4().hex)


def test_chown__raises_when_group_name_invalid():
    with pytest.raises(LookupError):
        sh.chown("path", group=uuid4().hex)
