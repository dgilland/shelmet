import fnmatch
from pathlib import Path
import re
import typing as t
from unittest import mock

import pytest
from pytest import param

import shelmet as sh
from shelmet.types import LsFilter

from .utils import FakeDir, FakeFile


parametrize = pytest.mark.parametrize


@parametrize(
    "items, kwargs, expected_contents",
    [
        param(
            [
                FakeDir("x/xx", files=[FakeFile("x1.txt")]),
                FakeDir("y/yy", files=[FakeFile("y1.txt"), FakeFile("y2.txt")]),
                FakeDir("z/zz"),
                FakeFile("a.txt"),
                FakeFile("b.txt"),
                FakeFile("c.txt"),
            ],
            {},
            {Path("x"), Path("y"), Path("z"), Path("a.txt"), Path("b.txt"), Path("c.txt")},
        ),
        param(
            [
                FakeDir("x/xx", files=[FakeFile("x1.txt")]),
                FakeDir("y/yy", files=[FakeFile("y1.txt"), FakeFile("y2.txt")]),
                FakeDir("z/zz"),
                FakeFile("a.txt"),
                FakeFile("b.txt"),
                FakeFile("c.txt"),
            ],
            {"recursive": True},
            {
                Path("x"),
                Path("x/xx"),
                Path("x/xx/x1.txt"),
                Path("y"),
                Path("y/yy"),
                Path("y/yy/y1.txt"),
                Path("y/yy/y2.txt"),
                Path("z"),
                Path("z/zz"),
                Path("a.txt"),
                Path("b.txt"),
                Path("c.txt"),
            },
        ),
        param(
            [
                FakeDir("x/xx", files=[FakeFile("x1.txt")]),
                FakeDir("y/yy", files=[FakeFile("y1.txt"), FakeFile("y2.txt")]),
                FakeDir("z/zz"),
                FakeFile("a.txt"),
                FakeFile("b.txt"),
                FakeFile("c.txt"),
            ],
            {"recursive": True, "only_files": True},
            {
                Path("x/xx/x1.txt"),
                Path("y/yy/y1.txt"),
                Path("y/yy/y2.txt"),
                Path("a.txt"),
                Path("b.txt"),
                Path("c.txt"),
            },
        ),
        param(
            [
                FakeDir("x/xx", files=[FakeFile("x1.txt")]),
                FakeDir("y/yy", files=[FakeFile("y1.txt"), FakeFile("y2.txt")]),
                FakeDir("z/zz"),
                FakeFile("a.txt"),
                FakeFile("b.txt"),
                FakeFile("c.txt"),
            ],
            {"recursive": True, "only_dirs": True},
            {Path("x"), Path("x/xx"), Path("y"), Path("y/yy"), Path("z"), Path("z/zz")},
        ),
        param(
            [
                FakeDir("x/xx", files=[FakeFile("x1.txt")]),
                FakeDir("y/yy", files=[FakeFile("y1.txt"), FakeFile("y2.txt")]),
                FakeDir("z/zz"),
                FakeFile("a.txt"),
                FakeFile("b.txt"),
                FakeFile("c.txt"),
            ],
            {"include": "*.txt"},
            {Path("a.txt"), Path("b.txt"), Path("c.txt")},
        ),
        param(
            [
                FakeDir("x/xx", files=[FakeFile("x1.txt")]),
                FakeDir("y/yy", files=[FakeFile("y1.txt"), FakeFile("y2.txt")]),
                FakeDir("z/zz"),
                FakeFile("a.txt"),
                FakeFile("b.txt"),
                FakeFile("c.txt"),
            ],
            {"exclude": "*.txt"},
            {Path("x"), Path("y"), Path("z")},
        ),
        param(
            [
                FakeDir("x/xx", files=[FakeFile("x1.txt")]),
                FakeDir("y/yy", files=[FakeFile("y1.txt"), FakeFile("y2.txt")]),
                FakeDir("z/zz"),
                FakeFile("a.txt"),
                FakeFile("b.txt"),
                FakeFile("c.txt"),
            ],
            {"include": "*.txt", "recursive": True},
            {
                Path("x/xx/x1.txt"),
                Path("y/yy/y1.txt"),
                Path("y/yy/y2.txt"),
                Path("a.txt"),
                Path("b.txt"),
                Path("c.txt"),
            },
        ),
        param(
            [
                FakeDir("x/xx", files=[FakeFile("x1.txt")]),
                FakeDir("y/yy", files=[FakeFile("y1.txt"), FakeFile("y2.txt")]),
                FakeDir("z/zz"),
                FakeFile("a.txt"),
                FakeFile("b.txt"),
                FakeFile("c.txt"),
            ],
            {"exclude": "*.txt", "recursive": True},
            {
                Path("x"),
                Path("x/xx"),
                Path("y"),
                Path("y/yy"),
                Path("z"),
                Path("z/zz"),
            },
        ),
        param(
            [
                FakeDir("x/xx", files=[FakeFile("x1.txt")]),
                FakeDir("y/yy", files=[FakeFile("y1.txt"), FakeFile("y2.txt")]),
                FakeDir("z/zz"),
                FakeFile("a.txt"),
                FakeFile("b.txt"),
                FakeFile("c.txt"),
            ],
            {"include": ["*.txt"], "only_dirs": True, "recursive": True},
            set(),
        ),
    ],
)
def test_ls(
    tmp_path: Path,
    items: t.List[t.Union[FakeDir, FakeFile]],
    kwargs: dict,
    expected_contents: t.Set[Path],
):
    src = FakeDir(tmp_path)
    src.add_all(items)
    src.mkdir()
    with sh.cd(tmp_path):
        contents = set(sh.ls("", **kwargs))
    assert contents == expected_contents


@parametrize(
    "include",
    [
        param("*_include", id="str"),
        param(["foo", "*_include"], id="str_list"),
        param(re.compile(fnmatch.translate("*_include")), id="regex"),
        param(
            [re.compile(fnmatch.translate("foo")), re.compile(fnmatch.translate("*_include"))],
            id="regex_list",
        ),
        param(lambda p: p.name.endswith("_include"), id="callable"),
        param(
            [lambda p: p.name == "foo", lambda p: p.name.endswith("_include")], id="callable_list"
        ),
    ],
)
def test_ls__includes_on_multiple_types(tmp_path: Path, include: LsFilter):
    items: t.List[t.Union[FakeDir, FakeFile]] = [
        FakeDir("a_dir_include"),
        FakeDir("b_dir"),
        FakeDir("c_dir_include"),
        FakeFile("d_file_include"),
        FakeFile("e_file"),
        FakeFile("f_file_include"),
    ]
    expected_contents = {
        Path("a_dir_include"),
        Path("c_dir_include"),
        Path("d_file_include"),
        Path("f_file_include"),
    }
    src = FakeDir(tmp_path)
    src.add_all(items)
    src.mkdir()
    with sh.cd(tmp_path):
        contents = set(sh.ls("", include=include))
    assert contents == expected_contents


@parametrize(
    "items, kwargs, expected_contents",
    [
        param(
            [
                FakeDir("a_dir_include"),
                FakeDir("b_dir"),
                FakeDir("c_dir_include"),
                FakeFile("d_file_include"),
                FakeFile("e_file"),
                FakeFile("f_file_include"),
            ],
            {"include": "*_include", "only_files": True},
            {Path("d_file_include"), Path("f_file_include")},
        ),
        param(
            [
                FakeDir("a_dir_include"),
                FakeDir("b_dir"),
                FakeDir("c_dir_include"),
                FakeFile("d_file_include"),
                FakeFile("e_file"),
                FakeFile("f_file_include"),
            ],
            {"include": "*_include", "only_dirs": True},
            {Path("a_dir_include"), Path("c_dir_include")},
        ),
    ],
)
def test_ls__uses_only_files_and_only_dirs_in_include(
    tmp_path: Path,
    items: t.List[t.Union[FakeDir, FakeFile]],
    kwargs: dict,
    expected_contents: t.Set[Path],
):
    src = FakeDir(tmp_path)
    src.add_all(items)
    src.mkdir()
    with sh.cd(tmp_path):
        contents = set(sh.ls("", **kwargs))
    assert contents == expected_contents


@parametrize(
    "exclude",
    [
        param("*_exclude", id="str"),
        param(["foo", "*_exclude"], id="str_list"),
        param(re.compile(fnmatch.translate("*_exclude")), id="regex"),
        param(
            [re.compile(fnmatch.translate("foo")), re.compile(fnmatch.translate("*_exclude"))],
            id="regex_list",
        ),
        param(lambda p: p.name.endswith("_exclude"), id="callable"),
        param(
            [lambda p: p.name == "foo", lambda p: p.name.endswith("_exclude")], id="callable_list"
        ),
    ],
)
def test_ls__excludes_on_multiple_types(tmp_path: Path, exclude: LsFilter):
    items: t.List[t.Union[FakeDir, FakeFile]] = [
        FakeDir("a_dir_exclude"),
        FakeDir("b_dir"),
        FakeDir("c_dir_exclude"),
        FakeFile("d_file_exclude"),
        FakeFile("e_file"),
        FakeFile("f_file_exclude"),
    ]
    expected_contents = {Path("b_dir"), Path("e_file")}
    src = FakeDir(tmp_path)
    src.add_all(items)
    src.mkdir()
    with sh.cd(tmp_path):
        contents = set(sh.ls("", exclude=exclude))
    assert contents == expected_contents


def test_ls__does_not_recurse_into_excluded_dirs(tmp_path: Path):
    items: t.List[t.Union[FakeDir, FakeFile]] = [
        FakeDir("a_dir_excluded", files=[FakeFile("a1.txt")]),
        FakeDir("b_dir", files=[FakeFile("b2.txt")]),
    ]
    expected_contents = {
        Path("b_dir"),
        Path("b_dir/b2.txt"),
    }
    exclude = "*_excluded"
    src = FakeDir(tmp_path)
    src.add_all(items)
    src.mkdir()
    with sh.cd(tmp_path):
        contents = set(sh.ls("", exclude=exclude, recursive=True))
    assert contents == expected_contents


def test_ls__raises_when_both_only_files_and_only_dirs_are_true():
    with pytest.raises(ValueError):
        list(sh.ls(only_files=True, only_dirs=True))


def test_ls__raises_when_include_is_invalid_type():
    with pytest.raises(TypeError):
        list(sh.ls(include=True))


@parametrize(
    "fn, expected_kwargs",
    [
        param(sh.lsfiles, {"only_files": True}),
        param(sh.lsdirs, {"only_dirs": True}),
        param(sh.walk, {"recursive": True, "only_files": False, "only_dirs": False}),
        param(sh.walkfiles, {"recursive": True, "only_files": True, "only_dirs": False}),
        param(sh.walkdirs, {"recursive": True, "only_dirs": True, "only_files": False}),
    ],
)
def test_ls_aliases(tmp_path: Path, fn: t.Callable, expected_kwargs: dict):
    expected_kwargs["include"] = None
    expected_kwargs["exclude"] = None

    with mock.patch.object(sh.path, "ls") as mocked_ls:
        list(fn(tmp_path))

    assert mocked_ls.called
    assert mocked_ls.call_args[1] == expected_kwargs
