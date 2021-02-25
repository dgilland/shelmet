from contextlib import contextmanager
from pathlib import Path
import typing as t
from unittest import mock


try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore


USES_FCNTL_FULLSYNC = hasattr(fcntl, "F_FULLFSYNC")


def is_subdict(subset: dict, superset: dict) -> bool:
    """Return whether one dict is a subset of another."""
    if isinstance(subset, dict):
        return all(
            key in superset and is_subdict(val, superset[key]) for key, val in subset.items()
        )

    if isinstance(subset, list) and isinstance(superset, list) and len(superset) == len(subset):
        return all(is_subdict(subitem, superset[idx]) for idx, subitem in enumerate(subset))

    # Assume that subset is a plain value if none of the above match.
    return subset == superset


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
