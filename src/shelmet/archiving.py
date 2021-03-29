"""The archiving module contains utilities for interacting with archive files."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import errno
import os
from pathlib import Path, PurePath
import tarfile
from types import TracebackType
import typing as t
import zipfile

from .fileio import atomicfile
from .filesystem import cp
from .path import Ls, walk
from .types import StrPath


try:
    import zlib
except ImportError:  # pragma: no cover
    zlib = None  # type: ignore


# Use same default tar format for older Python versions for consistency (default was changed to PAX
# in 3.8).
# NOTE: This format is only used for writing and doesn't affect reading archives in other formats.
DEFAULT_TAR_FORMAT = tarfile.PAX_FORMAT

# Use ZIP_DEFLATED as default zipfile compression if available.
DEFAULT_ZIP_COMPRESSION = zipfile.ZIP_DEFLATED if zlib else zipfile.ZIP_STORED

# Archive names to exclude when adding to an archive.
EXCLUDE_ARCNAMES = {".", ".."}


class ArchiveError(Exception):
    """General archive error."""

    def __init__(self, *args: t.Any, orig_exc: t.Optional[Exception] = None):
        super().__init__(*args)
        self.orig_exc = orig_exc


class UnsafeArchiveError(ArchiveError):
    """Unsafe archive exception raised when an untrusted archive would extract contents outside of
    the destination directory."""

    pass


class ArchiveSource:
    """Iterable representation of a path that should be added to an archive."""

    def __init__(self, source: t.Union[StrPath, Ls]):
        path = Path(source).resolve()
        subpaths: t.Optional[Ls] = None

        if isinstance(source, Ls):
            subpaths = source
        elif path.is_dir():
            subpaths = walk(source)

        self.source = source
        self.path = path
        self.subpaths = subpaths

    def __repr__(self) -> str:
        if isinstance(self.source, Ls):
            source = repr(self.source)
        else:
            source = f"'{self.source}'"
        return f"{self.__class__.__name__}(source={source}, path='{self.path}')"

    def __str__(self) -> str:
        """Return string representation of archive source."""
        return str(self.source)

    def __iter__(self) -> t.Iterator[Path]:
        """Yield contents of archive source including the base path and its subpaths."""
        yield self.path

        if not self.subpaths:
            return

        for subpath in self.subpaths:
            yield Path(subpath).resolve()


class BaseArchive(ABC):
    """Abstract base class that provides a common interface for interacting with different archive
    formats."""

    def __init__(self, backend):
        self.backend = backend

    def __enter__(self) -> "BaseArchive":
        """Enter context manager when reading or writing an archive."""
        return self

    def __exit__(
        self,
        exc_type: t.Optional[t.Type[BaseException]],
        exc_val: t.Optional[BaseException],
        exc_tb: t.Optional[TracebackType],
    ) -> None:
        """Exit context manager after reading or writing an archive."""
        self.close()

    @classmethod
    @abstractmethod
    def open(cls, file: t.Union[StrPath, t.IO], mode: str = "r") -> "BaseArchive":
        """Open an archive file."""
        pass  # pragma: no cover

    @abstractmethod
    def close(self) -> None:
        """Close the archive file."""
        pass  # pragma: no cover

    @abstractmethod
    def list(self) -> t.List[str]:
        """Return a list of file/directory names contained in the archive."""
        pass  # pragma: no cover

    @abstractmethod
    def extractall(self, path: StrPath) -> None:
        """Extract all contents of the archive to the given path."""
        pass  # pragma: no cover

    @abstractmethod
    def add(self, path: StrPath, arcname: t.Optional[str] = None) -> None:
        """Add path to the archive non-recursively."""
        pass  # pragma: no cover

    def addsource(self, source: ArchiveSource, arcname: t.Optional[StrPath] = None) -> None:
        """Add file system contents of source to archive."""
        if arcname:
            arcname = Path(arcname)

        root_path_offset = len(source.path.parts)

        for path in source:
            if arcname:
                name = str(Path(arcname, *path.parts[root_path_offset:]))
            else:  # pragma: no cover
                name = str(path)

            if name in EXCLUDE_ARCNAMES:
                continue

            self.add(path, arcname=name)


class ZipArchive(BaseArchive):
    """Archive class for interacting with zip archives."""

    backend: zipfile.ZipFile

    @classmethod
    def open(cls, file: t.Union[StrPath, t.IO], mode: str = "r") -> "ZipArchive":
        """Open an archive file."""
        return cls(zipfile.ZipFile(file, mode, compression=DEFAULT_ZIP_COMPRESSION))

    def close(self):
        """Close the archive file."""
        self.backend.close()

    def list(self) -> t.List[str]:
        """Return a list of file/directory names contained in the archive."""
        return self.backend.namelist()

    def extractall(self, path: StrPath) -> None:
        """Extract all contents of the archive to the given path."""
        self.backend.extractall(path)

    def add(self, path: StrPath, arcname: t.Optional[str] = None) -> None:
        """Add path to the archive non-recursively."""
        if not isinstance(path, Path):  # pragma: no cover
            path = Path(path)

        if not arcname:  # pragma: no cover
            arcname = str(path)

        self.backend.write(path, arcname=arcname)


class TarArchive(BaseArchive):
    """Archive class for interacting with tar archives without compression."""

    backend: tarfile.TarFile
    compression = ""

    @classmethod
    def open(cls, file: t.Union[StrPath, t.IO], mode: str = "r") -> "TarArchive":
        """Open an archive file."""
        if mode == "w" and cls.compression:
            mode = f"{mode}:{cls.compression}"

        if isinstance(file, (str, bytes, Path)):
            tar = tarfile.open(file, mode=mode, format=DEFAULT_TAR_FORMAT)
        else:
            tar = tarfile.open(fileobj=file, mode=mode, format=DEFAULT_TAR_FORMAT)

        return cls(tar)

    def close(self):
        """Close the archive file."""
        self.backend.close()

    def list(self) -> t.List[str]:
        """Return a list of file/directory names contained in the archive."""
        return self.backend.getnames()

    def extractall(self, path: StrPath) -> None:
        """Extract all contents of the archive to the given path."""
        self.backend.extractall(path)

    def add(self, path: StrPath, arcname: t.Optional[str] = None) -> None:
        """Add path to the archive non-recursively."""
        self.backend.add(path, arcname=arcname, recursive=False)


class TarGzArchive(TarArchive):
    """Archive class for interacting with tar archives with gzip compression."""

    compression = "gz"


class TarBzArchive(TarArchive):
    """Archive class for interacting with tar archives with bzip2 compression."""

    compression = "bz2"


class TarXzArchive(TarArchive):
    """Archive class for interacting with tar archives with lzma compression."""

    compression = "xz"


EXTENSION_ARCHIVES: t.Dict[str, t.Type[BaseArchive]] = {
    # Extensions that use uncompressed tar.
    ".tar": TarArchive,
    # Extensions that use Tar+gz compression.
    ".tar.gz": TarGzArchive,
    ".tgz": TarGzArchive,
    ".taz": TarGzArchive,
    # Extensions that use tar+bz2 compression.
    ".tar.bz2": TarBzArchive,
    ".tb2": TarBzArchive,
    ".tbz": TarBzArchive,
    ".tbz2": TarBzArchive,
    ".tz2": TarBzArchive,
    # Extensions that use tar+xz compression.
    ".tar.xz": TarXzArchive,
    ".txz": TarXzArchive,
    # Extensions that use zip format.
    ".docx": ZipArchive,
    ".egg": ZipArchive,
    ".jar": ZipArchive,
    ".odg": ZipArchive,
    ".odp": ZipArchive,
    ".ods": ZipArchive,
    ".odt": ZipArchive,
    ".pptx": ZipArchive,
    ".xlsx": ZipArchive,
    ".zip": ZipArchive,
}


def archive(
    file: StrPath,
    *paths: t.Union[StrPath, Ls],
    root: t.Optional[StrPath] = None,
    repath: t.Optional[t.Union[str, t.Mapping[StrPath, StrPath]]] = None,
    ext: str = "",
) -> None:
    """
    Create an archive from the given source paths.

    The source paths can be relative or absolute but the path names inside the archive will always
    be relative. By default, the paths within the archive will be determined by taking the common
    path of all the sources and removing it from each source path so that the archive paths are all
    relative to the shared parent path of all sources. If `root` is given, it will be used in place
    of the dynamic common path determination, but it must be a parent path common to all sources.

    The archive member names of the source paths can be customized using the `repath` argument. The
    `repath` argument is a mapping of source paths to their custom archive name. If a source path is
    given as relative, then its repath key must also be relative. If a source path is given as
    absolute, then its repath key must also be absolute. The repath keys/values should be either
    strings or ``Path`` objects but they don't have to match the corresponding source path. Both the
    keys and values will have their path separators normalized.

    Archives can be created in either the tar or zip format. A tar archive can use the same
    compressions that are available from ``tarfile`` which are gzipped, bzip2, and lzma. A zip
    archive will use deflate compression if the ``zlib`` library is available. Otherwise, it will
    fallback to being uncompressed.

    The archive format is interfered from the file extension of `file` by default, but can be
    overridden using the `ext` argument (e.g. ``ext=".tgz"`` for a gzipped tarball).

    The supported tar-based extensions are:

    - ``.tar``
    - ``.tar.gz``, ``.tgz``, ``.taz``
    - ``.tar.bz2``, ``.tb2``, ``.tbz``, ``.tbz2``, ``.tz2``
    - ``.tar.xz``, ``.txz``

    The supported zip-based extensions are:

    - ``.zip``,
    - ``.egg``, ``.jar``
    - ``.docx``, ``pptx``, ``xlsx``
    - ``.odg``, ``.odp``, ``.ods``, ``.odt``

    Args:
        file: Archive file path to create.
        *paths: Source paths (files and/or directories) to archive. Directories will be recursively
            added.
        root: Archive member paths will be relative to this root directory. The root path must be a
            parent directory of all source paths, otherwise, an exception will be raised.
        repath: A mapping of source paths to archive names that will rename the source path to the
            mapped value within the archive. A string representing the archive member name can only
            be used when a single source path is being added to the archive.
        ext: Specify the archive format to use by referencing the corresponding file extension
            (starting with a leading ".") instead of interfering the format from the `file`
            extension.
    """
    file = Path(file)
    archive_class = _get_archive_class_or_raise(file, ext)

    if repath is None:
        repath = {}

    if isinstance(repath, str) and len(paths) > 1:
        raise TypeError("repath must be a dict when there is more than one archive source path")

    if not isinstance(repath, str) and not isinstance(repath, dict):
        raise TypeError("repath must be a string or dict")

    sources = [ArchiveSource(path) for path in paths]

    if isinstance(repath, str):
        repath = {str(sources[0]): Path(repath)}
    else:
        repath = {str(Path(src)): Path(pth) for src, pth in repath.items()}

    if root:
        root = Path(root).resolve()
    else:
        # The archive contents will be relative to the common path shared by all source paths.
        root = Path(os.path.commonpath([src.path for src in sources])).parent

    # Check that source paths are valid relative to root before adding archive members. No need to
    # check sources that are going to be repathed since their arcname won't depend on them being
    # relative to the root directory.
    _verify_archive_root(root, [source for source in sources if str(source) not in repath])

    # Use atomicfile so that archive is only created at location if there are no errors while
    # archiving all paths.
    with atomicfile(file, "wb", skip_sync=True) as fp:
        with archive_class.open(fp, "w") as archive_file:
            try:
                for source in sources:
                    arcname = repath.get(str(source))
                    if arcname is None:
                        arcname = str(source.path.relative_to(root))
                    archive_file.addsource(source, arcname=arcname)
            except Exception as exc:
                raise ArchiveError(
                    f"archive: Failed to create archive '{file}' due to error: {exc}", orig_exc=exc
                ) from exc


def backup(
    src: StrPath,
    *,
    timestamp: t.Optional[str] = "%Y-%m-%dT%H:%M:%S.%f%z",
    utc: bool = False,
    epoch: bool = False,
    prefix: str = "",
    suffix: str = "~",
    ext: t.Optional[str] = None,
    hidden: bool = False,
    overwrite: bool = False,
    dir: t.Optional[StrPath] = None,
    namer: t.Optional[t.Callable[[Path], StrPath]] = None,
) -> Path:
    """
    Create a backup of a file or directory as either a direct copy or an archive file.

    The format of the backup name is ``{prefix}{src}.{timestamp}{suffix|ext}``.

    By default, the backup will be created in the same parent directory as the source and be named
    like ``"src.YYYY-MM-DDThh:mm:ss.ffffff~"``, where the timestamp is the current local time.

    If `utc` is ``True``, then the timestamp will be in the UTC timezone.

    If `epoch` is ``True``, then the timestamp will be the Unix time as returned by
    ``time.time()`` instead of the strftime format.

    If `ext` is given, the backup created will be an archive file. The extension must be one that
    :func:`archive` supports. The `suffix` value will be ignored and `ext` used in its place.

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
        ext: Create an archive of `src` as the backup instead of a direct copy using the given
            archive extension. The extension must be supported by :func:`archive` or an exception
            will be raised. When given the `suffix` value is ignored and `ext` will be used in its
            place.
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

    if ext:
        suffix = ext

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

    if ext:
        archive(dst, src, ext=ext)
    else:
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
        dir = src.parent.resolve()
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


def lsarchive(file: StrPath, ext: str = "") -> t.List[PurePath]:
    """
    Return list of member paths contained in archive file.

    Args:
        file: Archive file to list.
        ext: Specify the archive format to use by referencing the corresponding file extension
            (starting with a leading ".") instead of interfering the format from the `file`
            extension.
    """
    file = Path(file)
    archive_class = _get_archive_class_or_raise(file, ext)
    with archive_class.open(file, "r") as archive_file:
        return [PurePath(item) for item in archive_file.list()]


def unarchive(file: StrPath, dst: StrPath = ".", *, ext: str = "", trusted: bool = False) -> None:
    """
    Extract an archive to the given destination path.

    If the archive contains any paths that would be extracted outside the destination path, an
    :class:`ArchiveError` will be raised to prevent untrusted archives from extracting contents to
    locations that may pose a security risk. To allow a trusted archive to extract contents outside
    the destination, use the argument ``trusted=True``.

    Archives can be extracted from either zip or tar formats with compression. The tar compressions
    available are the same as what is supported by ``tarfile`` which are gzipped, bzip2, and lzma.

    The archive format is interfered from the file extension of `file` by default, but can be
    overridden using the `ext` argument (e.g. ``ext=".tgz"`` for a gzipped tarball).

    The supported tar extensions are:

    - ``.tar``
    - ``.tar.gz``, ``.tgz``, ``.taz``
    - ``.tar.bz2``, ``.tb2``, ``.tbz``, ``.tbz2``, ``.tz2``
    - ``.tar.xz``, ``.txz``
    - ``.zip``,
    - ``.egg``, ``.jar``
    - ``.docx``, ``pptx``, ``xlsx``
    - ``.odg``, ``.odp``, ``.ods``, ``.odt``

    Args:
        file: Archive file to unarchive.
        dst: Destination directory to unarchive contents to.
        ext: Specify the archive format to use by referencing the corresponding file extension
            (starting with a leading ".") instead of interfering the format from the `file`
            extension.
        trusted: Whether the archive is safe and can be trusted to allow it to extract contents
            outside of the destination path. Only enable this for archives that have been verified
            as originating from a trusted source.
    """
    file = Path(file)
    archive_class = _get_archive_class_or_raise(file, ext)

    try:
        with archive_class.open(file, "r") as archive_file:
            if not trusted:
                _verify_archive_safety(archive_file, dst)
            archive_file.extractall(dst)
    except ArchiveError:  # pragma: no cover
        raise
    except Exception as exc:
        raise ArchiveError(
            f"unarchive: Failed to unarchive '{file}' due to error: {exc}", orig_exc=exc
        ) from exc


def _get_archive_class_or_raise(file: Path, ext: str = "") -> t.Type[BaseArchive]:
    """Return the :class:`BaseArchive` that should be used to handle an archive file or raise if
    none found."""
    archive_class = _get_archive_class(file, ext=ext)
    if not archive_class:
        raise NotImplementedError(f"Archive format not supported: {ext!r}")
    return archive_class


def _get_archive_class(file: Path, ext: str = "") -> t.Optional[t.Type[BaseArchive]]:
    """Return the :class:`BaseArchive` that should be used to handle an archive file."""
    archive_class = EXTENSION_ARCHIVES.get(ext)

    if not archive_class:
        archive_class = EXTENSION_ARCHIVES.get("".join(file.suffixes))

    if not archive_class:
        archive_class = next(
            (a for e, a in EXTENSION_ARCHIVES.items() if file.name.endswith(e)), None
        )

    return archive_class


def _verify_archive_root(root: Path, sources: t.List[ArchiveSource]) -> None:
    """Check whether archive root path is valid for sources before adding them to an archive."""
    for source in sources:
        try:
            source.path.relative_to(root)
        except ValueError:
            raise ValueError(
                f"Source paths must be a subpath of the root archive path. '{source.path}' is"
                f" not in the subpath of '{root}'"
            )


def _verify_archive_safety(archive_file: BaseArchive, dst: StrPath) -> None:
    """Check whether the archive contains paths that would be extracted outside the target path and
    raise an exception if it would."""
    dst = Path(dst).resolve()
    safe_path_prefix = str(dst)

    for name in archive_file.list():
        extraction_path = (dst / name).resolve()
        if not str(extraction_path).startswith(safe_path_prefix):
            raise UnsafeArchiveError(
                f"unarchive: Archive has member '{name}' whose destination is outside the"
                f" target directory '{dst}' and cannot be extracted unless it is designated as"
                f" originating from a trusted source with 'trusted=True`."
            )
