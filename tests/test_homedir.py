import os
from pathlib import Path

import shelmet as sh


def test_homedir__returns_user_home_directory():
    home = sh.homedir()
    assert isinstance(home, Path)
    assert str(home) == os.path.expanduser("~")
