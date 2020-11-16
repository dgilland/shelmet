from contextlib import contextmanager
import errno
import fnmatch
import os
from pathlib import Path
import re
import typing as t
from unittest import mock

import pytest
from pytest import param

from shelmet import sh

from .utils import is_subdict


parametrize = pytest.mark.parametrize


USES_FCNTL_FULLSYNC = hasattr(sh.fcntl, "F_FULLFSYNC")


class FakeFile:
    def __init__(self, path: t.Union[Path, str], size: int = 0, text: t.Optional[str] = None):
        self.path = Path(path)
        self.size = size
        self.text = text

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(path={self.path!r})"

    def write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

        if self.text is not None:
            self.path.write_text(self.text)
        elif self.size > 0:
            with self.path.open("wb") as fp:
                fp.seek(self.size - 1)
                fp.write(b"\0")
        else:
            self.path.touch()


class FakeDir:
    def __init__(
        self,
        path: t.Union[Path, str],
        files: t.Optional[t.Sequence[t.Union[FakeFile, str]]] = None,
        dirs: t.Optional[t.Sequence[t.Union["FakeDir", str]]] = None,
    ):
        self.path = Path(path)
        self.files: t.List[FakeFile] = []
        self.dirs: t.List[FakeDir] = []

        if dirs:
            self.dirs = [self.new_dir(dir) for dir in dirs]

        if files:
            self.files = [self.new_file(file) for file in files]

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(path={self.path!r}, files={self.files}, dirs={self.dirs})"
        )

    def mkdir(
        self,
        files: t.Optional[t.Sequence[t.Union[FakeFile, str]]] = None,
        dirs: t.Optional[t.Sequence[t.Union["FakeDir", str]]] = None,
    ) -> None:
        self.path.mkdir(parents=True, exist_ok=True)

        if dirs:
            self.dirs.extend(self.new_dir(dir) for dir in dirs)

        if files:
            self.files.extend(self.new_file(file) for file in files)

        for dir in self.dirs:
            dir.mkdir()

        for file in self.files:
            file.write()

    def add(self, item: t.Union[FakeFile, "FakeDir"]) -> t.Union[FakeFile, "FakeDir"]:
        if isinstance(item, FakeFile):
            return self.add_file(item)
        else:
            return self.add_dir(item)

    def add_all(
        self, items: t.Sequence[t.Union[FakeFile, "FakeDir"]]
    ) -> t.List[t.Union[FakeFile, "FakeDir"]]:
        return [self.add(item) for item in items]

    def add_file(
        self, file: t.Union[FakeFile, str], size: int = 0, text: t.Optional[str] = None
    ) -> FakeFile:
        fake_file = self.new_file(file, size=size, text=text)
        fake_file.write()
        self.files.append(fake_file)
        return fake_file

    def add_dir(self, dir: t.Union["FakeDir", str]) -> "FakeDir":
        fake_dir = self.new_dir(dir)
        fake_dir.mkdir()
        return fake_dir

    def new_file(
        self, file: t.Union[FakeFile, str], size: int = 0, text: t.Optional[str] = None
    ) -> FakeFile:
        kwargs: t.Dict[str, t.Any] = {}
        if isinstance(file, FakeFile):
            kwargs["path"] = file.path
            kwargs["size"] = file.size
            kwargs["text"] = file.text
        else:
            kwargs["path"] = file
            kwargs["size"] = size
            kwargs["text"] = text
        kwargs["path"] = self.path / kwargs["path"]
        return FakeFile(**kwargs)

    def new_dir(self, dir: t.Union["FakeDir", str]) -> "FakeDir":
        kwargs: t.Dict[str, t.Any] = {}
        if isinstance(dir, FakeDir):
            kwargs["path"] = dir.path
            kwargs["files"] = dir.files
            kwargs["dirs"] = dir.dirs

            for f in kwargs["files"]:
                f.path = f.path.relative_to(dir.path)

            for d in kwargs["dirs"]:
                d.path = d.path.relative_to(dir.path)
        else:
            kwargs["path"] = dir
        kwargs["path"] = self.path / kwargs["path"]
        return FakeDir(**kwargs)


@contextmanager
def patch_os_fsync() -> t.Iterator[mock.MagicMock]:
    if USES_FCNTL_FULLSYNC:
        patched_os_fsync = mock.patch("fcntl.fcntl")
    else:
        patched_os_fsync = mock.patch("os.fsync")

    with patched_os_fsync as mocked_os_fsync:
        yield mocked_os_fsync


@parametrize(
    "opts",
    [
        param({}),
        param({"overwrite": False}),
        param({"skip_sync": True}),
        param({"overwrite": False, "skip_sync": True}),
    ],
)
def test_atomic_write(tmp_path: Path, opts: t.Dict[str, t.Any]):
    file = tmp_path / "test.txt"
    text = "test"

    with sh.atomic_write(file, **opts) as fp:
        assert not file.exists()
        fp.write(text)
        assert not file.exists()

    assert file.exists()
    assert file.read_text() == text


def test_atomic_write__should_sync_new_file_and_dir(tmp_path: Path):
    file = tmp_path / "test.txt"

    with patch_os_fsync() as mocked_os_fsync:
        with sh.atomic_write(file) as fp:
            fp.write("test")

    assert mocked_os_fsync.called
    assert mocked_os_fsync.call_count == 2


def test_atomic_write__should_not_overwrite_when_disabled(tmp_path: Path):
    file = tmp_path / "test.txt"
    file.write_text("")

    with pytest.raises(FileExistsError):
        with sh.atomic_write(file, overwrite=False):
            pass


def test_atomic_write__should_fail_if_path_is_dir(tmp_path: Path):
    already_exists_dir = tmp_path
    with pytest.raises(IsADirectoryError):
        with sh.atomic_write(already_exists_dir):
            pass

    will_exist_dir = tmp_path / "test"
    with pytest.raises(IsADirectoryError):
        with sh.atomic_write(will_exist_dir) as fp:
            will_exist_dir.mkdir()
            fp.write("test")


@parametrize(
    "mode",
    [
        param("r"),
        param("r+"),
        param("rb"),
        param("rb+"),
        param("a"),
        param("a+"),
        param("ab"),
        param("ab+"),
        param("x"),
        param("x+"),
        param(True),
    ],
)
def test_atomic_write__should_raise_when_mode_invalid(tmp_path: Path, mode: t.Any):
    with pytest.raises(ValueError):
        with sh.atomic_write(tmp_path / "test.txt", mode):
            pass


@parametrize(
    "path",
    [
        param(""),
        param("a"),
        param("a/b"),
        param("a/b/c"),
    ],
)
def test_cd__should_change_cwd(tmp_path: Path, path: str):
    orig_cwd = os.getcwd()
    cd_path = tmp_path / path
    cd_path.mkdir(parents=True, exist_ok=True)

    with sh.cd(cd_path):
        assert os.getcwd() == str(cd_path)
    assert os.getcwd() == orig_cwd


def test_cp__should_copy_file_to_file(tmp_path: Path):
    src_dir = FakeDir(tmp_path / "src")
    src_file = src_dir.add_file("test.txt", text="test")

    dst_file = tmp_path / "dst" / "target.txt"
    sh.cp(src_file.path, dst_file)

    assert dst_file.is_file()
    assert dst_file.read_text() == src_file.text


def test_cp__should_copy_file_to_existing_dir(tmp_path: Path):
    src_dir = FakeDir(tmp_path / "src")
    src_file = src_dir.add_file("test.txt", text="test")

    dst_dir = FakeDir(tmp_path / "dst")
    dst_dir.mkdir()
    sh.cp(src_file.path, dst_dir.path)

    dst_file = dst_dir.path / src_file.path.name
    assert dst_file.is_file()
    assert dst_file.read_text() == src_file.text


def test_cp__should_copy_dir_to_new_dir(tmp_path: Path):
    src_files = [
        FakeFile("1.txt", text="1"),
        FakeFile("2.txt", text="2"),
        FakeFile("a/a1.txt", text="a1"),
        FakeFile("a/a2.txt", text="a2"),
    ]
    src_dir = FakeDir(tmp_path / "src")
    src_dir.mkdir(files=src_files)

    dst_dir = FakeDir(tmp_path / "dst")
    sh.cp(src_dir.path, dst_dir.path)

    for src_file in src_files:
        dst_file = dst_dir.path / src_file.path
        assert dst_file.is_file()
        assert dst_file.read_text() == src_file.text


def test_cp__should_copy_and_merge_dir_to_existing_dir(tmp_path: Path):
    src_files = [
        FakeFile("1.txt", text="1"),
        FakeFile("2.txt", text="2"),
        FakeFile("a/a1.txt", text="a1"),
        FakeFile("a/a2.txt", text="a2"),
    ]
    src_dir = FakeDir(tmp_path / "src")
    src_dir.mkdir(files=src_files)

    dst_files = [
        FakeFile("11.txt", text="11"),
        FakeFile("22.txt", text="22"),
        FakeFile("a/b1.txt", text="b1"),
        FakeFile("a/b2.txt", text="b2"),
    ]
    dst_dir = FakeDir(tmp_path / "dst")
    dst_dir.mkdir(files=dst_files)

    sh.cp(src_dir.path, dst_dir.path)

    for file in src_files + dst_files:
        dst_file = dst_dir.path / file.path
        assert dst_file.is_file()
        assert dst_file.read_text() == file.text


def test_cp__should_raise_when_copying_dir_to_existing_file(tmp_path: Path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    dst_file = tmp_path / "dst" / "dst.txt"
    dst_file.parent.mkdir()
    dst_file.touch()

    with pytest.raises(FileExistsError):
        sh.cp(src_dir, dst_file)


def test_dirsync(tmp_path: Path):
    path = tmp_path / "test"
    path.mkdir()

    with patch_os_fsync() as mocked_os_fsync:
        sh.dirsync(path)

    assert mocked_os_fsync.called


@parametrize(
    "env",
    [
        param({"a": "1"}),
        param({"a": "1", "b": "2"}),
    ],
)
def test_environ__should_extend_envvars_and_restore_original(env: dict):
    orig_env = os.environ.copy()

    with sh.environ(env) as envvars:
        assert is_subdict(env, envvars)
        assert is_subdict(env, os.environ)
        assert os.environ != orig_env
    assert os.environ == orig_env


@parametrize(
    "env",
    [
        param({"a": "1"}),
        param({"a": "1", "b": "2"}),
    ],
)
def test_environ__should_replace_envvars_and_replace_original(env: dict):
    orig_env = os.environ.copy()

    with sh.environ(env, replace=True) as envvars:
        assert env == envvars
        assert env == os.environ
    assert os.environ == orig_env


def test_fsync__should_sync_file_object(tmp_path: Path):
    file = tmp_path / "test.txt"

    with file.open("w") as fp:
        fp.write("test")
        fileno = fp.fileno()
        with mock.patch.object(fp, "flush") as mock_flush, patch_os_fsync() as mock_os_fsync:
            sh.fsync(fp)

    assert mock_flush.called
    assert mock_os_fsync.called
    assert mock_os_fsync.call_args[0][0] == fileno


def test_fsync__should_sync_fileno(tmp_path: Path):
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
def test_fsync__should_raise_on_invalid_arg_type(arg):
    with pytest.raises(ValueError):
        sh.fsync(arg)


@parametrize(
    "files, pattern, expected_size",
    [
        param([FakeFile("a", size=10)], None, 10),
        param(
            [
                FakeFile("a", size=10),
                FakeFile("b/1", size=5),
                FakeFile("b/2", size=5),
                FakeFile("b/3", size=3),
                FakeFile("b/4", size=2),
                FakeFile("b/c/5", size=100),
                FakeFile("d", size=50),
            ],
            None,
            175,
        ),
        param(
            [
                FakeFile("a.json", size=123),
                FakeFile("b.txt", size=17),
                FakeFile("c.json", size=38),
                FakeFile("d", size=173),
            ],
            "*.json",
            161,
        ),
        param(
            [
                FakeFile("1/a.py", size=123),
                FakeFile("1/2/b.py", size=17),
                FakeFile("1/2/3/c.py", size=38),
                FakeFile("d.py", size=173),
                FakeFile("foo.txt", size=12),
                FakeFile("1/bar.txt", size=293),
                FakeFile("1/2/baz.txt", size=314),
                FakeFile("1/2/3/qux.txt", size=83),
            ],
            "**/*.py",
            351,
        ),
    ],
)
def test_getdirsize(
    tmp_path: Path, files: t.List[FakeFile], pattern: t.Optional[str], expected_size: int
):
    FakeDir(tmp_path).mkdir(files=files)
    kwargs = {}
    if pattern:
        kwargs["pattern"] = pattern
    assert sh.getdirsize(tmp_path, **kwargs) == expected_size


@parametrize(
    "items, kwargs, expected_contents",
    [
        param(
            [
                FakeDir("x/xx", files=[FakeFile("x1.txt")]),
                FakeDir("y/yy", files=[FakeFile("y1.txt"), FakeFile("y2.txt")]),
                FakeDir("z/zz"),
                FakeFile("a.txt"),
                FakeFile("b.txt"),
                FakeFile("c.txt"),
            ],
            {},
            {Path("x"), Path("y"), Path("z"), Path("a.txt"), Path("b.txt"), Path("c.txt")},
        ),
        param(
            [
                FakeDir("x/xx", files=[FakeFile("x1.txt")]),
                FakeDir("y/yy", files=[FakeFile("y1.txt"), FakeFile("y2.txt")]),
                FakeDir("z/zz"),
                FakeFile("a.txt"),
                FakeFile("b.txt"),
                FakeFile("c.txt"),
            ],
            {"recursive": True},
            {
                Path("x"),
                Path("x/xx"),
                Path("x/xx/x1.txt"),
                Path("y"),
                Path("y/yy"),
                Path("y/yy/y1.txt"),
                Path("y/yy/y2.txt"),
                Path("z"),
                Path("z/zz"),
                Path("a.txt"),
                Path("b.txt"),
                Path("c.txt"),
            },
        ),
        param(
            [
                FakeDir("x/xx", files=[FakeFile("x1.txt")]),
                FakeDir("y/yy", files=[FakeFile("y1.txt"), FakeFile("y2.txt")]),
                FakeDir("z/zz"),
                FakeFile("a.txt"),
                FakeFile("b.txt"),
                FakeFile("c.txt"),
            ],
            {"recursive": True, "only_files": True},
            {
                Path("x/xx/x1.txt"),
                Path("y/yy/y1.txt"),
                Path("y/yy/y2.txt"),
                Path("a.txt"),
                Path("b.txt"),
                Path("c.txt"),
            },
        ),
        param(
            [
                FakeDir("x/xx", files=[FakeFile("x1.txt")]),
                FakeDir("y/yy", files=[FakeFile("y1.txt"), FakeFile("y2.txt")]),
                FakeDir("z/zz"),
                FakeFile("a.txt"),
                FakeFile("b.txt"),
                FakeFile("c.txt"),
            ],
            {"recursive": True, "only_dirs": True},
            {Path("x"), Path("x/xx"), Path("y"), Path("y/yy"), Path("z"), Path("z/zz")},
        ),
        param(
            [
                FakeDir("x/xx", files=[FakeFile("x1.txt")]),
                FakeDir("y/yy", files=[FakeFile("y1.txt"), FakeFile("y2.txt")]),
                FakeDir("z/zz"),
                FakeFile("a.txt"),
                FakeFile("b.txt"),
                FakeFile("c.txt"),
            ],
            {"include": "*.txt"},
            {Path("a.txt"), Path("b.txt"), Path("c.txt")},
        ),
        param(
            [
                FakeDir("x/xx", files=[FakeFile("x1.txt")]),
                FakeDir("y/yy", files=[FakeFile("y1.txt"), FakeFile("y2.txt")]),
                FakeDir("z/zz"),
                FakeFile("a.txt"),
                FakeFile("b.txt"),
                FakeFile("c.txt"),
            ],
            {"exclude": "*.txt"},
            {Path("x"), Path("y"), Path("z")},
        ),
        param(
            [
                FakeDir("x/xx", files=[FakeFile("x1.txt")]),
                FakeDir("y/yy", files=[FakeFile("y1.txt"), FakeFile("y2.txt")]),
                FakeDir("z/zz"),
                FakeFile("a.txt"),
                FakeFile("b.txt"),
                FakeFile("c.txt"),
            ],
            {"include": "*.txt", "recursive": True},
            {
                Path("x/xx/x1.txt"),
                Path("y/yy/y1.txt"),
                Path("y/yy/y2.txt"),
                Path("a.txt"),
                Path("b.txt"),
                Path("c.txt"),
            },
        ),
        param(
            [
                FakeDir("x/xx", files=[FakeFile("x1.txt")]),
                FakeDir("y/yy", files=[FakeFile("y1.txt"), FakeFile("y2.txt")]),
                FakeDir("z/zz"),
                FakeFile("a.txt"),
                FakeFile("b.txt"),
                FakeFile("c.txt"),
            ],
            {"exclude": "*.txt", "recursive": True},
            {
                Path("x"),
                Path("x/xx"),
                Path("y"),
                Path("y/yy"),
                Path("z"),
                Path("z/zz"),
            },
        ),
        param(
            [
                FakeDir("x/xx", files=[FakeFile("x1.txt")]),
                FakeDir("y/yy", files=[FakeFile("y1.txt"), FakeFile("y2.txt")]),
                FakeDir("z/zz"),
                FakeFile("a.txt"),
                FakeFile("b.txt"),
                FakeFile("c.txt"),
            ],
            {"include": ["*.txt"], "only_dirs": True, "recursive": True},
            set(),
        ),
    ],
)
def test_ls(
    tmp_path: Path,
    items: t.List[t.Union[FakeDir, FakeFile]],
    kwargs: dict,
    expected_contents: t.Set[Path],
):
    src = FakeDir(tmp_path)
    src.add_all(items)
    src.mkdir()
    with sh.cd(tmp_path):
        contents = set(sh.ls("", **kwargs))
    assert contents == expected_contents


@parametrize(
    "include",
    [
        param("*_include", id="str"),
        param(["foo", "*_include"], id="str_list"),
        param(re.compile(fnmatch.translate("*_include")), id="regex"),
        param(
            [re.compile(fnmatch.translate("foo")), re.compile(fnmatch.translate("*_include"))],
            id="regex_list",
        ),
        param(lambda p: p.name.endswith("_include"), id="callable"),
        param(
            [lambda p: p.name == "foo", lambda p: p.name.endswith("_include")], id="callable_list"
        ),
    ],
)
def test_ls__should_include_on_multiple_types(tmp_path: Path, include: sh.T_LS_FILTER):
    items: t.List[t.Union[FakeDir, FakeFile]] = [
        FakeDir("a_dir_include"),
        FakeDir("b_dir"),
        FakeDir("c_dir_include"),
        FakeFile("d_file_include"),
        FakeFile("e_file"),
        FakeFile("f_file_include"),
    ]
    expected_contents = {
        Path("a_dir_include"),
        Path("c_dir_include"),
        Path("d_file_include"),
        Path("f_file_include"),
    }
    src = FakeDir(tmp_path)
    src.add_all(items)
    src.mkdir()
    with sh.cd(tmp_path):
        contents = set(sh.ls("", include=include))
    assert contents == expected_contents


@parametrize(
    "items, kwargs, expected_contents",
    [
        param(
            [
                FakeDir("a_dir_include"),
                FakeDir("b_dir"),
                FakeDir("c_dir_include"),
                FakeFile("d_file_include"),
                FakeFile("e_file"),
                FakeFile("f_file_include"),
            ],
            {"include": "*_include", "only_files": True},
            {Path("d_file_include"), Path("f_file_include")},
        ),
        param(
            [
                FakeDir("a_dir_include"),
                FakeDir("b_dir"),
                FakeDir("c_dir_include"),
                FakeFile("d_file_include"),
                FakeFile("e_file"),
                FakeFile("f_file_include"),
            ],
            {"include": "*_include", "only_dirs": True},
            {Path("a_dir_include"), Path("c_dir_include")},
        ),
    ],
)
def test_ls__should_use_only_files_and_only_dirs_in_include(
    tmp_path: Path,
    items: t.List[t.Union[FakeDir, FakeFile]],
    kwargs: dict,
    expected_contents: t.Set[Path],
):
    src = FakeDir(tmp_path)
    src.add_all(items)
    src.mkdir()
    with sh.cd(tmp_path):
        contents = set(sh.ls("", **kwargs))
    assert contents == expected_contents


@parametrize(
    "exclude",
    [
        param("*_exclude", id="str"),
        param(["foo", "*_exclude"], id="str_list"),
        param(re.compile(fnmatch.translate("*_exclude")), id="regex"),
        param(
            [re.compile(fnmatch.translate("foo")), re.compile(fnmatch.translate("*_exclude"))],
            id="regex_list",
        ),
        param(lambda p: p.name.endswith("_exclude"), id="callable"),
        param(
            [lambda p: p.name == "foo", lambda p: p.name.endswith("_exclude")], id="callable_list"
        ),
    ],
)
def test_ls__should_exclude_on_multiple_types(tmp_path: Path, exclude: sh.T_LS_FILTER):
    items: t.List[t.Union[FakeDir, FakeFile]] = [
        FakeDir("a_dir_exclude"),
        FakeDir("b_dir"),
        FakeDir("c_dir_exclude"),
        FakeFile("d_file_exclude"),
        FakeFile("e_file"),
        FakeFile("f_file_exclude"),
    ]
    expected_contents = {Path("b_dir"), Path("e_file")}
    src = FakeDir(tmp_path)
    src.add_all(items)
    src.mkdir()
    with sh.cd(tmp_path):
        contents = set(sh.ls("", exclude=exclude))
    assert contents == expected_contents


def test_ls__should_not_recurse_into_excluded_dirs(tmp_path: Path):
    items: t.List[t.Union[FakeDir, FakeFile]] = [
        FakeDir("a_dir_excluded", files=[FakeFile("a1.txt")]),
        FakeDir("b_dir", files=[FakeFile("b2.txt")]),
    ]
    expected_contents = {
        Path("b_dir"),
        Path("b_dir/b2.txt"),
    }
    exclude = "*_excluded"
    src = FakeDir(tmp_path)
    src.add_all(items)
    src.mkdir()
    with sh.cd(tmp_path):
        contents = set(sh.ls("", exclude=exclude, recursive=True))
    assert contents == expected_contents


def test_ls__should_raise_when_both_only_files_and_only_dirs_are_true():
    with pytest.raises(ValueError):
        list(sh.ls(only_files=True, only_dirs=True))


def test_ls__should_raise_when_include_is_invalid_type():
    with pytest.raises(TypeError):
        list(sh.ls(include=True))


@parametrize(
    "fn, expected_kwargs",
    [
        param(sh.lsfiles, {"only_files": True}),
        param(sh.lsdirs, {"only_dirs": True}),
        param(sh.walk, {"recursive": True, "only_files": False, "only_dirs": False}),
        param(sh.walkfiles, {"recursive": True, "only_files": True, "only_dirs": False}),
        param(sh.walkdirs, {"recursive": True, "only_dirs": True, "only_files": False}),
    ],
)
def test_ls_aliases(tmp_path: Path, fn: t.Callable, expected_kwargs: dict):
    expected_kwargs["include"] = None
    expected_kwargs["exclude"] = None

    with mock.patch.object(sh, "ls") as mocked_ls:
        list(fn(tmp_path))

    assert mocked_ls.called
    assert mocked_ls.call_args[1] == expected_kwargs


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


def test_mkdir__should_set_mode(tmp_path: Path):
    targets = [tmp_path / "test1", tmp_path / "test2", tmp_path / "1" / "2" / "3"]
    mode = 0o755

    sh.mkdir(*targets, mode=mode)
    for target in targets:
        target_mode = oct(target.stat().st_mode & 0o777)
        assert target_mode == oct(mode)


def test_mkdir__should_raise_if_exist_not_ok(tmp_path: Path):
    with pytest.raises(FileExistsError):
        sh.mkdir(tmp_path, exist_ok=False)


@parametrize(
    "src, dst, expected",
    [
        param(
            FakeFile("src.txt", text="src"),
            FakeFile("dst.txt"),
            FakeFile("dst.txt", text="src"),
            id="to_new_file",
        ),
        param(
            FakeFile("src.txt", text="src"),
            FakeDir("dst"),
            FakeFile("dst/src.txt", text="src"),
            id="to_new_file_under_destination",
        ),
        param(
            FakeFile("src.txt", text="src"),
            FakeFile("dst.txt", text="dst"),
            FakeFile("dst.txt", text="src"),
            id="to_overwite_existing_file",
        ),
    ],
)
def test_mv__should_move_file(
    tmp_path: Path, src: FakeFile, dst: t.Union[FakeFile, FakeDir], expected: FakeFile
):
    base_dir = FakeDir(tmp_path)
    src_file = base_dir.add_file(src)
    expected_file = base_dir.new_file(expected)

    dst_target: t.Union[FakeFile, FakeDir]
    if isinstance(dst, FakeFile):
        dst_target = base_dir.new_file(dst)
        if dst_target.text:
            dst_target.write()
    else:
        dst_target = base_dir.add_dir(dst)

    sh.mv(src_file.path, dst_target.path)

    assert not src_file.path.exists()
    assert expected_file.path.exists()
    assert expected_file.path.read_text() == expected_file.text


@parametrize(
    "src_files, dst, expected",
    [
        param([FakeFile("1.txt", text="1")], "dst", "dst", id="to_new_dir"),
        param(
            [FakeFile("1.txt", text="1")],
            FakeDir("dst", files=[FakeFile("2.txt")]),
            "dst/src",
            id="to_new_dir_under_destination",
        ),
        param(
            [FakeFile("1.txt", text="1")],
            FakeDir("dst", dirs=[FakeDir("src")]),
            "dst/src",
            id="to_new_dir_overwriting_existing_dir_under_destination",
        ),
    ],
)
def test_mv__should_move_dir(
    tmp_path: Path, src_files: t.List[FakeFile], dst: t.Union[FakeDir, str], expected: str
):
    src_dir = FakeDir(tmp_path / "src", files=src_files)
    src_dir.mkdir()

    if isinstance(dst, FakeDir):
        dst_dir = FakeDir(tmp_path / dst.path, files=dst.files)
        dst_dir.mkdir()
    else:
        dst_dir = FakeDir(tmp_path / dst)

    sh.mv(src_dir.path, dst_dir.path)

    expected_dst_dir = FakeDir(tmp_path / expected)
    assert not src_dir.path.exists()
    assert expected_dst_dir.path.exists()

    for src_file in src_files:
        dst_file = expected_dst_dir.new_file(src_file)
        assert dst_file.path.read_text() == src_file.text


def test_mv__should_allow_same_file_as_destination(tmp_path: Path):
    src_file = FakeFile(tmp_path / "src.txt", text="src")
    src_file.write()
    sh.mv(src_file.path, src_file.path)
    assert src_file.path.exists()
    assert src_file.path.read_text() == src_file.text


def test_mv__should_work_across_file_systems(tmp_path: Path):
    src_file = FakeFile(tmp_path / "src.txt", text="src")
    src_file.write()

    dst_file = FakeFile(tmp_path / "dst.txt")
    _os_rename = os.rename

    def mock_os_rename(src, dst):
        if str(src) == str(src_file.path) and str(dst) == str(dst_file.path):
            raise OSError(errno.EXDEV, "mock error from move across file systems")
        return _os_rename(src, dst)

    with mock.patch("os.rename", side_effect=mock_os_rename):
        sh.mv(src_file.path, dst_file.path)

    assert dst_file.path.exists()
    assert dst_file.path.read_text() == src_file.text
    assert not src_file.path.exists()


def test_mv__should_raise_when_source_dir_exists_in_destination_and_is_not_empty(tmp_path: Path):
    src_dir = FakeDir(tmp_path / "src", files=[FakeFile("src.txt", text="src")])
    src_dir.mkdir()
    dst_dir = FakeDir(tmp_path / "dst", files=[FakeFile("src/other.txt", text="other")])
    dst_dir.mkdir()

    with pytest.raises(OSError):
        sh.mv(src_dir.path, dst_dir.path)


@parametrize(
    "paths, expected",
    [
        param(["a"], "a"),
        param(["a/"], "a"),
        param(["a", "b", "c/d"], "a/b/c/d"),
        param(["a", "/b", "/c/d"], "a/b/c/d"),
        param(["/a", "b", "c/d"], "/a/b/c/d"),
        param(["/a/", "/b/", "/c/d/"], "/a/b/c/d"),
        param([Path("a")], "a"),
        param([Path("a/")], "a"),
        param([Path("a"), Path("b"), Path("c/d")], "a/b/c/d"),
        param([Path("a"), Path("/b"), Path("/c/d")], "a/b/c/d"),
        param([Path("/a"), Path("b"), Path("c/d")], "/a/b/c/d"),
        param(["a", Path("b"), "c/d"], "a/b/c/d"),
        param([Path("a"), "b", Path("c/d")], "a/b/c/d"),
    ],
)
def test_reljoin(paths: t.Sequence[t.Union[Path, str]], expected: str):
    assert sh.reljoin(*paths) == expected


@parametrize(
    "sources",
    [
        param([FakeFile("1.txt")], id="one_file"),
        param([FakeFile("1.txt"), FakeFile("2.txt"), FakeFile("3.txt")], id="many_files"),
        param([FakeDir("1")], id="one_dir_with_no_files"),
        param(
            [FakeDir("1", files=[FakeFile("1.txt"), FakeFile("2.txt")])], id="one_dir_with_files"
        ),
        param(
            [FakeDir("1"), FakeDir("2"), FakeDir("3/4"), FakeDir("5/6/7")],
            id="many_dirs_with_no_files",
        ),
        param(
            [
                FakeDir("1", files=[FakeFile("1.txt")]),
                FakeDir("2", files=[FakeFile("2.txt")], dirs=[FakeDir("2.1")]),
                FakeDir("3/4", files=[FakeFile("3.txt"), FakeFile("4.txt")]),
                FakeDir("5/6/7"),
            ],
            id="many_dirs_with_files",
        ),
    ],
)
def test_rm(tmp_path: Path, sources: t.Sequence[FakeFile]):
    base_dir = FakeDir(tmp_path)
    srcs = [base_dir.add(source) for source in sources]

    for src in srcs:
        assert src.path.exists()

    sh.rm(*(src.path for src in srcs))

    for src in srcs:
        assert not src.path.exists()


@parametrize(
    "sources",
    [
        param([FakeDir("1")], id="one_dir_with_no_files"),
        param(
            [FakeDir("1", files=[FakeFile("1.txt"), FakeFile("2.txt")])], id="one_dir_with_files"
        ),
        param(
            [FakeDir("1"), FakeDir("2"), FakeDir("3/4"), FakeDir("5/6/7")],
            id="many_dirs_with_no_files",
        ),
        param(
            [
                FakeDir("1", files=[FakeFile("1.txt")]),
                FakeDir("2", files=[FakeFile("2.txt")], dirs=[FakeDir("2.1")]),
                FakeDir("3/4", files=[FakeFile("3.txt"), FakeFile("4.txt")]),
                FakeDir("5/6/7"),
            ],
            id="many_dirs_with_files",
        ),
    ],
)
def test_rmdir(tmp_path: Path, sources: t.Sequence[FakeFile]):
    base_dir = FakeDir(tmp_path)
    srcs = [base_dir.add(source) for source in sources]

    for src in srcs:
        assert src.path.exists()

    sh.rmdir(*(src.path for src in srcs))

    for src in srcs:
        assert not src.path.exists()


def test_rmdir__should_raise_on_file(tmp_path: Path):
    path = tmp_path / "test.txt"
    path.touch()

    with pytest.raises(NotADirectoryError):
        sh.rmdir(path)


@parametrize(
    "sources",
    [
        param([FakeFile("1.txt")], id="one_file"),
        param([FakeFile("1.txt"), FakeFile("2.txt"), FakeFile("3.txt")], id="many_files"),
    ],
)
def test_rmfile(tmp_path: Path, sources: t.Sequence[FakeFile]):
    base_dir = FakeDir(tmp_path)
    srcs = [base_dir.add(source) for source in sources]

    for src in srcs:
        assert src.path.exists()

    sh.rmfile(*(src.path for src in srcs))

    for src in srcs:
        assert not src.path.exists()


def test_rmfile__should_raise_on_dir(tmp_path: Path):
    path = tmp_path / "test"
    path.mkdir()

    with pytest.raises(IsADirectoryError):
        sh.rmfile(path)


@parametrize(
    "rm_fn",
    [
        param(sh.rm),
        param(sh.rmdir),
        param(sh.rmfile),
    ],
)
def test_rm_fn__should_ignore_missing_sources(tmp_path: Path, rm_fn: t.Callable):
    rm_fn(tmp_path / "1", tmp_path / "2", tmp_path / "3")


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
