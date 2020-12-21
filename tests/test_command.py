import re
import subprocess
import typing as t
from unittest import mock

import pytest
from pytest import param

from shelmet import sh

from .utils import is_subdict


parametrize = pytest.mark.parametrize


@pytest.fixture()
def mock_run() -> t.Generator[mock.MagicMock, None, None]:
    with mock.patch("shelmet.sh._run") as _mock_run:
        yield _mock_run


def test_command__should_return_command_object_with_defaults():
    args = ["ls", "-la"]
    cmd = sh.command(*args)

    assert cmd.args == args
    assert cmd.stdin is None
    assert cmd.input is None
    assert cmd.stdout == subprocess.PIPE
    assert cmd.stderr == subprocess.PIPE
    assert cmd.capture_output is True
    assert cmd.cwd is None
    assert cmd.timeout is None
    assert cmd.check is True
    assert cmd.encoding is None
    assert cmd.errors is None
    assert cmd.text is True
    assert cmd.env is None
    assert cmd.replace_env is False
    assert cmd.popen_kwargs == {}
    assert cmd.parent is None
    assert cmd.parents == []
    assert cmd.shell_cmd == "ls -la"


@parametrize(
    "args, exception, match",
    [
        param([], TypeError, "Command(): requires at least one non-empty positional argument"),
        param(
            [None, None],
            TypeError,
            "Command(): requires at least one non-empty positional argument",
        ),
        param(
            [5],
            TypeError,
            "Command(): requires all positional arguments to be either string or bytes",
        ),
    ],
)
def test_command__should_raise_on_bad_args(args: list, exception: t.Type[Exception], match: str):
    with pytest.raises(exception, match=re.escape(match)):
        sh.command(*args)


@parametrize(
    "cmd, expected_repr",
    [
        param(sh.command("ls", "-la"), "Command(args=['ls', '-la'])"),
        param(
            sh.command("ls", "-la").pipe("grep", "foo"),
            "Command(args=['grep', 'foo'], parents=[Command(args=['ls', '-la'])])",
        ),
        param(
            sh.command("cmd1").pipe("cmd2").pipe("cmd3"),
            "Command(args=['cmd3'], parents=[Command(args=['cmd1']), Command(args=['cmd2'])])",
        ),
    ],
)
def test_command_repr(cmd, expected_repr):
    assert repr(cmd) == expected_repr


def test_command_run__should_call_sh_run(mock_run: mock.MagicMock):
    args = ["ls", "-la"]
    kwargs: t.Dict[str, t.Any] = {
        "stdin": None,
        "input": "test",
        "stdout": None,
        "stderr": None,
        "capture_output": False,
        "cwd": "/",
        "timeout": 10,
        "check": False,
        "encoding": "utf-8",
        "errors": "ignore",
        "text": False,
        "env": {"A": "B"},
        "replace_env": True,
        "umask": 1,
    }
    cmd = sh.command(*args, **kwargs)
    cmd.run()
    assert mock_run.called

    (run_args,), run_kwargs = mock_run.call_args
    assert run_args == args
    assert run_kwargs == kwargs


@parametrize(
    "cmd, extra_args, overrides",
    [
        param(sh.command("ls"), ["-l", "-a"], {}),
        param(sh.command("ls"), [], {"env": {"A": "B"}, "replace_env": True}),
        param(sh.command("ls"), [], {"cwd": "/tmp"}),
        param(sh.command("ls"), [], {"stdin": subprocess.PIPE, "stdout": None, "stderr": None}),
        param(sh.command("ls"), [], {"capture_output": False}),
        param(sh.command("ls"), [], {"input": "test", "timeout": 10}),
        param(sh.command("ls"), [], {"encoding": "utf-8", "errors": "ignore", "text": False}),
    ],
)
def test_command_run__should_extend_defaults(
    mock_run: mock.MagicMock, cmd: sh.Command, extra_args: list, overrides: dict
):
    cmd.run(*extra_args, **overrides)
    assert mock_run.called

    (run_args,), run_kwargs = mock_run.call_args
    assert run_args == cmd.args + extra_args
    assert is_subdict(overrides, run_kwargs)


def test_command_run__should_call_parent_command_run(mock_run: mock.MagicMock):
    cmd = sh.command("cmd1").pipe("cmd2").pipe("cmd3")
    cmd.run()

    assert len(mock_run.call_args_list) == 3
    call_cmd1, call_cmd2, call_cmd3 = mock_run.call_args_list
    assert call_cmd1[0][0] == ["cmd1"]
    assert call_cmd2[0][0] == ["cmd2"]
    assert call_cmd3[0][0] == ["cmd3"]


def test_command_run__should_pipe_parent_stdout_to_child(mock_run: mock.MagicMock):
    cmd1_stdout = "cmd1_stdout"
    mock_run().stdout = cmd1_stdout

    cmd = sh.command("cmd1").pipe("cmd2")
    cmd.run()

    call_cmd2 = mock_run.call_args_list[-1]
    assert call_cmd2[0][0] == ["cmd2"]
    assert call_cmd2[1]["input"] == cmd1_stdout


def test_command_pipe__should_set_parent():
    cmd1 = sh.command("cmd1")
    cmd2 = cmd1.pipe("cmd2")
    cmd3 = cmd2.pipe("cmd3")
    cmd4 = cmd3.pipe("cmd4")

    assert cmd2.parent is cmd1
    assert cmd3.parent is cmd2
    assert cmd4.parent is cmd3


def test_command_pipe__should_return_child_command():
    parent = sh.command("parent")
    child_kwargs = {
        "stdin": None,
        "input": "test",
        "stdout": None,
        "stderr": None,
        "capture_output": False,
        "cwd": "/",
        "timeout": 10,
        "check": False,
        "encoding": "utf-8",
        "errors": "ignore",
        "text": False,
        "env": {"A": "B"},
        "replace_env": True,
    }
    child_popen_kwargs = {"umask": 1}
    child = parent.pipe("child", "cmd", **child_kwargs, **child_popen_kwargs)

    assert child.args == ["child", "cmd"]
    for attr, value in child_kwargs.items():
        assert getattr(child, attr) == value
    assert child.popen_kwargs == child_popen_kwargs
    assert child.parent is parent


@parametrize(
    "cmd, expected_shell_cmd",
    [
        param(sh.command("ls"), "ls"),
        param(sh.command("ps").pipe("grep", "foo bar"), "ps | grep 'foo bar'"),
        param(
            sh.command("ps").pipe("grep", "foo bar").pipe("grep", "test"),
            "ps | grep 'foo bar' | grep test",
        ),
    ],
)
def test_command_shell_cmd__should_return_full_piped_command(
    cmd: sh.Command, expected_shell_cmd: str
):
    assert cmd.shell_cmd == expected_shell_cmd
