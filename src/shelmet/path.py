"""The path module contains utilities for working with OS paths."""

from contextlib import contextmanager
import fnmatch
import os
from pathlib import Path
import typing as t
from typing import Iterable

from .types import LsFilter, LsFilterable, LsFilterFn, StrPath


@contextmanager
def cd(path: StrPath) -> t.Iterator[None]:
    """
    Context manager that changes the working directory on enter and restores it on exit.

    Args:
        path: Directory to change to.
    """
    orig_cwd = os.getcwd()

    if path:
        os.chdir(path)

    try:
        yield
    finally:
        if path:
            os.chdir(orig_cwd)


def cwd() -> Path:
    """Return current working directory as ``Path`` object."""
    return Path.cwd()


def homedir():
    """Return current user's home directory as ``Path`` object."""
    return Path.home()


def ls(
    path: StrPath = ".",
    *,
    recursive: bool = False,
    only_files: bool = False,
    only_dirs: bool = False,
    include: t.Optional[LsFilter] = None,
    exclude: t.Optional[LsFilter] = None,
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
    path: StrPath = ".",
    *,
    include: t.Optional[LsFilter] = None,
    exclude: t.Optional[LsFilter] = None,
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
    path: StrPath = ".",
    *,
    include: t.Optional[LsFilter] = None,
    exclude: t.Optional[LsFilter] = None,
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
    path: StrPath = ".",
    *,
    recursive: bool = False,
    include_filters: t.Optional[t.List[LsFilterFn]] = None,
    exclude_filters: t.Optional[t.List[LsFilterFn]] = None,
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
    only_files: bool = False, only_dirs: bool = False, filterable: t.Optional[LsFilterable] = None
) -> LsFilterFn:
    filter_fn: t.Optional[LsFilterFn] = None
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


def _make_ls_filterable_fn(filterable: LsFilterable) -> LsFilterFn:
    _ls_filterable_fn: LsFilterFn

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


def reljoin(*paths: StrPath) -> str:
    """
    Like ``os.path.join`` except that all paths are treated as relative to the previous one so that
    an absolute path in the middle will extend the existing path instead of becoming the new root
    path.

    Args:
        *paths: Paths to join together.
    """
    path = os.sep.join(str(Path(path)) for path in paths)
    return os.path.normpath(path)


def walk(
    path: StrPath = ".",
    *,
    only_files: bool = False,
    only_dirs: bool = False,
    include: t.Optional[LsFilter] = None,
    exclude: t.Optional[LsFilter] = None,
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
    path: StrPath = ".",
    *,
    include: t.Optional[LsFilter] = None,
    exclude: t.Optional[LsFilter] = None,
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
    path: StrPath = ".",
    *,
    include: t.Optional[LsFilter] = None,
    exclude: t.Optional[LsFilter] = None,
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
