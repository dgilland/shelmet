from pathlib import Path
import typing as t

import pytest
from pytest import param

import shelmet as sh


parametrize = pytest.mark.parametrize


@parametrize(
    "paths",
    [
        param(["a"]),
        param(["a", "b", "c/d/e"]),
    ],
)
def test_touch(tmp_path: Path, paths: t.List[str]):
    targets = [tmp_path / path for path in paths]
    sh.touch(*targets)
    for path in targets:
        assert path.is_file()
