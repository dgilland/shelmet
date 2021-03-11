from pathlib import Path
import typing as t

import pytest
from pytest import param

import shelmet as sh

from .utils import Dir, File


parametrize = pytest.mark.parametrize


@parametrize(
    "files, pattern, expected_size",
    [
        param([File("a", size=10)], None, 10),
        param(
            [
                File("a", size=10),
                File("b/1", size=5),
                File("b/2", size=5),
                File("b/3", size=3),
                File("b/4", size=2),
                File("b/c/5", size=100),
                File("d", size=50),
            ],
            None,
            175,
        ),
        param(
            [
                File("a.json", size=123),
                File("b.txt", size=17),
                File("c.json", size=38),
                File("d", size=173),
            ],
            "*.json",
            161,
        ),
        param(
            [
                File("1/a.py", size=123),
                File("1/2/b.py", size=17),
                File("1/2/3/c.py", size=38),
                File("d.py", size=173),
                File("foo.txt", size=12),
                File("1/bar.txt", size=293),
                File("1/2/baz.txt", size=314),
                File("1/2/3/qux.txt", size=83),
            ],
            "**/*.py",
            351,
        ),
    ],
)
def test_getdirsize(
    tmp_path: Path, files: t.List[File], pattern: t.Optional[str], expected_size: int
):
    Dir(tmp_path, *files).mkdir()
    kwargs = {}
    if pattern:
        kwargs["pattern"] = pattern
    assert sh.getdirsize(tmp_path, **kwargs) == expected_size
