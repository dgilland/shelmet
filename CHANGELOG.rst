Changelog
=========


v0.5.0 (XXXX-XX-XX)
-------------------

- Import all utility functions into ``shelmet`` namespace.
- Remove ``shelmet.sh`` catch-all submodule in favor of splitting it into smaller submodules, ``shelmet.filesystem`` and ``shelmet.path``. Recommend using ``import shelmet as sh`` as primary usage pattern instead of importing submodules.  **breaking change**
- Add functions:

  - ``read``
  - ``readbytes``
  - ``readchunks``
  - ``readlines``
  - ``readtext``


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
