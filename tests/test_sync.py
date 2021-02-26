from pathlib import Path
from unittest import mock

import pytest
from pytest import param

import shelmet as sh

from .utils import patch_os_fsync


parametrize = pytest.mark.parametrize


def test_dirsync(tmp_path: Path):
    path = tmp_path / "test"
    path.mkdir()

    with patch_os_fsync() as mocked_os_fsync:
        sh.dirsync(path)

    assert mocked_os_fsync.called


def test_fsync__syncs_on_file_object(tmp_path: Path):
    file = tmp_path / "test.txt"

    with file.open("w") as fp:
        fp.write("test")
        fileno = fp.fileno()
        with mock.patch.object(fp, "flush") as mock_flush, patch_os_fsync() as mock_os_fsync:
            sh.fsync(fp)

    assert mock_flush.called
    assert mock_os_fsync.called
    assert mock_os_fsync.call_args[0][0] == fileno


def test_fsync__syncs_on_fileno(tmp_path: Path):
    file = tmp_path / "test.txt"
    file.write_text("test")

    with file.open() as fp:
        fileno = fp.fileno()
        with patch_os_fsync() as mock_os_fsync:
            sh.fsync(fileno)

    assert mock_os_fsync.called
    assert mock_os_fsync.call_args[0][0] == fileno


@parametrize(
    "arg",
    [
        param(1.1),
        param(True),
        param([]),
        param({}),
        param(set()),
    ],
)
def test_fsync__raises_on_invalid_arg_type(arg):
    with pytest.raises(ValueError):
        sh.fsync(arg)
