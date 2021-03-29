Changelog
=========


v0.6.0 (2021-03-29)
-------------------

- Change return type for ``ls``, ``lsfiles``, ``lsdirs``, ``walk``, ``walkfiles``, and ``walkdirs`` to an iterable class, ``Ls``. Previously, these functions were generators.
- Add option to backup to an archive file in ``backup``.
- Add functions:

  - ``archive``
  - ``chmod``
  - ``chown``
  - ``lsarchive``
  - ``unarchive``


v0.5.0 (2021-03-04)
-------------------

- Import all utility functions into ``shelmet`` namespace.
- Remove ``shelmet.sh`` catch-all submodule in favor of splitting it into smaller submodules, ``shelmet.filesystem`` and ``shelmet.path``. Recommend using ``import shelmet as sh`` as primary usage pattern instead of importing submodules.  **breaking change**
- Add functions:

  - ``backup``
  - ``read``
  - ``readbytes``
  - ``readchunks``
  - ``readlines``
  - ``readtext``
  - ``write``
  - ``writebytes``
  - ``writelines``
  - ``writetext``


v0.4.0 (2021-01-26)
-------------------

- Rename ``sh.command`` to ``sh.cmd``. **breaking change**
- Add methods to ``sh.Command`` / ``sh.command``:

  - ``Command.and_``
  - ``Command.or_``
  - ``Command.after``


v0.3.0 (2020-12-24)
-------------------

- Add to ``sh`` module:

  - ``Command``
  - ``command``
  - ``cwd``
  - ``homedir``
  - ``run``


v0.2.0 (2020-11-30)
-------------------

- Add to ``sh`` module:

  - ``atomicdir``

- Rename ``atomic_write`` to ``atomicfile``. **breaking change**


v0.1.0 (2020-11-16)
-------------------

- First release.
- Add ``sh`` module:

  - ``atomic_write``
  - ``cd``
  - ``cp``
  - ``dirsync``
  - ``environ``
  - ``fsync``
  - ``getdirsize``
  - ``ls``
  - ``lsdirs``
  - ``lsfiles``
  - ``mkdir``
  - ``mv``
  - ``reljoin``
  - ``rm``
  - ``rmdir``
  - ``rmfile``
  - ``touch``
  - ``umask``
  - ``walk``
  - ``walkdirs``
  - ``walkfiles``
