"""The fileio module contains utilities for file IO."""

from contextlib import contextmanager
import errno
from functools import partial
import io
import os
from pathlib import Path
import typing as t

from .filesystem import _candidate_temp_pathname, dirsync, fsync, mkdir, rm
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


@t.overload
def read(file: StrPath, mode: ReadOnlyTextMode, **open_kwargs: t.Any) -> str:
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
    mode: ReadOnlyTextMode,
    *,
    size: int = ...,
    sep: t.Optional[str] = ...,
    **open_kwargs: t.Any,
) -> t.Generator[str, None, None]:
    ...  # pragma: no cover


@t.overload
def readchunks(
    file: StrPath,
    mode: ReadOnlyBinMode,
    *,
    size: int = ...,
    sep: t.Optional[bytes] = ...,
    **open_kwargs: t.Any,
) -> t.Generator[bytes, None, None]:
    ...  # pragma: no cover


@t.overload
def readchunks(
    file: StrPath,
    mode: str = "r",
    *,
    size: int = ...,
    sep: t.Optional[t.Union[str, bytes]] = ...,
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
    file: StrPath, mode: ReadOnlyTextMode, *, limit: int = ..., **open_kwargs: t.Any
) -> t.Generator[str, None, None]:
    ...  # pragma: no cover


@t.overload
def readlines(
    file: StrPath, mode: ReadOnlyBinMode, *, limit: int = ..., **open_kwargs: t.Any
) -> t.Generator[bytes, None, None]:
    ...  # pragma: no cover


@t.overload
def readlines(
    file: StrPath, mode: str = "r", *, limit: int = ..., **open_kwargs: t.Any
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


@t.overload
def write(
    file: StrPath,
    contents: str,
    mode: WriteOnlyTextMode,
    *,
    atomic: bool = ...,
    **open_kwargs: t.Any,
) -> None:
    ...  # pragma: no cover


@t.overload
def write(
    file: StrPath,
    contents: bytes,
    mode: WriteOnlyBinMode,
    *,
    atomic: bool = ...,
    **open_kwargs: t.Any,
) -> None:
    ...  # pragma: no cover


@t.overload
def write(
    file: StrPath,
    contents: t.Union[str, bytes],
    mode: str = "w",
    *,
    atomic: bool = ...,
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
    mode: WriteOnlyTextMode,
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
