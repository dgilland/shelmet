import os
from pathlib import Path

from shelmet import sh


def test_homedir__should_return_user_home_directory():
    home = sh.homedir()
    assert isinstance(home, Path)
    assert str(home) == os.path.expanduser("~")
