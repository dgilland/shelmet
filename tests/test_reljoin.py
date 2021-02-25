from pathlib import Path
import typing as t

import pytest
from pytest import param

import shelmet as sh


parametrize = pytest.mark.parametrize


@parametrize(
    "paths, expected",
    [
        param(["a"], "a"),
        param(["a/"], "a"),
        param(["a", "b", "c/d"], "a/b/c/d"),
        param(["a", "/b", "/c/d"], "a/b/c/d"),
        param(["/a", "b", "c/d"], "/a/b/c/d"),
        param(["/a/", "/b/", "/c/d/"], "/a/b/c/d"),
        param([Path("a")], "a"),
        param([Path("a/")], "a"),
        param([Path("a"), Path("b"), Path("c/d")], "a/b/c/d"),
        param([Path("a"), Path("/b"), Path("/c/d")], "a/b/c/d"),
        param([Path("/a"), Path("b"), Path("c/d")], "/a/b/c/d"),
        param(["a", Path("b"), "c/d"], "a/b/c/d"),
        param([Path("a"), "b", Path("c/d")], "a/b/c/d"),
    ],
)
def test_reljoin(paths: t.Sequence[t.Union[Path, str]], expected: str):
    assert sh.reljoin(*paths) == expected
