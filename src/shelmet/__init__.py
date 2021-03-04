"""
The shelmet package.

A shell power-up for working with the file system and running subprocess commands.
"""

from .__version__ import __version__
from .command import Command, cmd, run
from .filesystem import (
    atomicdir,
    atomicfile,
    backup,
    cp,
    dirsync,
    environ,
    fsync,
    getdirsize,
    mkdir,
    mv,
    read,
    readbytes,
    readchunks,
    readlines,
    readtext,
    rm,
    rmdir,
    rmfile,
    touch,
    umask,
    write,
    writebytes,
    writelines,
    writetext,
)
from .path import cd, cwd, homedir, ls, lsdirs, lsfiles, reljoin, walk, walkdirs, walkfiles
