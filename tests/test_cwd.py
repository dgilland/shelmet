import os
from pathlib import Path

from shelmet import sh


def test_cwd__should_return_current_working_directory():
    cwd = sh.cwd()
    assert isinstance(cwd, Path)
    assert str(cwd) == os.getcwd()
