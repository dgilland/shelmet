from contextlib import contextmanager
import filecmp
from pathlib import Path
import typing as t
from unittest import mock


try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore


USES_FCNTL_FULLSYNC = hasattr(fcntl, "F_FULLFSYNC")

TAR_COMPRESSIONS = {
    ".tar": "",
    ".tar.gz": "gz",
    ".tgz": "gz",
    ".taz": "gz",
    ".tar.bz2": "bz2",
    ".tb2": "bz2",
    ".tbz": "bz2",
    ".tbz2": "bz2",
    ".tz2": "bz2",
    ".tar.xz": "xz",
    ".txz": "xz",
}
TAR_EXTENSIONS = list(TAR_COMPRESSIONS.keys())
ZIP_EXTENSIONS = [
    ".docx",
    ".egg",
    ".jar",
    ".odg",
    ".odp",
    ".ods",
    ".odt",
    ".pptx",
    ".xlsx",
    ".zip",
]
ARCHIVE_EXTENSIONS = TAR_EXTENSIONS + ZIP_EXTENSIONS


class File:
    def __init__(self, path: t.Union[Path, str], text: t.Optional[str] = None, size: int = 0):
        self.path = Path(path)
        self.text = text
        self.size = size

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(path={self.path!r})"

    def clone(self) -> "File":
        return self.__class__(self.path, text=self.text, size=self.size)

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


class Dir:
    def __init__(self, path: t.Union[Path, str], *items: t.Union[File, "Dir"]):
        self.path = Path(path)
        self.items = list(items)

    @property
    def files(self) -> t.List[File]:
        return [item for item in self.items if isinstance(item, File)]

    @property
    def dirs(self) -> t.List["Dir"]:
        return [item for item in self.items if isinstance(item, Dir)]

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(path={self.path!r}, files={self.files}, dirs={self.dirs})"
        )

    def clone(self) -> "Dir":
        return self.__class__(self.path, *(item.clone() for item in self.items))

    def mkdir(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)

        for dir in self.dirs:
            dir.path = self.path / dir.path
            dir.mkdir()

        for file in self.files:
            file.path = self.path / file.path
            file.write()

    def repath(self, root: Path) -> "Dir":
        items = []
        for item in self.items:
            new_path = root / item.path.relative_to(self.path)
            if isinstance(item, File):
                item = item.clone()
                item.path = new_path
            else:
                item = item.repath(new_path)
            items.append(item)
        return Dir(root, *items)


@contextmanager
def patch_os_fsync() -> t.Iterator[mock.MagicMock]:
    if USES_FCNTL_FULLSYNC:
        patched_os_fsync = mock.patch("fcntl.fcntl")
    else:
        patched_os_fsync = mock.patch("os.fsync")

    with patched_os_fsync as mocked_os_fsync:
        yield mocked_os_fsync


def is_same_file(file1: Path, file2: Path) -> bool:
    return filecmp.cmp(file1, file2)


def is_same_dir(dir1: Path, dir2: Path) -> bool:
    return _is_same_dir(filecmp.dircmp(dir1, dir2))


def _is_same_dir(dcmp: filecmp.dircmp) -> bool:
    if dcmp.diff_files or dcmp.left_only or dcmp.right_only:
        return False

    for sub_dcmp in dcmp.subdirs.values():
        if not _is_same_dir(sub_dcmp):
            return False

    return True


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
