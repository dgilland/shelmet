"""The filesystem module contains utilities for interacting with the file system."""

from contextlib import contextmanager
from datetime import datetime, timezone
import errno
import itertools
import os
from pathlib import Path
import random
import re
import shutil
import stat
import string
import typing as t

from .types import StrPath


try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore


CHMOD_SYMBOLIC_PATTERN = re.compile(r"^(?P<who>[ugoa]*)(?P<op>[+\-=])(?P<perm>[ugo]|[rwxst]*)$")
CHMOD_SYMBOLIC_TABLE: t.Dict[str, int] = {
    "ur": stat.S_IRUSR,
    "uw": stat.S_IWUSR,
    "ux": stat.S_IXUSR,
    "us": stat.S_ISUID,
    "gr": stat.S_IRGRP,
    "gw": stat.S_IWGRP,
    "gx": stat.S_IXGRP,
    "gs": stat.S_ISGID,
    "or": stat.S_IROTH,
    "ow": stat.S_IWOTH,
    "ox": stat.S_IXOTH,
    "ot": stat.S_ISVTX,
    "ar": stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH,
    "aw": stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH,
    "ax": stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH,
    "at": stat.S_ISVTX,
    "u": stat.S_IRWXU | stat.S_ISUID,
    "g": stat.S_IRWXG | stat.S_ISGID,
    "o": stat.S_IRWXO | stat.S_ISVTX,
}


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


def chmod(
    path: t.Union[StrPath, int], mode: t.Union[str, int], *, follow_symlinks: bool = True
) -> None:
    """
    Change file or directory permissions using numeric or symbolic modes.

    The mode can either be an integer, an octal number (e.g. ``0o600``), an octal string
    (e.g. ``"600"``), or a symbolic permissions string (e.g. ``"u+rw,g=r,o-rwx"``).

    The symbolic permissions string format is similar to what is accepted by the UNIX command
    ``chmod``:

    - Symbolic format: ``[ugoa...][-+=][rwxstugo...][,...]``
    - ``[ugoa...]``: Optional zero or more characters that set the user class parameter.

      - ``u``: user
      - ``g``: group
      - ``o``: other
      - ``a``: all
      - Defaults to ``a`` when none given

    - ``[-+=]``: Required operation that modifies the permissions.

      - ``-``: removes the given permissions
      - ``+``: adds the given permissions
      - ``=``: sets the given permissions to what was specified
      - If ``=`` is used without permissions, then the user class will have all of its permissions
        removed

    - ``[rwxstugo...]``: Permissions to modify for the given user classes.

      - ``r``: Read
      - ``w``: Write
      - ``x``: Execute
      - ``s``: User or Group ID bit
      - ``t``: Sticky bit
      - ``u``: User permission bits of the original path mode
      - ``g``: Group permission bits of the original path mode
      - ``o``: Other permission bits of the original path mode

    - Multiple permission clauses are separated with ``,``.

    Examples::

        # Set permissions to 600 using octal number.
        chmod(path, 0o600)

        # Set permissions to 600 using octal string.
        chmod(path, "600")

        # Set user to read-write, group to read, and remove read-write-execute from other
        chmod(path, "u=rw,g=r,o-rwx")

        # Set user, group, and other to read-write
        chmod(path, "a=rw")

        # Add execute permission for user, group, and other
        chmod(path, "+x")

        # Add user id bit, group id bit, and set sticky bit
        chmod(path, "u+s,g+s,+t")

        # Set group permission to same as user
        chmod(path, "g=u")

    Args:
        path: File, directory, or file-descriptor.
        mode: Permission mode to set.
        follow_symlinks: Whether to follow symlinks.
    """
    if isinstance(mode, str):
        # Attempt to convert mode from octal string to integer to support values like "640".
        try:
            mode = int(mode, 8)
        except (ValueError, TypeError):
            pass

    if isinstance(mode, str):
        # Process mode as symbolic permissions like "ug=rw,o=r".
        if isinstance(path, int):
            path_stat = os.stat(path)
        else:
            path_stat = Path(path).stat()
        mode = _get_symbolic_mode(path_stat.st_mode, mode)

    os.chmod(path, mode, follow_symlinks=follow_symlinks)


def _get_symbolic_mode(base_mode: int, symbolic_mode: str) -> int:
    mode = base_mode
    items = symbolic_mode.split(",")

    for item in items:
        match = CHMOD_SYMBOLIC_PATTERN.match(item)

        if not match:
            raise ValueError(f"chmod: Unsupported symbolic mode: {symbolic_mode}")

        who = match.group("who")
        op = match.group("op")
        perm = match.group("perm")

        if not who:
            who = "a"

        mask = 0
        for who_char, perm_char in itertools.product(who, perm):
            if perm_char in "ugo":
                # Permission character is a who-class that we should inherit permissions from.
                submask = _get_inherited_symbolic_mode(mode, to_who=who_char, from_who=perm_char)
            else:
                symbol = who_char + perm_char
                if symbol not in CHMOD_SYMBOLIC_TABLE:
                    raise ValueError(f"chmod: Unsupported symbolic mode: {symbolic_mode}")
                submask = CHMOD_SYMBOLIC_TABLE[symbol]
            mask |= submask

        if op == "=":
            # Since we're setting permissions to be equal to the given mode, clear the existing
            # mode for each "who" so that its permissions will be set to just what was given.
            mode = _clear_symbolic_mode(mode, who)

        if op == "-":
            mode &= ~mask
        else:
            # Handles both "=" and "+" operators.
            mode |= mask

    return mode


def _get_inherited_symbolic_mode(base_mode: int, to_who: str, from_who: str) -> int:
    mode = 0
    for perm_char in "rwxst":
        from_symbol = from_who + perm_char
        to_symbol = to_who + perm_char
        if (
            from_symbol in CHMOD_SYMBOLIC_TABLE
            and to_symbol in CHMOD_SYMBOLIC_TABLE
            and base_mode & CHMOD_SYMBOLIC_TABLE[from_symbol]
        ):
            mode |= CHMOD_SYMBOLIC_TABLE[to_symbol]
    return mode


def _clear_symbolic_mode(mode: int, who: str) -> int:
    for who_char, perm_char in itertools.product(who, "rwxst"):
        symbol = who_char + perm_char
        if symbol not in CHMOD_SYMBOLIC_TABLE:
            continue
        mode &= ~CHMOD_SYMBOLIC_TABLE[who_char + perm_char]
    return mode


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
