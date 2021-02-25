from pathlib import Path
import typing as t

import pytest
from pytest import param

import shelmet as sh

from .utils import FakeDir, FakeFile


parametrize = pytest.mark.parametrize


@parametrize(
    "files, pattern, expected_size",
    [
        param([FakeFile("a", size=10)], None, 10),
        param(
            [
                FakeFile("a", size=10),
                FakeFile("b/1", size=5),
                FakeFile("b/2", size=5),
                FakeFile("b/3", size=3),
                FakeFile("b/4", size=2),
                FakeFile("b/c/5", size=100),
                FakeFile("d", size=50),
            ],
            None,
            175,
        ),
        param(
            [
                FakeFile("a.json", size=123),
                FakeFile("b.txt", size=17),
                FakeFile("c.json", size=38),
                FakeFile("d", size=173),
            ],
            "*.json",
            161,
        ),
        param(
            [
                FakeFile("1/a.py", size=123),
                FakeFile("1/2/b.py", size=17),
                FakeFile("1/2/3/c.py", size=38),
                FakeFile("d.py", size=173),
                FakeFile("foo.txt", size=12),
                FakeFile("1/bar.txt", size=293),
                FakeFile("1/2/baz.txt", size=314),
                FakeFile("1/2/3/qux.txt", size=83),
            ],
            "**/*.py",
            351,
        ),
    ],
)
def test_getdirsize(
    tmp_path: Path, files: t.List[FakeFile], pattern: t.Optional[str], expected_size: int
):
    FakeDir(tmp_path).mkdir(files=files)
    kwargs = {}
    if pattern:
        kwargs["pattern"] = pattern
    assert sh.getdirsize(tmp_path, **kwargs) == expected_size
