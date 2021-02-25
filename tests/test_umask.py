from pathlib import Path

import shelmet as sh


def test_umask(tmp_path: Path):
    mode = 0o644  # -rw-rw-r-- (user,group = read-write, other = read)
    umask = 0o77  # g-rw,o-rw (disallow read-write for group and other)
    expected_mode_with_umask = 0o600  # -rw------- (user = read-write, group,other = no-access)

    file_before_umask = tmp_path / "before"
    file_with_umask = tmp_path / "with"
    file_after_umask = tmp_path / "after"

    file_before_umask.touch(mode=mode)
    stat_before = file_before_umask.stat()
    assert oct(stat_before.st_mode & 0o777) == oct(mode)

    with sh.umask(umask):
        file_with_umask.touch(mode=mode)
        stat_during = file_with_umask.stat()
        assert oct(stat_during.st_mode & 0o777) == oct(expected_mode_with_umask)

    file_after_umask.touch(mode=mode)
    stat_after = file_after_umask.stat()
    assert oct(stat_after.st_mode & 0o777) == oct(mode)
