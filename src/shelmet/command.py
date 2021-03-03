"""The command module contains utilities for working with subprocess commands."""

from abc import ABCMeta, abstractmethod
import os
import shlex
import subprocess
import typing as t
from typing import Iterable

from .types import RunArgs, StdFile, StrPath


class Command:
    """
    A system command that can be executed multiple times and used to create piped commands.

    Executing the command is done using :meth:`run` which is a wrapper around ``subprocess.run``.
    However, the default arguments for a :class:`Command` enable different default behavior than
    ``subprocess.run``:

    - Output is captured
    - Text-mode is enabled
    - Environment variables extend ``os.environ`` instead of replacing them.
    - Exceptions are raised by default when the completed process returns a non-zero exit code.
    - System command arguments can be passed as a var-args instead of just a list.

    To disable output capture completely, use ``capture_output=False``. To disable output capture
    for just one of them, set ``stdout`` or ``stderr`` to ``None``.

    To disable ``os.environ`` extension, use ``replace_env=True``.

    To disable exception raising, use ``check=False``.

    Therefore, to use the default behavior of ``subprocess.run``, set the following keyword
    arguments:

    ::

        ls = Command(["ls", "-la"], capture_output=False, text=False, check=False, replace_env=True)
        ls.run()

    Args:
        *args: System command arguments to execute. If ``None`` is given as an argument value, it
            will be discarded.
        stdin: Specify the executed command’s standard input.
        input: If given it will be passed to the underlying process as stdin. When used, stdin will
            be set to ``PIPE`` automatically and cannot be used. The value will be encoded or
            decoded automatically if it does not match the expected type based on whether text-mode
            is enabled or not.
        stdout: Specify the executed command’s standard output.
        stderr: Specify the executed command’s standard error.
        capture_output: Whether to capture stdout and stderr and include in the returned completed
            process result.
        combine_output: Whether to combine stdout and stderr. Equilvalent to setting
            ``stderr=subprocess.STDOUT``.
        cwd: Set the current working directory when executing the command.
        timeout: If the timeout expires, the child process will be killed and waited for.
        check: Whether to check return code and raise if it is non-zero.
        encoding: Set encoding to use for text-mode.
        errors: Specify how encoding and decoding errors should be handled. Must be one of "strict",
            "ignore", "replace", "backslashreplace", "xmlcharrefreplace", "namereplace"
        text: Set text-mode.
        env: Environment variables for the new process. Unlike in ``subprocess.run``, the default
            behavior is to extend the existing environment. Use ``replace_env=True`` to replace the
            environment variables instead.
        replace_env: Whether to replace the current environment when `env` given.

    Keyword Args:
        All other keyword arguments are passed to ``subprocess.run`` which subsequently passes them
        to ``subprocess.Popen``.
    """

    def __init__(
        self,
        *args: RunArgs,
        stdin: t.Optional[StdFile] = None,
        input: t.Optional[t.Union[str, bytes]] = None,
        stdout: t.Optional[StdFile] = subprocess.PIPE,
        stderr: t.Optional[StdFile] = subprocess.PIPE,
        capture_output: bool = True,
        combine_output: bool = False,
        cwd: t.Optional[StrPath] = None,
        timeout: t.Optional[t.Union[float, int]] = None,
        check: bool = True,
        encoding: t.Optional[str] = None,
        errors: t.Optional[str] = None,
        text: bool = True,
        env: t.Optional[dict] = None,
        replace_env: bool = False,
        parent: t.Optional["ChainCommand"] = None,
        **popen_kwargs: t.Any,
    ):
        run_args = _parse_run_args(args, error_prefix=f"{self.__class__.__name__}(): ")

        if input is not None:
            # Coerce input based on text mode setting.
            if text and isinstance(input, bytes):
                input = input.decode()
            elif not text and isinstance(input, str):
                input = input.encode()

        if not capture_output:
            stdout = None
            stderr = None

        if combine_output:
            stderr = subprocess.STDOUT

        self.args = run_args
        self.stdin = stdin
        self.input = input
        self.stdout = stdout
        self.stderr = stderr
        self.capture_output = capture_output
        self.combine_output = combine_output
        self.cwd = cwd
        self.timeout = timeout
        self.check = check
        self.encoding = encoding
        self.errors = errors
        self.text = text
        self.env = env
        self.replace_env = replace_env
        self.popen_kwargs = popen_kwargs
        self.parent = parent

    @property
    def parents(self) -> t.List["ChainCommand"]:
        """Return list of parent :class:`Command` objects that pipe output into this command."""
        parents = []
        if self.parent:
            grand_parents = self.parent.command.parents
            if grand_parents:
                parents.extend(grand_parents)
            parents.append(self.parent)
        return parents

    @property
    def shell_cmd(self) -> str:
        """Return string version of command that would be used when executing from a shell."""
        cmd = " ".join(
            shlex.quote(arg.decode() if isinstance(arg, bytes) else arg) for arg in self.args
        )
        if self.parent:
            cmd = f"{self.parent.shell_cmd} {cmd}"
        return cmd

    def __repr__(self) -> str:
        kv_items: t.List[t.Tuple[str, t.Any]] = [("args", self.args)]

        parents = self.parents
        if parents:
            repr_parents = ", ".join(repr(parent) for parent in self.parents)
            kv_items.append(("parents", f"[{repr_parents}]"))

        kv_out = ", ".join(f"{key}={value}" for key, value in kv_items)
        return f"{self.__class__.__name__}({kv_out})"

    @classmethod
    def from_command(cls, command, *extra_args: RunArgs, **override_kwargs: t.Any) -> "Command":
        run_args = command.args
        if extra_args:
            run_args = run_args + _parse_run_args(
                extra_args, error_prefix=f"{cls.__name__}.run(): "
            )

        override_kwargs.setdefault("input", command.input)
        override_kwargs.setdefault("stdin", command.stdin)
        override_kwargs.setdefault("stdout", command.stdout)
        override_kwargs.setdefault("stderr", command.stderr)
        override_kwargs.setdefault("capture_output", command.capture_output)
        override_kwargs.setdefault("combine_output", command.combine_output)
        override_kwargs.setdefault("cwd", command.cwd)
        override_kwargs.setdefault("timeout", command.timeout)
        override_kwargs.setdefault("check", command.check)
        override_kwargs.setdefault("encoding", command.encoding)
        override_kwargs.setdefault("errors", command.errors)
        override_kwargs.setdefault("text", command.text)
        override_kwargs.setdefault("env", command.env)
        override_kwargs.setdefault("replace_env", command.replace_env)
        override_kwargs.update(command.popen_kwargs)

        return cls(*run_args, **override_kwargs)

    def pipe(
        self,
        *args: RunArgs,
        stdin: t.Optional[StdFile] = None,
        input: t.Optional[t.Union[str, bytes]] = None,
        stdout: t.Optional[StdFile] = subprocess.PIPE,
        stderr: t.Optional[StdFile] = subprocess.PIPE,
        capture_output: bool = True,
        combine_output: bool = False,
        cwd: t.Optional[StrPath] = None,
        timeout: t.Optional[t.Union[float, int]] = None,
        check: bool = True,
        encoding: t.Optional[str] = None,
        errors: t.Optional[str] = None,
        text: bool = True,
        env: t.Optional[dict] = None,
        replace_env: bool = False,
        **popen_kwargs: t.Any,
    ) -> "Command":
        """
        Return a new command whose input will be piped from the output of this command.

        This is like running "<this-command> | <next-command>".
        """
        return self.__class__(
            *args,
            stdin=stdin,
            input=input,
            stdout=stdout,
            stderr=stderr,
            capture_output=capture_output,
            combine_output=combine_output,
            cwd=cwd,
            timeout=timeout,
            check=check,
            encoding=encoding,
            errors=errors,
            text=text,
            env=env,
            replace_env=replace_env,
            parent=PipeCommand(self),
            **popen_kwargs,
        )

    def after(
        self,
        *args: RunArgs,
        stdin: t.Optional[StdFile] = None,
        input: t.Optional[t.Union[str, bytes]] = None,
        stdout: t.Optional[StdFile] = subprocess.PIPE,
        stderr: t.Optional[StdFile] = subprocess.PIPE,
        capture_output: bool = True,
        combine_output: bool = False,
        cwd: t.Optional[StrPath] = None,
        timeout: t.Optional[t.Union[float, int]] = None,
        check: bool = True,
        encoding: t.Optional[str] = None,
        errors: t.Optional[str] = None,
        text: bool = True,
        env: t.Optional[dict] = None,
        replace_env: bool = False,
        **popen_kwargs: t.Any,
    ) -> "Command":
        """
        Return a new command that will be executed after this command regardless of this command's
        return code.

        This is like running "<this-command> ; <next-command>".
        """
        return self.__class__(
            *args,
            stdin=stdin,
            input=input,
            stdout=stdout,
            stderr=stderr,
            capture_output=capture_output,
            combine_output=combine_output,
            cwd=cwd,
            timeout=timeout,
            check=check,
            encoding=encoding,
            errors=errors,
            text=text,
            env=env,
            replace_env=replace_env,
            parent=AfterCommand(self),
            **popen_kwargs,
        )

    def and_(
        self,
        *args: RunArgs,
        stdin: t.Optional[StdFile] = None,
        input: t.Optional[t.Union[str, bytes]] = None,
        stdout: t.Optional[StdFile] = subprocess.PIPE,
        stderr: t.Optional[StdFile] = subprocess.PIPE,
        capture_output: bool = True,
        combine_output: bool = False,
        cwd: t.Optional[StrPath] = None,
        timeout: t.Optional[t.Union[float, int]] = None,
        check: bool = True,
        encoding: t.Optional[str] = None,
        errors: t.Optional[str] = None,
        text: bool = True,
        env: t.Optional[dict] = None,
        replace_env: bool = False,
        **popen_kwargs: t.Any,
    ) -> "Command":
        """
        Return a new command that will be AND'd with this command.

        This is like running "<this-command> && <next-command>".
        """
        return self.__class__(
            *args,
            stdin=stdin,
            input=input,
            stdout=stdout,
            stderr=stderr,
            capture_output=capture_output,
            combine_output=combine_output,
            cwd=cwd,
            timeout=timeout,
            check=check,
            encoding=encoding,
            errors=errors,
            text=text,
            env=env,
            replace_env=replace_env,
            parent=AndCommand(self),
            **popen_kwargs,
        )

    def or_(
        self,
        *args: RunArgs,
        stdin: t.Optional[StdFile] = None,
        input: t.Optional[t.Union[str, bytes]] = None,
        stdout: t.Optional[StdFile] = subprocess.PIPE,
        stderr: t.Optional[StdFile] = subprocess.PIPE,
        capture_output: bool = True,
        combine_output: bool = False,
        cwd: t.Optional[StrPath] = None,
        timeout: t.Optional[t.Union[float, int]] = None,
        check: bool = True,
        encoding: t.Optional[str] = None,
        errors: t.Optional[str] = None,
        text: bool = True,
        env: t.Optional[dict] = None,
        replace_env: bool = False,
        **popen_kwargs: t.Any,
    ) -> "Command":
        """
        Return a new command that will be OR'd with this command.

        This is like running "<this-command> || <next-command>".
        """
        return self.__class__(
            *args,
            stdin=stdin,
            input=input,
            stdout=stdout,
            stderr=stderr,
            capture_output=capture_output,
            combine_output=combine_output,
            cwd=cwd,
            timeout=timeout,
            check=check,
            encoding=encoding,
            errors=errors,
            text=text,
            env=env,
            replace_env=replace_env,
            parent=OrCommand(self),
            **popen_kwargs,
        )

    def run(self, *extra_args: RunArgs, **override_kwargs: t.Any) -> subprocess.CompletedProcess:
        """
        Wrapper around ``subprocess.run`` that uses this class' arguments as defaults.

        To add additional command args to :attr:`args`, pass them as var-args.

        To override default keyword arguments, pass them as keyword-args.

        If :attr:`parent` is set (e.g. if this command was created with :meth:`pipe`,
        :meth:`after`, :meth:`and_`, or :meth:`or_`), then the parent command will be called first
        and then chained with this command.

        Args:
            *extra_args: Extend :attr:`args` with extra command arguments.
            **override_kwargs: Override this command's keyword arguments.
        """
        if extra_args or override_kwargs or self.parent:
            command = self.from_command(self, *extra_args, **override_kwargs)
        else:
            command = self

        if self.parent:
            result = self.parent.run(command)
        else:
            result = command._run()

        return result

    def _run(self):
        if self.env and not self.replace_env:
            env = {**os.environ, **self.env}
        else:
            env = self.env

        return subprocess.run(
            self.args,
            stdin=self.stdin,
            input=self.input,
            stdout=self.stdout,
            stderr=self.stderr,
            cwd=self.cwd,
            timeout=self.timeout,
            check=self.check,
            encoding=self.encoding,
            errors=self.errors,
            universal_newlines=self.text,  # NOTE: "text" argument doesn't exist in Python 3.6.
            env=env,
            **self.popen_kwargs,
        )


class ChainCommand(metaclass=ABCMeta):
    """
    Abstract base class for representing a chained command.

    The class is initialized with a parent command that will be called before the next command in
    the chain. The next command will be passed into the :meth:`run` method. Each subclass is
    responsible for implementing the :meth:`run` logic.
    """

    def __init__(self, command: Command):
        self.command = command

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(args={self.command.args})"

    @property
    def shell_cmd(self):
        return f"{self.command.shell_cmd} {self.separator}"

    @property
    @abstractmethod
    def separator(self) -> str:  # pragma: no cover
        # The separator is used for representational purposes only in `shell_cmd`.
        pass

    @abstractmethod
    def run(self, next_command: Command) -> subprocess.CompletedProcess:  # pragma: no cover
        # The primary logic that runs the parent command followed by the next command if applicable.
        pass


class AfterCommand(ChainCommand):
    """
    Chained command that runs one command after another regardless of the first command's return
    code.

    This is like the shell equivalent of "<cmd1> ; <cmd2>".
    """

    separator = ";"

    def run(self, next_command: Command):
        """Run `next_command` after :attr:`command`."""
        try:
            self.command.run()
        except subprocess.CalledProcessError:
            pass
        return next_command.run()


class PipeCommand(ChainCommand):
    """
    Chained command that pipes the output of one command into the input of another.

    This is like the shell equivalent of "<cmd1> | <cmd2>".
    """

    separator = "|"

    def run(self, next_command: Command) -> subprocess.CompletedProcess:
        """Pipe :attr:`command` into `next_command`."""
        result: t.Union[subprocess.CompletedProcess, subprocess.CalledProcessError]
        try:
            result = self.command.run()
        except subprocess.CalledProcessError as exc:
            result = exc
        return next_command.run(input=result.stdout, stdin=None)


class AndCommand(ChainCommand):
    """
    Chained command that runs one command after the other if the first command succeeds.

    This is like the shell equivalent of "<cmd1> | <cmd2>".
    """

    separator = "&&"

    def run(self, next_command: Command) -> subprocess.CompletedProcess:
        """Run `next_command` after :attr:`command` if :attr:`command` succeeds."""
        result = self.command.run()
        if result.returncode == 0:
            result = next_command.run()
        return result


class OrCommand(ChainCommand):
    """
    Chained command that runs one command after the other if the first command fails.

    This is like the shell equivalent of "<cmd1> | <cmd2>".
    """

    separator = "||"

    def run(self, next_command: Command) -> subprocess.CompletedProcess:
        """Run `next_command` after :attr:`command` if :attr:`command` fails."""
        try:
            result = self.command.run()
        except subprocess.CalledProcessError:
            failed = True
        else:
            failed = result.returncode != 0
        if failed:
            result = next_command.run()
        return result


def _parse_run_args(args: tuple, error_prefix: str = "run(): ") -> t.List[t.Union[str, bytes]]:
    good_args = []
    bad_args = []

    for arg in _flatten(args):
        if arg is None:
            # Ignore None values.
            continue
        elif isinstance(arg, (str, bytes)):
            good_args.append(arg)
        else:
            bad_args.append(arg)

    if bad_args:
        raise TypeError(
            f"{error_prefix}requires all positional arguments to be either string or bytes, not"
            f" {bad_args}"
        )

    if not good_args:
        raise TypeError(f"{error_prefix}requires at least one non-empty positional argument")

    return good_args


def _flatten(items: t.Iterable) -> t.Generator[t.Any, None, None]:
    for item in items:
        if isinstance(item, Iterable) and not isinstance(item, (str, bytes)):
            yield from item
        else:
            yield item


def cmd(
    *args: RunArgs,
    stdin: t.Optional[StdFile] = None,
    input: t.Optional[t.Union[str, bytes]] = None,
    stdout: t.Optional[StdFile] = subprocess.PIPE,
    stderr: t.Optional[StdFile] = subprocess.PIPE,
    capture_output: bool = True,
    combine_output: bool = False,
    cwd: t.Optional[StrPath] = None,
    timeout: t.Optional[t.Union[float, int]] = None,
    check: bool = True,
    encoding: t.Optional[str] = None,
    errors: t.Optional[str] = None,
    text: bool = True,
    env: t.Optional[dict] = None,
    replace_env: bool = False,
    **popen_kwargs: t.Any,
) -> Command:
    """
    Factory that returns an instance of :class:`.Command` initialized with the given arguments.

    See Also:
        :class:`.Command` for description of arguments.
    """
    return Command(
        *args,
        stdin=stdin,
        input=input,
        stdout=stdout,
        stderr=stderr,
        capture_output=capture_output,
        combine_output=combine_output,
        cwd=cwd,
        timeout=timeout,
        check=check,
        encoding=encoding,
        errors=errors,
        text=text,
        env=env,
        replace_env=replace_env,
        **popen_kwargs,
    )


def run(
    *args: RunArgs,
    stdin: t.Optional[StdFile] = None,
    input: t.Optional[t.Union[str, bytes]] = None,
    stdout: t.Optional[StdFile] = subprocess.PIPE,
    stderr: t.Optional[StdFile] = subprocess.PIPE,
    capture_output: bool = True,
    combine_output: bool = False,
    cwd: t.Optional[StrPath] = None,
    timeout: t.Optional[t.Union[float, int]] = None,
    check: bool = True,
    encoding: t.Optional[str] = None,
    errors: t.Optional[str] = None,
    text: bool = True,
    env: t.Optional[dict] = None,
    replace_env: bool = False,
    **popen_kwargs: t.Any,
) -> subprocess.CompletedProcess:
    """
    Convenience function-wrapper around :meth:`.Command.run`.

    Using this function is equivalent to:

    ::

        result = sh.cmd(*args, **kwargs).run()

    See Also:
        :class:`.Command` for description of arguments.
    """
    cmd = Command(
        *args,
        stdin=stdin,
        input=input,
        stdout=stdout,
        stderr=stderr,
        capture_output=capture_output,
        combine_output=combine_output,
        cwd=cwd,
        timeout=timeout,
        check=check,
        encoding=encoding,
        errors=errors,
        text=text,
        env=env,
        replace_env=replace_env,
        **popen_kwargs,
    )
    return cmd.run()
