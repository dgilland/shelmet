import os
from pathlib import Path

import pytest
from pytest import param

import shelmet as sh


parametrize = pytest.mark.parametrize


@parametrize(
    "path",
    [
        param(""),
        param("a"),
        param("a/b"),
        param("a/b/c"),
    ],
)
def test_cd__changes_cwd(tmp_path: Path, path: str):
    orig_cwd = os.getcwd()
    cd_path = tmp_path / path
    cd_path.mkdir(parents=True, exist_ok=True)

    with sh.cd(cd_path):
        assert os.getcwd() == str(cd_path)
    assert os.getcwd() == orig_cwd
