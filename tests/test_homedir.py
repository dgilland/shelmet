import os
from pathlib import Path

import shelmet as sh


def test_homedir__should_return_user_home_directory():
    home = sh.homedir()
    assert isinstance(home, Path)
    assert str(home) == os.path.expanduser("~")
