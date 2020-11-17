shelmet
*******

|version| |build| |coveralls| |license|


A collection of shell utilities


Links
=====

- Project: https://github.com/dgilland/shelmet
- Documentation: https://shelmet.readthedocs.io
- PyPI: https://pypi.python.org/pypi/shelmet/
- Github Actions: https://github.com/dgilland/shelmet/actions


Features
========

- Shell utilities like...

  - ``cp``, ``mv``, ``mkdir``, ``touch``
  - ``rm``, ``rmfile``, ``rmdir``
  - ``ls``, ``lsfiles``, ``lsdirs``
  - ``walk``, ``walkfiles``, ``walkdirs``
  - ``cd``, ``environ``
  - and more!

- 100% test coverage
- Fully type-annotated
- Python 3.6+


Quickstart
==========

Install using pip:


::

    pip3 install shelmet


Import the ``sh`` module:

.. code-block:: python

    from shelmet import sh


Perform some file operations:

.. code-block:: python

    # Make directories and sub-directories. Behaves like "$ mkdir -p"
    sh.mkdir("a", "b", "c", "d/e/f/g")

    # Context-manager to change working directory temporarily. Behaves like "$ cd".
    with sh.cd("d/e/f/g"):
        sh.touch("1.txt", "2.txt", "3.txt")

        # Move files or directories. Works across file-systems. Behaves like "$ mv".
        sh.mv("1.txt", "11.txt")

        # Copy files or directories. Behaves like "$ cp -r"
        sh.cp("2.txt", "22.txt")

        # List top-level directory contents.
        # NOTE: sh.ls() and its siblings are generators.
        list(sh.ls())

        # Limit to files.
        list(sh.lsfiles())

        # Limit to directories.
        list(sh.lsdirs())

        # Remove files.
        sh.rmfile("11.txt", "22.txt", "3.txt")
        # Or use sh.rm which handles both files and directories.
        sh.rm("11.txt", "22.txt", "3.txt")

    # Recursively walk current directory.
    # NOTE: sh.walk() and its siblings are generators.
    list(sh.walk())

    # Or just a specified directory.
    list(sh.walk("d"))

    # Or just it's files or directories.
    list(sh.walkfiles())
    list(sh.walkdirs())

    # Remove directories.
    sh.rmdir("a", "b", "c", "d")
    # Or use sh.rm which handles both files and directories.
    sh.rm("a", "b", "c", "d")


Write to a file atomically where content is written to a temporary and then moved once finished:

.. code-block:: python

    import os

    with sh.atomic_write("path/to/atomic.txt") as fp:
        # Writes are sent to a temporary file in the same directory as the destination.
        print(fp.name) # will be something like "path/to/.atomic.txt_XZKVqrlk.tmp"
        fp.write("some text")
        fp.write("some more text")
        assert not os.path.exists("path/to/atomic.txt")

    # Exiting context manager will result in the temporary file being atomically moved to destination.
    # This will also result in a lower-level fsync on the destination file and directory.
    assert os.path.exists("path/to/atomic.txt")

    # File mode, sync skipping, and overwrite flag can be specified to change the default behavior which is...
    with sh.atomic_write("file.txt", "w", skip_sync=False, overwrite=True): pass

    # Additional parameters to open() can be passed as keyword arguments.
    with sh.atomic_write("file.txt", "w", **open_kwargs): pass


Temporarily change environment variables:

.. code-block:: python

    # Extend existing environment.
    with sh.environ({"KEY1": "value1", "KEY2": "value2"}) as new_environ:
        # Do something while environment changed.
        # Environment variables include all previous ones and {"KEY1": "value1", "KEY2": "value2"}.
        pass

    # Replace the entire environment with a new one.
    with sh.environ({"KEY": "value"}, replace=True):
        # Environment variables are replaced and are now just {"KEY": "value"}.
        pass


For more details, please see the full documentation at https://shelmet.readthedocs.io.



.. |version| image:: https://img.shields.io/pypi/v/shelmet.svg?style=flat-square
    :target: https://pypi.python.org/pypi/shelmet/

.. |build| image:: https://img.shields.io/github/workflow/status/dgilland/shelmet/Main/master?style=flat-square
    :target: https://github.com/dgilland/shelmet/actions

.. |coveralls| image:: https://img.shields.io/coveralls/dgilland/shelmet/master.svg?style=flat-square
    :target: https://coveralls.io/r/dgilland/shelmet

.. |license| image:: https://img.shields.io/pypi/l/shelmet.svg?style=flat-square
    :target: https://pypi.python.org/pypi/shelmet/
