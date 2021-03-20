"""
The shelmet package.

A shell power-up for working with the file system and running subprocess commands.
"""

__version__ = "0.5.0"

from .archiving import ArchiveError, archive, unarchive
from .command import Command, cmd, run
from .fileio import (
    atomicdir,
    atomicfile,
    read,
    readbytes,
    readchunks,
    readlines,
    readtext,
    write,
    writebytes,
    writelines,
    writetext,
)
from .filesystem import (
    backup,
    chmod,
    chown,
    cp,
    dirsync,
    environ,
    fsync,
    getdirsize,
    mkdir,
    mv,
    rm,
    rmdir,
    rmfile,
    touch,
    umask,
)
from .path import cd, cwd, homedir, ls, lsdirs, lsfiles, reljoin, walk, walkdirs, walkfiles
