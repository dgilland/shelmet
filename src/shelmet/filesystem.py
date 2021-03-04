"""The filesystem module contains utilities for interacting with the file system."""

from contextlib import contextmanager
from datetime import datetime, timezone
import errno
from functools import partial
import io
import os
from pathlib import Path
import random
import shutil
import string
import typing as t

from .types import (
    READ_ONLY_MODES,
    WRITE_ONLY_BIN_MODES,
    WRITE_ONLY_MODES,
    WRITE_ONLY_TEXT_MODES,
    ReadOnlyBinMode,
    ReadOnlyTextMode,
    StrPath,
    WriteOnlyBinMode,
    WriteOnlyTextMode,
)


try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore


DEFAULT_CHUNK_SIZE = io.DEFAULT_BUFFER_SIZE


@contextmanager
def atomicdir(dir: StrPath, *, skip_sync: bool = False, overwrite: bool = True) -> t.Iterator[Path]:
    """
    Context-manager that is used to atomically create a directory and its contents.

    This context-manager will create a temporary directory in the same directory as the destination
    and yield the temporary directory as a ``pathblib.Path`` object. All atomic file system updates
    to the directory should then be done within the context-manager. Once the context-manager exits,
    the temporary directory will be passed to :func:`dirsync` (unless ``skip_sync=True``) and then
    moved to the destination followed by :func:`dirsync` on the parent directory. If the
    destination directory exists, it will be overwritten unless ``overwrite=False``.

    Args:
        dir: Directory path to create.
        skip_sync: Whether to skip calling :func:`dirsync` on the directory. Skipping this can help
            with performance at the cost of durability.
        overwrite: Whether to raise an exception if the destination exists once the directory is to
            be moved to its destination.
    """
    dst = Path(dir).absolute()
    if dst.is_file():
        raise FileExistsError(errno.EEXIST, f"Atomic directory target must not be a file: {dst}")

    tmp_dir = _candidate_temp_pathname(path=dst, prefix="_", suffix="_tmp")
    mkdir(tmp_dir)

    try:
        yield Path(tmp_dir)

        if not skip_sync:
            dirsync(tmp_dir)

        if overwrite:
            rm(dst)
        elif dst.exists():
            raise FileExistsError(
                errno.EEXIST,
                f"Atomic directory target must not exist when overwrite disabled: {dst}",
            )

        os.rename(tmp_dir, dst)

        if not skip_sync:
            dirsync(dst)
    finally:
        # In case something went wrong that prevented moving tmp_dir to dst.
        rm(tmp_dir)


@contextmanager
def atomicfile(
    file: StrPath,
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

    This context-manager will open a temporary file for writing in the same directory as the
    destination and yield a file object just like ``open()`` does. All file operations while the
    context-manager is opened will be performed on the temporary file. Once the context-manager
    exits, the temporary file will flushed and fsync'd (unless ``skip_sync=True``). If the
    destination file exists, it will be overwritten unless ``overwrite=False``.

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
        raise ValueError(
            "Atomic file write mode 'x' is not supported. Use 'overwrite=False' instead."
        )

    if not isinstance(mode, str) or "w" not in mode:
        raise ValueError(f"Invalid atomic write mode: {mode}")

    dst = Path(file).absolute()
    if dst.is_dir():
        raise IsADirectoryError(errno.EISDIR, f"Atomic file target must not be a directory: {dst}")

    mkdir(dst.parent)
    tmp_file = _candidate_temp_pathname(path=dst, prefix="_", suffix=".tmp")

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


def backup(
    src: StrPath,
    *,
    timestamp: t.Optional[str] = "%Y-%m-%dT%H:%M:%S.%f%z",
    utc: bool = False,
    epoch: bool = False,
    prefix: str = "",
    suffix: str = "~",
    hidden: bool = False,
    overwrite: bool = False,
    dir: t.Optional[StrPath] = None,
    namer: t.Optional[t.Callable[[Path], StrPath]] = None,
) -> Path:
    """
    Create a backup of a file or directory.

    The format of the backup name is ``{prefix}{src}.{timestamp}{suffix}``.

    By default, the backup will be created in the same parent directory as the source and be named
    like ``"src.YYYY-MM-DDThh:mm:ss.ffffff~"``, where the timestamp is the current local time.

    If `utc` is ``True``, then the timestamp will be in the UTC timezone.

    If `epoch` is ``True``, then the timestamp will be the Unix time as returned by
    ``time.time()`` instead of the strftime format.

    If `hidden` is ``True``, then a ``"."`` will be prepended to the `prefix`. It won't be added if
    `prefix` already starts with a ``"."``.

    If `dir` is given, it will be used as the parent directory of the backup instead of the source's
    parent directory.

    If `overwrite` is ``True`` and the backup location already exists, then it will be overwritten.

    If `namer` is given, it will be called with ``namer(src)`` and it should return the full
    destination path of the backup. All other arguments to this function will be ignored except for
    `overwrite`.

    Args:
        src: Source file or directory to backup.
        timestamp: Timestamp strftime-format string or ``None`` to exclude timestamp from backup
            name. Defaults to ISO-8601 format.
        utc: Whether to use UTC time instead of local time for the timestamp.
        epoch: Whether to use the Unix time for the timestamp instead of the strftime format in
            `timestamp`.
        prefix: Name prefix to prepend to the backup.
        suffix: Name suffix to append to the backup.
        hidden: Whether to ensure that the backup location is a hidden file or directory.
        overwrite: Whether to overwrite an existing file or directory when backing up.
        dir: Set the parent directory of the backup. Defaults to ``None`` which will use the parent
            directory of the `src`.
        namer: Naming function that can be used to return the full path of the backup location. It
            will be passed the `src` value as a ``pathlib.Path`` object as a positional argument. It
            should return the destination path of the backup as a ``str`` or ``pathlib.Path``.

    Returns:
        Backup location.
    """
    if not isinstance(timestamp, str) and timestamp is not None:
        raise ValueError(
            f"timestamp should be a strftime-formatted string or None, not {timestamp!r}"
        )

    src = Path(src).resolve()

    if namer:
        dst = Path(namer(src)).resolve()
    else:
        dst = _backup_namer(
            src,
            timestamp=timestamp,
            utc=utc,
            epoch=epoch,
            prefix=prefix,
            suffix=suffix,
            hidden=hidden,
            dir=dir,
        )

    if src == dst:
        raise FileExistsError(errno.EEXIST, f"Backup destination cannot be the source: {src}")

    if not overwrite and dst.exists():
        raise FileExistsError(errno.EEXIST, f"Backup destination already exists: {dst}")

    cp(src, dst)

    return dst


def _backup_namer(
    src: Path,
    *,
    timestamp: t.Optional[str] = "%Y-%m-%dT%H:%M:%S.%f%z",
    utc: bool = False,
    epoch: bool = False,
    prefix: str = "",
    suffix: str = "~",
    hidden: bool = False,
    dir: t.Optional[StrPath] = None,
) -> Path:
    if not dir:
        dir = src.parent
    else:
        dir = Path(dir).resolve()

    if hidden and not prefix.startswith("."):
        prefix = f".{prefix}"

    ts: t.Union[str, float] = ""
    if timestamp is not None:
        tz = None
        if utc:
            tz = timezone.utc
        dt = datetime.now(tz)

        if epoch:
            ts = dt.timestamp()
        else:
            ts = dt.strftime(timestamp)

        ts = f".{ts}"

    name = f"{prefix}{src.name}{ts}{suffix}"
    dst = dir / name

    return dst


def cp(src: StrPath, dst: StrPath, *, follow_symlinks: bool = True) -> None:
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
        tmp_dst = _candidate_temp_pathname(path=dst, prefix="_")
        shutil.copy2(src, tmp_dst, follow_symlinks=follow_symlinks)
        try:
            os.rename(tmp_dst, dst)
        except OSError:  # pragma: no cover
            rm(tmp_dst)
            raise


def dirsync(path: StrPath) -> None:
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


def getdirsize(path: StrPath, pattern: str = "**/*") -> int:
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


def mkdir(*paths: StrPath, mode: int = 0o777, exist_ok: bool = True) -> None:
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


def mv(src: StrPath, dst: StrPath) -> None:
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
            tmp_dst = _candidate_temp_pathname(path=dst, prefix="_")
            try:
                cp(src, tmp_dst)
                os.rename(tmp_dst, dst)
                rm(src)
            finally:
                rm(tmp_dst)
        else:
            raise


@t.overload
def read(file: StrPath, mode: ReadOnlyTextMode = "r", **open_kwargs: t.Any) -> str:
    ...  # pragma: no cover


@t.overload
def read(file: StrPath, mode: ReadOnlyBinMode, **open_kwargs: t.Any) -> bytes:
    ...  # pragma: no cover


@t.overload
def read(file: StrPath, mode: str = "r", **open_kwargs: t.Any) -> t.Union[str, bytes]:
    ...  # pragma: no cover


def read(file: StrPath, mode: str = "r", **open_kwargs: t.Any) -> t.Union[str, bytes]:
    """
    Return contents of file.

    Args:
        file: File to read.
        mode: File open mode.
        **open_kwargs: Additional keyword arguments to pass to ``open``.
    """
    if mode not in READ_ONLY_MODES:
        raise ValueError(f"Invalid read-only mode: {mode}")

    with open(file, mode, **open_kwargs) as fp:
        return fp.read()


def readbytes(file: StrPath, **open_kwargs: t.Any) -> bytes:
    """
    Return binary contents of file.

    Equivalent to calling :func:`read` with ``mode="rb"``.

    Args:
        file: File to read.
        **open_kwargs: Additional keyword arguments to pass to ``open``.
    """
    return read(file, "rb", **open_kwargs)


def readtext(file: StrPath, **open_kwargs: t.Any) -> str:
    """
    Return text contents of file.

    Equivalent to calling :func:`read` with ``mode="r"`` (the default behavior of :func:`read`).

    Args:
        file: File to read.
        **open_kwargs: Additional keyword arguments to pass to ``open``.
    """
    return read(file, "r", **open_kwargs)


@t.overload
def readchunks(
    file: StrPath,
    mode: ReadOnlyTextMode = "r",
    *,
    size: int = DEFAULT_CHUNK_SIZE,
    sep: t.Optional[str] = None,
    **open_kwargs: t.Any,
) -> t.Generator[str, None, None]:
    ...  # pragma: no cover


@t.overload
def readchunks(
    file: StrPath,
    mode: ReadOnlyBinMode,
    *,
    size: int = DEFAULT_CHUNK_SIZE,
    sep: t.Optional[bytes] = None,
    **open_kwargs: t.Any,
) -> t.Generator[bytes, None, None]:
    ...  # pragma: no cover


@t.overload
def readchunks(
    file: StrPath,
    mode: str = "r",
    *,
    size: int = DEFAULT_CHUNK_SIZE,
    sep: t.Optional[t.Union[str, bytes]] = None,
    **open_kwargs: t.Any,
) -> t.Generator[t.Union[str, bytes], None, None]:
    ...  # pragma: no cover


def readchunks(
    file: StrPath,
    mode: str = "r",
    *,
    size: int = DEFAULT_CHUNK_SIZE,
    sep: t.Optional[t.Union[str, bytes]] = None,
    **open_kwargs: t.Any,
) -> t.Generator[t.Union[str, bytes], None, None]:
    """
    Yield contents of file as chunks.

    If separator, `sep`, is not given, chunks will be yielded by `size`.

    If separator, `sep`, is given, chunks will be yielded from as if from ``contents.split(sep)``.
    The `size` argument will still be used for each file read operation, but the contents will be
    buffered until a separator is encountered.

    Args:
        file: File to read.
        mode: File open mode.
        size: Size of chunks to read from file at a time and chunk size to yield when `sep` not
            given.
        sep: Separator to split chunks by in lieu of splitting by size.
        **open_kwargs: Additional keyword arguments to pass to ``open``.
    """
    if mode not in READ_ONLY_MODES:
        raise ValueError(f"Invalid read-only mode: {mode}")
    return _readchunks(file, mode, size=size, sep=sep, **open_kwargs)


def _readchunks(file, mode="r", *, size=DEFAULT_CHUNK_SIZE, sep=None, **open_kwargs):
    buffer = ""
    if "b" in mode:
        buffer = b""

    with open(file, mode, **open_kwargs) as fp:
        try:
            while True:
                chunk = fp.read(size)

                if not chunk:
                    # We're done with the file but if we have anything in the buffer, yield it.
                    if buffer:
                        yield buffer
                    break
                elif not sep:
                    # Yield chunks delineated by size.
                    yield chunk
                else:
                    buffer += chunk
                    # Yield chunks delineated by separator.
                    while sep in buffer:
                        chunk, buffer = buffer.split(sep, 1)
                        yield chunk

        except GeneratorExit:  # pragma: no cover
            # Catch GeneratorExit to ensure contextmanager closes file when exiting generator early.
            pass


@t.overload
def readlines(
    file: StrPath, mode: ReadOnlyTextMode = "r", *, limit: int = -1, **open_kwargs: t.Any
) -> t.Generator[str, None, None]:
    ...  # pragma: no cover


@t.overload
def readlines(
    file: StrPath, mode: ReadOnlyBinMode, *, limit: int = -1, **open_kwargs: t.Any
) -> t.Generator[bytes, None, None]:
    ...  # pragma: no cover


@t.overload
def readlines(
    file: StrPath, mode: str = "r", *, limit: int = -1, **open_kwargs: t.Any
) -> t.Generator[t.Union[str, bytes], None, None]:
    ...  # pragma: no cover


def readlines(
    file: StrPath, mode: str = "r", *, limit: int = -1, **open_kwargs: t.Any
) -> t.Generator[t.Union[str, bytes], None, None]:
    """
    Yield each line of a file.

    Note:
        Line-endings are included in the yielded values.

    Args:
        file: File to read.
        mode: File open mode.
        limit: Maximum length of each line to yield. For example, ``limit=10`` will yield the first
            10 characters of each line.
        **open_kwargs: Additional keyword arguments to pass to ``open``.
    """
    if mode not in READ_ONLY_MODES:
        raise ValueError(f"Invalid read-only mode: {mode}")
    return _readlines(file, mode, limit=limit, **open_kwargs)


def _readlines(file, mode="r", *, limit=-1, **open_kwargs):
    sentinel = ""
    if "b" in mode:
        sentinel = b""

    with open(file, mode, **open_kwargs) as fp:
        try:
            yield from iter(lambda: fp.readline(limit), sentinel)
        except GeneratorExit:  # pragma: no cover
            # Catch GeneratorExit to ensure contextmanager closes file when exiting generator early.
            pass


def rm(*paths: StrPath) -> None:
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


def rmdir(*dirs: StrPath) -> None:
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


def rmfile(*files: StrPath) -> None:
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


def touch(*paths: StrPath) -> None:
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
def umask(mask: int = 0) -> t.Iterator[None]:
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


@t.overload
def write(
    file: StrPath,
    contents: str,
    mode: WriteOnlyTextMode = "w",
    *,
    atomic: bool = False,
    **open_kwargs: t.Any,
) -> None:
    ...  # pragma: no cover


@t.overload
def write(
    file: StrPath,
    contents: bytes,
    mode: WriteOnlyBinMode,
    *,
    atomic: bool = False,
    **open_kwargs: t.Any,
) -> None:
    ...  # pragma: no cover


@t.overload
def write(
    file: StrPath,
    contents: t.Union[str, bytes],
    mode: str = "w",
    *,
    atomic: bool = False,
    **open_kwargs: t.Any,
) -> None:
    ...  # pragma: no cover


def write(
    file: StrPath,
    contents: t.Union[str, bytes],
    mode: str = "w",
    *,
    atomic: bool = False,
    **open_kwargs: t.Any,
) -> None:
    """
    Write contents to file.

    Args:
        file: File to write.
        contents: Contents to write.
        mode: File open mode.
        atomic: Whether to write the file to a temporary location in the same directory before
            moving it to the destination.
        **open_kwargs: Additional keyword arguments to pass to ``open``.
    """
    if mode not in WRITE_ONLY_MODES:
        raise ValueError(f"Invalid write-only mode: {mode}")

    opener = open
    if atomic:
        overwrite = "x" not in mode
        mode = mode.replace("x", "w")
        opener = partial(atomicfile, overwrite=overwrite)  # type: ignore

    with opener(file, mode, **open_kwargs) as fp:
        fp.write(contents)


def writetext(
    file: StrPath, contents: str, mode: str = "w", *, atomic: bool = False, **open_kwargs: t.Any
) -> None:
    """
    Write text contents to file.

    Args:
        file: File to write.
        contents: Contents to write.
        mode: File open mode.
        atomic: Whether to write the file to a temporary location in the same directory before
            moving it to the destination.
        **open_kwargs: Additional keyword arguments to pass to ``open``.
    """
    if mode not in WRITE_ONLY_TEXT_MODES:
        raise ValueError(f"Invalid write-only text-mode: {mode}")
    write(file, contents, mode, atomic=atomic, **open_kwargs)


def writebytes(
    file: StrPath, contents: bytes, mode: str = "wb", *, atomic: bool = False, **open_kwargs: t.Any
) -> None:
    """
    Write binary contents to file.

    Args:
        file: File to write.
        contents: Contents to write.
        mode: File open mode.
        atomic: Whether to write the file to a temporary location in the same directory before
            moving it to the destination.
        **open_kwargs: Additional keyword arguments to pass to ``open``.
    """
    if mode not in WRITE_ONLY_BIN_MODES:
        raise ValueError(f"Invalid write-only binary-mode: {mode}")
    write(file, contents, mode, atomic=atomic, **open_kwargs)


@t.overload
def writelines(
    file: StrPath,
    items: t.Iterable[str],
    mode: WriteOnlyTextMode = "w",
    *,
    ending: t.Optional[str] = None,
    atomic: bool = False,
    **open_kwargs: t.Any,
) -> None:
    ...  # pragma: no cover


@t.overload
def writelines(
    file: StrPath,
    items: t.Iterable[bytes],
    mode: WriteOnlyBinMode,
    *,
    ending: t.Optional[bytes] = None,
    atomic: bool = False,
    **open_kwargs: t.Any,
) -> None:
    ...  # pragma: no cover


@t.overload
def writelines(
    file: StrPath,
    items: t.Union[t.Iterable[str], t.Iterable[bytes]],
    mode: str = "w",
    *,
    ending: t.Optional[t.Union[str, bytes]] = None,
    atomic: bool = False,
    **open_kwargs: t.Any,
) -> None:
    ...  # pragma: no cover


def writelines(
    file: StrPath,
    items: t.Union[t.Iterable[str], t.Iterable[bytes]],
    mode: str = "w",
    *,
    ending: t.Optional[t.Union[str, bytes]] = None,
    atomic: bool = False,
    **open_kwargs: t.Any,
) -> None:
    """
    Write lines to file.

    Args:
        file: File to write.
        items: Items to write.
        mode: File open mode.
        ending: Line ending to use. Defaults to newline.
        atomic: Whether to write the file to a temporary location in the same directory before
            moving it to the destination.
        **open_kwargs: Additional keyword arguments to pass to ``open``.
    """
    if mode not in WRITE_ONLY_MODES:
        raise ValueError(f"Invalid write-only mode: {mode}")

    if ending is None:
        ending = "\n"
        if "b" in mode:
            ending = b"\n"

    opener = open
    if atomic:
        overwrite = "x" not in mode
        mode = mode.replace("x", "w")
        opener = partial(atomicfile, overwrite=overwrite)  # type: ignore

    lines = (item + ending for item in items)  # type: ignore
    with opener(file, mode, **open_kwargs) as fp:
        fp.writelines(lines)


def _candidate_temp_pathname(
    path: StrPath = "", prefix: StrPath = "", suffix: StrPath = "", hidden: bool = True
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
    path: StrPath = "", prefix: StrPath = "", suffix: StrPath = "", length: int = 8
) -> str:
    _pid, _random = getattr(_random_name, "_state", (None, None))
    if _pid != os.getpid() or not _random:
        # Ensure separate processes don't share same random generator.
        _random = random.Random()
        _random_name._state = (os.getpid(), _random)  # type: ignore

    inner = "".join(_random.choice(string.ascii_letters) for _ in range(length))
    return f"{path}{prefix}{inner}{suffix}"
