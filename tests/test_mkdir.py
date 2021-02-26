from pathlib import Path
import typing as t

import pytest
from pytest import param

import shelmet as sh


parametrize = pytest.mark.parametrize


@parametrize(
    "paths,",
    [
        param(["a"]),
        param(["a", "a/b", "a/b/c", "d/e/f/g/h"]),
        param([Path("a")]),
        param([Path("a"), Path("a/b"), Path("a/b/c"), Path("d/e/f/g/h")]),
    ],
)
def test_mkdir(tmp_path: Path, paths: t.List[t.Union[str, Path]]):
    targets = [tmp_path / path for path in paths]
    sh.mkdir(*targets)

    for target in targets:
        assert target.is_dir()


def test_mkdir__sets_mode(tmp_path: Path):
    targets = [tmp_path / "test1", tmp_path / "test2", tmp_path / "1" / "2" / "3"]
    mode = 0o755

    sh.mkdir(*targets, mode=mode)
    for target in targets:
        target_mode = oct(target.stat().st_mode & 0o777)
        assert target_mode == oct(mode)


def test_mkdir__raises_if_exist_not_ok(tmp_path: Path):
    with pytest.raises(FileExistsError):
        sh.mkdir(tmp_path, exist_ok=False)
