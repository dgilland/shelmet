shelmet
*******

|version| |build| |coveralls| |license|


A shell power-up for working with the file system and running subprocess commands.


Links
=====

- Project: https://github.com/dgilland/shelmet
- Documentation: https://shelmet.readthedocs.io
- PyPI: https://pypi.python.org/pypi/shelmet/
- Github Actions: https://github.com/dgilland/shelmet/actions


Features
========

- Run and define subprocess commands

  - ``run``
  - ``cmd``

- Interact with files

  - ``atomicdfile``, ``atomicdir``
  - ``read``, ``readchunks``, ``readlines``
  - ``write``, ``writechunks``
  - ``fsync``, ``dirsync``

- Execute core shell operations

  - ``cp``, ``mv``, ``mkdir``, ``touch``
  - ``rm``, ``rmfile``, ``rmdir``
  - ``ls``, ``lsfiles``, ``lsdirs``
  - ``walk``, ``walkfiles``, ``walkdirs``

- Other utilities

  - ``backup``
  - ``cd``
  - ``environ``
  - ``cwd``, ``homedir``
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

    import shelmet as sh


Run system commands:

.. code-block:: python

    # sh.run() is a wrapper around subprocess.run() that defaults to output capture, text-mode,
    # exception raising on non-zero exit codes, environment variable extension instead of
    # replacement, and support for passing command arguments as a variable number of strings instead
    # of just a list of strings.
    result = sh.run("ps", "aux")
    print(result.stdout)
    print(result.stderr)

    # stdout and stderr can be combined with...
    result = sh.run("some", "command", combine_output=True)

    # or not captured at all...
    sh.run("...", capture_output=False)


Create reusable run commands that support chained commands like "pipe" ``|`` , "and" ``&&``, "or" ``||``, and "after" ``;``:

.. code-block:: python

    # sh.cmd() returns a sh.Command object that can be used to execute a fixed command.
    ps_aux = sh.cmd("ps", "aux")

    # And has the option to pipe it's output into another command automatically.
    grep_ps = ps_aux.pipe("grep", "-i", check=False)
    print(grep_ps.shell_cmd)
    # ps aux | grep -i

    search_result_1 = grep_ps.run("search term 1")
    print(search_result_1.stdout)

    search_result_2 = grep_ps.run("search term 2")
    print(search_result_2.stdout)

    # Equivalent to: mkdir foo && echo 'success' || echo 'failure'
    sh.cmd("mkdir", "foo").and_("echo", "success").or_("echo", "failure").run()


Perform file system operations:

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


Perform file IO:

.. code-block:: python

    sh.write("test.txt", "some text\n")
    sh.write("test.txt", " some more text\n", "a")

    sh.write("test.bin", b"some bytes")
    sh.write("test.bin", b" some more bytes", "ab")

    sh.writelines("output.txt", ["1", "2", "3"])              # -> "1\n2\n3\n"
    sh.writelines("output.txt", (str(i) for i in range(10)))  # -> "0\n1\n2\n3\n4\n5\n6\n7\n8\n9\n"

    # Write to a file atomically. See sh.atomicfile for more details.
    sh.write("test.txt", "content", atomic=True)
    sh.writelines("test.txt", ["content"], atomic=True)

    text = sh.read("test.txt")        # -> "some text\nsome more text\n"
    data = sh.read("text.bin", "rb")  # -> b"some bytes some more bytes"

    for line in sh.readlines("test.txt"):
        print(line)

    for chunk in sh.readchunks("test.txt", size=1024):
        print(chunk)

    sh.write("test.txt", "a|b|c|d")
    items = list(sh.readchunks("test.txt", sep="|"))
    print(items)  # -> ["a", "b", "c", "d"]

    sh.write("test.txt", b"a|b|c|d", "wb")
    assert "".join(sh.readchunks("test.txt", "rb", sep=b"|")) == b"a|b|c|d"


Backup files:

.. code-block:: python

    backup_file = sh.backup("test.txt")
    print(backup_file)                                     # test.txt.2021-02-24_16-19-20-276491~
    sh.backup("test.txt", utc=True)                        # test.txt.2021-02-24T11:19:20.276491Z~
    sh.backup("test.txt", epoch=True)                      # test.txt.1614878783.56201
    sh.backup("test.txt", suffix=".bak")                   # test.txt.2021-02-24T16:19:20.276491.bak
    sh.backup("test.txt", suffix=".bak", timestamp=False)  # test.txt.bak
    sh.backup("test.txt", prefix="BACKUP_", suffix="")     # BACKUP_test.txt.2021-02-24T16:19:20.276491

    from functools import partial
    import itertools

    counter = itertools.count(1)
    backup = partial(sh.backup, namer=lambda src: f"{src.name}-{next(counter)}~")
    backup("test.txt")  # test.txt-1~
    backup("test.txt")  # test.txt-2~
    backup("test.txt")  # test.txt-3~


Write to a new file atomically where content is written to a temporary file and then moved once finished:

.. code-block:: python

    import os

    with sh.atomicfile("path/to/atomic.txt") as fp:
        # Writes are sent to a temporary file in the same directory as the destination.
        print(fp.name) # will be something like "path/to/.atomic.txt_XZKVqrlk.tmp"
        fp.write("some text")
        fp.write("some more text")

        # File doesn't exist yet.
        assert not os.path.exists("path/to/atomic.txt")

    # Exiting context manager will result in the temporary file being atomically moved to destination.
    # This will also result in a lower-level fsync on the destination file and directory.
    assert os.path.exists("path/to/atomic.txt")

    # File mode, sync skipping, and overwrite flag can be specified to change the default behavior which is...
    with sh.atomicfile("file.txt", "w", skip_sync=False, overwrite=True) as fp:
        pass

    # Additional parameters to open() can be passed as keyword arguments.
    with sh.atomicfile("file.txt", "w", **open_kwargs) as fp:
        pass

    # To writie to a file atomically without a context manager
    sh.write("file.txt", "content", atomic=True)


Create a new directory atomically where its contents are written to a temporary directory and then moved once finished:

.. code-block:: python

    with sh.atomicdir("path/to/atomic_dir") as atomic_dir:
        # Yielded path is temporary directory within the same parent directory as the destination.
        # path will be something like "path/to/.atomic_dir_QGLDfPwz_tmp"
        some_file = atomic_dir / "file.txt"
        some_file.write_text("contents")  # file written to "path/to/.atomic_dir_QGLDfPwz_tmp/file.txt"

        some_dir = atomic_dir / "dir"
        some_dir.mkdir()  # directory created at "path/to/.atomic_dir_QGLDfPwz_tmp/dir/"

        # Directory doesn't exist yet.
        assert not os.path.exists("path/to/atomic_dir")

    # Exiting context manager will result in the temporary directory being atomically moved to destination.
    assert os.path.exists("path/to/atomic_dir")

    # Sync skipping and overwrite flag can be specified to change the default behavior which is...
    with sh.atomicdir("atomic_dir", skip_sync=False, overwrite=True) as atomic_dir:
        pass


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
