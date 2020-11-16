"""The sh module contains utilities for interacting with files, directories, and the file system."""

from contextlib import contextmanager
import errno
import os
from pathlib import Path
import random
import shutil
import string
import typing as t


try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore


T_PATHLIKE = t.Union[str, Path]


@contextmanager
def atomic_write(
    file: T_PATHLIKE,
    mode: str = "w",
    *,
    skip_sync: bool = False,
    overwrite: bool = True,
    **open_kwargs: t.Any,
) -> t.Iterator[t.IO]:
    """
    Context-manager similar to ``open()`` that is used to perform an atomic file write operation by
    first writing to a temporary location in the same directory as the destination and then renaming
    the file to the destination after all write operations are finished.

    By default, this function will open a temporary file for writing in the same directory as the
    destination. A file object will be returned by this context-manager just like ``open()`` would.
    All file operations while the context-manager is opened will be performed on the temporary file.
    Once the context-manager is closed, the temporary file will flushed and fsync'd (unless
    ``skip_sync=True``). If the destination file exists, it will be overwritten unless
    ``overwrite=False``.

    Args:
        file: File path to write to.
        mode: File open mode.
        skip_sync: Whether to skip calling ``fsync`` on file. Skipping this can help with
            performance at the cost of durability.
        overwrite: Whether to raise an exception if the destination file exists once the file is to
            be written to its destination.
        **open_kwargs: Additional keyword arguments to ``open()`` when creating the temporary write
            file.
    """
    if isinstance(mode, str) and "x" in mode:
        raise ValueError("Atomic write mode 'x' is not supported. Use 'overwrite=False' instead.")

    if not isinstance(mode, str) or "w" not in mode:
        raise ValueError(f"Invalid atomic write mode: {mode}")

    dst = Path(file).absolute()
    if dst.is_dir():
        raise IsADirectoryError(errno.EISDIR, f"Atomic write file must not be a directory: {dst}")

    mkdir(dst.parent)
    tmp_file = _candidate_temp_path(path=dst, prefix="_", suffix=".tmp")

    try:
        with open(tmp_file, mode, **open_kwargs) as fp:
            yield fp
            if not skip_sync:
                fsync(fp)

        if overwrite:
            os.rename(tmp_file, dst)
        else:
            # This will fail if dst exists.
            os.link(tmp_file, dst)
            rm(tmp_file)

        if not skip_sync:
            dirsync(dst.parent)
    finally:
        # In case something went wrong that prevented moving tmp_file to dst.
        rm(tmp_file)


@contextmanager
def cd(path: T_PATHLIKE) -> t.Iterator[None]:
    """
    Context manager that changes the working directory on enter and restores it on exit.

    Args:
        path: Directory to change to.

    Yields:
        None
    """
    orig_cwd = os.getcwd()

    if path:
        os.chdir(path)

    try:
        yield
    finally:
        if path:
            os.chdir(orig_cwd)


def cp(src: T_PATHLIKE, dst: T_PATHLIKE, *, follow_symlinks: bool = True) -> None:
    """

    Args:
        src: Source file or directory to copy from.
        dst: Destination file or directory to copy to.
        follow_symlinks: When true (the default), symlinks in the source will be dereferenced into
            the destination. When false, symlinks in the source will be preserved as symlinks in the
            destination.
    """
    src = Path(src)
    dst = Path(dst)
    mkdir(dst.parent)

    if src.is_dir():
        if dst.exists() and not dst.is_dir():
            raise FileExistsError(
                errno.EEXIST, f"Cannot copy {src!r} to {dst!r} since destination is a file"
            )

        if dst.is_dir():
            src_dirname = str(src)
            dst_dirname = str(dst)
            for src_dir, _dirs, files in os.walk(str(src)):
                dst_dir = src_dir.replace(src_dirname, dst_dirname, 1)
                for file in files:
                    src_file = os.path.join(src_dir, file)
                    dst_file = os.path.join(dst_dir, file)
                    cp(src_file, dst_file, follow_symlinks=follow_symlinks)
        else:

            def copy_function(_src, _dst):
                return cp(_src, _dst, follow_symlinks=follow_symlinks)

            shutil.copytree(src, dst, symlinks=not follow_symlinks, copy_function=copy_function)
    else:
        if dst.is_dir():
            dst = dst / src.name
        tmp_dst = _candidate_temp_path(path=dst, prefix="_")
        shutil.copy2(src, tmp_dst, follow_symlinks=follow_symlinks)
        try:
            os.rename(tmp_dst, dst)
        except OSError:  # pragma: no cover
            rm(tmp_dst)
            raise


@contextmanager
def environ(
    env: t.Optional[t.Dict[str, str]] = None, *, replace: bool = False
) -> t.Iterator[t.Dict[str, str]]:
    """
    Context manager that updates environment variables with `env` on enter and restores the original
    environment on exit.

    Args:
        env: Environment variables to set.
        replace: Whether to clear existing environment variables before setting new ones. This fully
            replaces the existing environment variables so that only `env` are set.

    Yields:
        The current environment variables.
    """
    orig_env = os.environ.copy()

    if replace:
        os.environ.clear()

    if env:
        os.environ.update(env)

    try:
        yield os.environ.copy()
    finally:
        os.environ.clear()
        os.environ.update(orig_env)


def dirsync(path: T_PATHLIKE) -> None:
    """
    Force sync on directory.

    Args:
        path: Directory to sync.
    """
    fd = os.open(path, os.O_RDONLY)
    try:
        fsync(fd)
    finally:
        os.close(fd)


def fsync(fd: t.Union[t.IO, int]) -> None:
    """
    Force write of file to disk.

    The file descriptor will have ``os.fsync()`` (or ``fcntl.fcntl()`` with ``fcntl.F_FULLFSYNC``
    if available) called on it. If a file object is passed it, then it will first be flushed before
    synced.

    Args:
        fd: Either file descriptor integer or file object.
    """
    if (
        not isinstance(fd, int)
        and not (hasattr(fd, "fileno") and hasattr(fd, "flush"))
        or isinstance(fd, bool)
    ):
        raise ValueError(
            f"File descriptor must be a fileno integer or file-like object, not {type(fd)}"
        )

    if isinstance(fd, int):
        fileno = fd
    else:
        fileno = fd.fileno()
        fd.flush()

    if hasattr(fcntl, "F_FULLFSYNC"):  # pragma: no cover
        # Necessary for MacOS to do proper fsync: https://bugs.python.org/issue11877
        fcntl.fcntl(fileno, fcntl.F_FULLFSYNC)  # pylint: disable=no-member
    else:  # pragma: no cover
        os.fsync(fileno)


def getdirsize(path: T_PATHLIKE, pattern: str = "**/*") -> int:
    """
    Return total size of directory's contents.

    Args:
        path: Directory to calculate total size of.
        pattern: Only count files if they match this glob-pattern.

    Returns:
        Total size of directory in bytes.
    """
    total_size = 0

    for item in Path(path).glob(pattern):
        if item.is_file():
            try:
                total_size += item.stat().st_size
            except OSError:  # pragma: no cover
                # File doesn't exist or is inaccessible.
                pass

    return total_size


def mkdir(*paths: T_PATHLIKE, mode: int = 0o777, exist_ok: bool = True) -> None:
    """
    Recursively create directories in `paths` along with any parent directories that don't already
    exists.

    This is like the Unix command ``mkdir -p <path1> <path2> ...``.

    Args:
        *paths: Directories to create.
        mode: Access mode for directories.
        exist_ok: Whether it's ok or not if the path already exists. When ``True``, a
            ``FileExistsError`` will be raised.
    """
    for path in paths:
        os.makedirs(path, mode=mode, exist_ok=exist_ok)


def mv(src: T_PATHLIKE, dst: T_PATHLIKE) -> None:
    """
    Move source file or directory to destination.

    The move semantics are as follows:

    - If src and dst are files, then src will be renamed to dst and overwrite dst if it exists.
    - If src is a file and dst is a directory, then src will be moved under dst.
    - If src is a directory and dst does not exist, then src will be renamed to dst and any parent
      directories that don't exist in the dst path will be created.
    - If src is a directory and dst is a directory and the src's basename does not exist or if the
      basename is an empty directory, then src will be moved under dst.
    - If src is directory and dst is a directory and the src's basename is a non-empty directory
      under dst, then an ``OSError`` will be raised.
    - If src and dst reference two difference file-systems, then src will be copied to dst using
      :func:`.cp` and then deleted at src.

    Args:
        src: Source file or directory to move.
        dst: Destination file or directory to move source to.
    """
    src = Path(src)
    dst = Path(dst)
    mkdir(dst.parent)

    if dst.is_dir():
        dst = dst / src.name

    try:
        os.rename(src, dst)
    except OSError as exc:
        if exc.errno == errno.EXDEV:
            # errno.EXDEV means we tried to move from one file-system to another which is not
            # allowed. In that case, we'll fallback to a copy-and-delete approach instead.
            tmp_dst = _candidate_temp_path(path=dst, prefix="_")
            try:
                cp(src, tmp_dst)
                os.rename(tmp_dst, dst)
                rm(src)
            finally:
                rm(tmp_dst)
        else:
            raise


def reljoin(*paths: T_PATHLIKE) -> str:
    """
    Like ``os.path.join`` except that all paths are treated as relative to the previous one so that
    an absolute path in the middle will extend the existing path instead of becoming the new root
    path.

    Args:
        *paths: Paths to join together.
    """
    path = os.sep.join(str(Path(path)) for path in paths)
    return os.path.normpath(path)


def rm(*paths: T_PATHLIKE) -> None:
    """
    Delete files and directories.

    Note:
        Deleting non-existent files or directories does not raise an error.

    Warning:
        This function is like ``$ rm -rf`` so be careful. To limit the scope of the removal to just
        files or just directories, use :func:`.rmfile` or :func:`.rmdir` respectively.

    Args:
        *paths: Files and/or directories to delete.
    """
    for path in paths:
        try:
            try:
                shutil.rmtree(path)
            except NotADirectoryError:
                os.remove(path)
        except FileNotFoundError:
            pass


def rmdir(*dirs: T_PATHLIKE) -> None:
    """
    Delete directories.

    Note:
        Deleting non-existent directories does not raise an error.

    Warning:
        This function is like calling ``$ rm -rf`` on a directory. To limit the scope of the removal
        to just files, use :func:`.rmfile`.

    Args:
        *dirs: Directories to delete.

    Raises:
        NotADirectoryError: When given path is not a directory.
    """
    for path in dirs:
        try:
            shutil.rmtree(path)
        except FileNotFoundError:
            pass


def rmfile(*files: T_PATHLIKE) -> None:
    """
    Delete files.

    Note:
        Deleting non-existent files does not raise an error.

    Args:
        *files: Files to delete.

    Raises:
        IsADirectoryError: When given path is a directory.
    """
    for path in files:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


def touch(*paths: T_PATHLIKE) -> None:
    """
    Touch files.

    Args:
        *paths: File paths to create.
    """
    for path in paths:
        path = Path(path)
        mkdir(path.parent)
        path.touch()


@contextmanager
def umask(mask: int = 0):
    """
    Context manager that sets the umask to `mask` and restores it on exit.

    Args:
        mask: Numeric umask to set.

    Yields:
        None
    """
    orig_mask = os.umask(mask)
    try:
        yield
    finally:
        os.umask(orig_mask)


def _candidate_temp_path(
    path: T_PATHLIKE = "", prefix: T_PATHLIKE = "", suffix: T_PATHLIKE = "", hidden: bool = True
) -> str:
    tries = 100
    for _ in range(tries):
        filename = Path(_random_name(path=path, prefix=prefix, suffix=suffix))
        if hidden:
            filename = filename.parent / f".{filename.name}"
        if not filename.exists():
            return str(filename)
    raise FileNotFoundError(
        errno.ENOENT, f"No usable temporary filename found in {Path(prefix).absolute()}"
    )  # pragma: no cover


def _random_name(
    path: T_PATHLIKE = "", prefix: T_PATHLIKE = "", suffix: T_PATHLIKE = "", length: int = 8
) -> str:
    _pid, _random = getattr(_random_name, "_state", (None, None))
    if _pid != os.getpid() or not _random:
        # Ensure separate processes don't share same random generator.
        _random = random.Random()
        _random_name._state = (os.getpid(), _random)  # type: ignore

    inner = "".join(_random.choice(string.ascii_letters) for _ in range(length))
    return f"{path}{prefix}{inner}{suffix}"
