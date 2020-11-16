"""The sh module contains utilities for interacting with files, directories, and the file system."""

from collections.abc import Iterable
from contextlib import contextmanager
import errno
import fnmatch
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
T_LS_FILTER_FN = t.Callable[[Path], bool]
T_LS_FILTERABLE = t.Union[str, t.Pattern, T_LS_FILTER_FN]
T_LS_FILTER = t.Union[T_LS_FILTERABLE, t.Iterable[T_LS_FILTERABLE]]


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


def ls(
    path: T_PATHLIKE = ".",
    *,
    recursive: bool = False,
    only_files: bool = False,
    only_dirs: bool = False,
    include: t.Optional[T_LS_FILTER] = None,
    exclude: t.Optional[T_LS_FILTER] = None,
) -> t.Generator[Path, None, None]:
    """
    Yield directory contents as ``Path`` objects.

    Args:
        path: Directory to list
        recursive: Whether to recurse into subdirectories. Defaults to ``False``.
        only_files: Limit results to files only. Mutually exclusive with ``only_dirs``.
        only_dirs: Limit results to directories only. Mutually exclusive with ``only_files``.
        include: Include paths by filtering on a glob-pattern string, compiled regex, callable, or
            iterable containing any of those types. Path is yielded if any of the filters return
            ``True`` and path matches ``only_files`` or ``only_dirs`` if set. If path is a directory
            and is not included, its contents are still eligible for inclusion if they match one of
            the include filters.
        exclude: Exclude paths by filtering on a glob-pattern string, compiled regex, callable, or
            iterable containing any of those types. Path is not yielded if any of the filters return
            ``True``. If the path is a directory and is excluded, then none of its contents will be
            yielded.

    Yields:
        Contents of directory.
    """
    if only_files and only_dirs:
        raise ValueError("only_files and only_dirs cannot both be true")

    include_filters: t.List[t.Callable[[Path], bool]] = []
    exclude_filters: t.List[t.Callable[[Path], bool]] = []

    if include:
        if isinstance(include, Iterable) and not isinstance(include, (str, bytes)):
            includes = include
        else:
            includes = [include]
        # When creating the include filters, need to also take into account the only_* filter
        # settings so that an include filter will only match if both are true.
        include_filters.extend(
            _make_ls_filter(only_files=only_files, only_dirs=only_dirs, filterable=incl)
            for incl in includes
        )
    elif only_files or only_dirs:
        # If no include filters are given, but one of the only_* filters is, then we'll add it.
        # Otherwise, when include is given, the only_* filters are taken into account for each
        # include filter.
        include_filters.append(_make_ls_filter(only_files=only_files, only_dirs=only_dirs))

    if exclude:
        if isinstance(exclude, Iterable) and not isinstance(exclude, (str, bytes)):
            excludes = exclude
        else:
            excludes = [exclude]
        exclude_filters.extend(_make_ls_filter(filterable=excl) for excl in excludes)

    yield from _ls(
        path, recursive=recursive, include_filters=include_filters, exclude_filters=exclude_filters
    )


def lsfiles(
    path: T_PATHLIKE = ".",
    *,
    include: t.Optional[T_LS_FILTER] = None,
    exclude: t.Optional[T_LS_FILTER] = None,
) -> t.Generator[Path, None, None]:
    """
    Yield only files in directory as ``Path`` objects.

    See Also:
        This function is not recursive and will only yield the top-level contents of a directory.
        Use :func:`.walkfiles` to recursively yield all files from a directory.

    Args:
        path: Directory to list
        include: Include paths by filtering on a glob-pattern string, compiled regex, callable, or
            iterable containing any of those types. Path is yielded if any of the filters return
            ``True`` and path matches ``only_files`` or ``only_dirs`` if set. If path is a directory
            and is not included, its contents are still eligible for inclusion if they match one of
            the include filters.
        exclude: Exclude paths by filtering on a glob-pattern string, compiled regex, callable, or
            iterable containing any of those types. Path is not yielded if any of the filters return
            ``True``. If the path is a directory and is excluded, then none of its contents will be
            yielded.

    Yields:
        Files in directory.
    """
    yield from ls(path, only_files=True, include=include, exclude=exclude)


def lsdirs(
    path: T_PATHLIKE = ".",
    *,
    include: t.Optional[T_LS_FILTER] = None,
    exclude: t.Optional[T_LS_FILTER] = None,
) -> t.Generator[Path, None, None]:
    """
    Yield only directories in directory as ``Path`` objects.

    See Also:
        This function is not recursive and will only yield the top-level contents of a directory.
        Use :func:`.walkdirs` to recursively yield all directories from a directory.

    Args:
        path: Directory to list
        include: Include paths by filtering on a glob-pattern string, compiled regex, callable, or
            iterable containing any of those types. Path is yielded if any of the filters return
            ``True`` and path matches ``only_files`` or ``only_dirs`` if set. If path is a directory
            and is not included, its contents are still eligible for inclusion if they match one of
            the include filters.
        exclude: Exclude paths by filtering on a glob-pattern string, compiled regex, callable, or
            iterable containing any of those types. Path is not yielded if any of the filters return
            ``True``. If the path is a directory and is excluded, then none of its contents will be
            yielded.

    Yields:
        Directories in directory.
    """
    yield from ls(path, only_dirs=True, include=include, exclude=exclude)


def _ls(
    path: T_PATHLIKE = ".",
    *,
    recursive: bool = False,
    include_filters: t.Optional[t.List[T_LS_FILTER_FN]] = None,
    exclude_filters: t.Optional[t.List[T_LS_FILTER_FN]] = None,
) -> t.Generator[Path, None, None]:
    scanner = os.scandir(Path(path))
    recurse_into: t.List[str] = []

    with scanner:
        while True:
            try:
                try:
                    entry = next(scanner)
                except StopIteration:
                    break
            except OSError:  # pragma: no cover
                return

            entry_path = Path(entry.path)
            excluded = exclude_filters and any(
                is_excluded(entry_path) for is_excluded in exclude_filters
            )

            if not excluded and (
                not include_filters
                or any(is_included(entry_path) for is_included in include_filters)
            ):
                yield entry_path

            if recursive and not excluded and entry_path.is_dir() and not entry_path.is_symlink():
                recurse_into.append(entry.path)

    for subdir in recurse_into:
        yield from _ls(
            subdir,
            recursive=recursive,
            include_filters=include_filters,
            exclude_filters=exclude_filters,
        )


def _make_ls_filter(
    only_files: bool = False,
    only_dirs: bool = False,
    filterable: t.Optional[T_LS_FILTERABLE] = None,
) -> T_LS_FILTER_FN:
    filter_fn: t.Optional[T_LS_FILTER_FN] = None
    if filterable:
        filter_fn = _make_ls_filterable_fn(filterable)

    def _ls_filter(path: Path) -> bool:
        if only_files and path.is_dir():
            return False
        elif only_dirs and path.is_file():
            return False
        elif filter_fn:
            return filter_fn(path)
        else:
            return True

    return _ls_filter


def _make_ls_filterable_fn(filterable: T_LS_FILTERABLE) -> T_LS_FILTER_FN:
    _ls_filterable_fn: T_LS_FILTER_FN

    if isinstance(filterable, str):

        def _ls_filterable_fn(path: Path) -> bool:
            return fnmatch.fnmatch(path, filterable)  # type: ignore

    elif isinstance(filterable, t.Pattern):

        def _ls_filterable_fn(path: Path) -> bool:
            return bool(filterable.match(str(path)))  # type: ignore

    elif callable(filterable):

        def _ls_filterable_fn(path: Path) -> bool:
            return filterable(path)  # type: ignore

    else:
        raise TypeError(
            f"ls filter must be one of str, re.compile() or callable, not {type(filterable)!r}"
        )

    return _ls_filterable_fn


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


def walk(
    path: T_PATHLIKE = ".",
    *,
    only_files: bool = False,
    only_dirs: bool = False,
    include: t.Optional[T_LS_FILTER] = None,
    exclude: t.Optional[T_LS_FILTER] = None,
) -> t.Generator[Path, None, None]:
    """
    Recursively yield all directory contents as ``Path`` objects.

    See Also:
        This function is recursive and will yield all contents of a directory. Use :func:`.ls` to
        yield only the top-level contents of a directory.

    Args:
        path: Directory to list
        only_files: Limit results to files only. Mutually exclusive with ``only_dirs``.
        only_dirs: Limit results to directories only. Mutually exclusive with ``only_files``.
        include: Include paths by filtering on a glob-pattern string, compiled regex, callable, or
            iterable containing any of those types. Path is yielded if any of the filters return
            ``True`` and path matches ``only_files`` or ``only_dirs`` if set. If path is a directory
            and is not included, its contents are still eligible for inclusion if they match one of
            the include filters.
        exclude: Exclude paths by filtering on a glob-pattern string, compiled regex, callable, or
            iterable containing any of those types. Path is not yielded if any of the filters return
            ``True``. If the path is a directory and is excluded, then none of its contents will be
            yielded.

    Yields:
        Contents of directory.
    """
    yield from ls(
        path,
        recursive=True,
        only_files=only_files,
        only_dirs=only_dirs,
        include=include,
        exclude=exclude,
    )


def walkfiles(
    path: T_PATHLIKE = ".",
    *,
    include: t.Optional[T_LS_FILTER] = None,
    exclude: t.Optional[T_LS_FILTER] = None,
) -> t.Generator[Path, None, None]:
    """
    Recursively yield only files in directory as ``Path`` objects.

    See Also:
        This function is recursive and will yield all files in a directory. Use :func:`.lsfiles` to
        yield only the top-level files in a directory.

    Args:
        path: Directory to list
        include: Include paths by filtering on a glob-pattern string, compiled regex, callable, or
            iterable containing any of those types. Path is yielded if any of the filters return
            ``True`` and path matches ``only_files`` or ``only_dirs`` if set. If path is a directory
            and is not included, its contents are still eligible for inclusion if they match one of
            the include filters.
        exclude: Exclude paths by filtering on a glob-pattern string, compiled regex, callable, or
            iterable containing any of those types. Path is not yielded if any of the filters return
            ``True``. If the path is a directory and is excluded, then none of its contents will be
            yielded.

    Yields:
        Files in directory.
    """
    yield from walk(path, only_files=True, include=include, exclude=exclude)


def walkdirs(
    path: T_PATHLIKE = ".",
    *,
    include: t.Optional[T_LS_FILTER] = None,
    exclude: t.Optional[T_LS_FILTER] = None,
) -> t.Generator[Path, None, None]:
    """
    Recursively yield only directories in directory as ``Path`` objects.

    See Also:
        This function is recursive and will yield all directories in a directory. Use
        :func:`.lsfiles` to yield only the top-level directories in a directory.

    Args:
        path: Directory to list
        include: Include paths by filtering on a glob-pattern string, compiled regex, callable, or
            iterable containing any of those types. Path is yielded if any of the filters return
            ``True`` and path matches ``only_files`` or ``only_dirs`` if set. If path is a directory
            and is not included, its contents are still eligible for inclusion if they match one of
            the include filters.
        exclude: Exclude paths by filtering on a glob-pattern string, compiled regex, callable, or
            iterable containing any of those types. Path is not yielded if any of the filters return
            ``True``. If the path is a directory and is excluded, then none of its contents will be
            yielded.

    Yields:
        Directories in directory.
    """
    yield from walk(path, only_dirs=True, include=include, exclude=exclude)


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
