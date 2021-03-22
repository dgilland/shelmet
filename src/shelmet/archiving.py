"""The archiving module contains utilities for interacting with archive files."""

from abc import ABC, abstractmethod
import os
from pathlib import Path
import tarfile
from types import TracebackType
import typing as t
import zipfile

from .fileio import atomicfile
from .path import walk
from .types import StrPath


class ArchiveError(Exception):
    """General archive error."""

    def __init__(self, *args: t.Any, orig_exc: t.Optional[Exception] = None):
        super().__init__(*args)
        self.orig_exc = orig_exc


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
    def open(cls, file: t.Union[StrPath, t.BinaryIO], mode: str = "r") -> "BaseArchive":
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

    def archive(self, *paths: StrPath) -> None:
        """Create the archive that contains the given source paths."""
        # The archive contents will be relative to the common path shared by all source paths.
        absolute_paths = [Path(path).absolute() for path in paths]
        common_path = Path(os.path.commonpath(absolute_paths)).parent

        for path in absolute_paths:
            self.add(path, arcname=str(path.relative_to(common_path)))

            if path.is_dir():
                for subpath in walk(path):
                    self.add(subpath, arcname=str(subpath.relative_to(common_path)))

    def unarchive(self, dst: StrPath, *, trusted: bool = False) -> None:
        """Extract the archive to the destination path."""
        if not trusted:
            self.verify_unarchive_safety(dst)
        self.extractall(dst)

    def verify_unarchive_safety(self, dst: StrPath) -> None:
        """Check whether the archive contains paths that would be extracted outside the target path
        and raise an exception if it would."""
        dst = Path(dst).resolve()
        safe_path_prefix = str(dst)

        for name in self.list():
            extraction_path = (dst / name).resolve()
            if not str(extraction_path).startswith(safe_path_prefix):
                raise ArchiveError(
                    f"unarchive: Archive has member '{name}' whose destination is outside the"
                    f" target directory '{dst}' and cannot be extracted unless it is designated as"
                    f" originating from a trusted source with 'trusted=True`."
                )


class ZipArchive(BaseArchive):
    """Archive class for interacting with zip archives."""

    backend: zipfile.ZipFile

    @classmethod
    def open(cls, file: t.Union[StrPath, t.BinaryIO], mode: str = "r") -> "ZipArchive":
        """Open an archive file."""
        return cls(zipfile.ZipFile(file, mode))

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
    def open(cls, file: t.Union[StrPath, t.BinaryIO], mode: str = "r") -> "TarArchive":
        """Open an archive file."""
        if mode == "w" and cls.compression:
            mode = f"{mode}:{cls.compression}"

        if isinstance(file, (str, bytes, Path)):
            tar = tarfile.open(file, mode=mode)
        else:
            tar = tarfile.open(fileobj=file, mode=mode)

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


def archive(file: StrPath, *paths: StrPath, ext: str = "") -> None:
    """
    Create an archive from the given source paths.

    The source paths can be relative or absolute paths but the path names inside the archive will
    always be relative. The paths within the archive will be determined by taking the common path
    of all the sources and removing it from each source path so that the archive paths are all
    relative to the shared parent path of all sources.

    Archives can be created in either zip or tar format with compression. The tar compressions
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
        file: Archive file path to create.
        *paths: Source paths (files and/or directories) to archive. Directories will be recursively
            added.
        ext: Specify the archive format to use by referencing the corresponding file extension
            (starting with a leading ".") instead of interfering the format from the `file`
            extension.
    """
    file = Path(file)
    archive_class = _get_archive_class_for_file(file, ext)

    # Use atomicfile so that archive is only created at location if there are no errors while
    # archiving all paths.
    with atomicfile(file, "wb", skip_sync=True) as fp:
        with archive_class.open(fp, "w") as archive_file:  # type: ignore
            try:
                archive_file.archive(*paths)
            except Exception as exc:
                raise ArchiveError(
                    f"archive: Failed to create archive '{file}' due to error: {exc}", orig_exc=exc
                ) from exc


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
    archive_class = _get_archive_class_for_file(file, ext)

    with archive_class.open(file, "r") as archive_file:
        try:
            archive_file.unarchive(dst, trusted=trusted)
        except ArchiveError:
            raise
        except Exception as exc:
            raise ArchiveError(
                f"unarchive: Failed to unarchive '{file}' due to error: {exc}", orig_exc=exc
            ) from exc


def _get_archive_class_for_file(file: Path, ext: str = "") -> t.Type[BaseArchive]:
    """Return the :class:`BaseArchive` that should be used to handle an archive file."""
    if not ext:
        ext = "".join(file.suffixes)
    archive_class = EXTENSION_ARCHIVES.get(ext)
    if not archive_class:
        raise ArchiveError(f"Archive format not supported: {ext!r}")
    return archive_class
