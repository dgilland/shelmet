import os
import re
import subprocess
import typing as t
from unittest import mock

import pytest
from pytest import param

import shelmet as sh


parametrize = pytest.mark.parametrize


@pytest.fixture()
def mock_subprocess_run() -> t.Generator[mock.MagicMock, None, None]:
    with mock.patch("subprocess.run") as _mock_subprocess_run:
        yield _mock_subprocess_run


def run_call_args(
    args,
    stdin=None,
    input=None,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    cwd=None,
    timeout=None,
    check=True,
    encoding=None,
    errors=None,
    text=True,
    env=None,
    **popen_kwargs,
):
    popen_kwargs.pop("capture_output", None)
    popen_kwargs.pop("combine_output", None)
    popen_kwargs.pop("replace_env", None)
    return mock.call(
        args,
        stdin=stdin,
        input=input,
        stdout=stdout,
        stderr=stderr,
        cwd=cwd,
        timeout=timeout,
        check=check,
        encoding=encoding,
        errors=errors,
        universal_newlines=text,
        env=env,
        **popen_kwargs,
    )


def test_command__returns_command_object_with_defaults():
    args = ["ls", "-la"]
    cmd = sh.cmd(*args)

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
def test_command__raises_on_bad_args(args: list, exception: t.Type[Exception], match: str):
    with pytest.raises(exception, match=re.escape(match)):
        sh.cmd(*args)


@parametrize(
    "cmd, expected_repr",
    [
        param(sh.cmd("ls", "-la"), "Command(args=['ls', '-la'])"),
        param(
            sh.cmd("ls", "-la").pipe("grep", "foo"),
            "Command(args=['grep', 'foo'], parents=[PipeCommand(args=['ls', '-la'])])",
        ),
        param(
            sh.cmd("cmd1").pipe("cmd2").pipe("cmd3"),
            (
                "Command(args=['cmd3'],"
                " parents=[PipeCommand(args=['cmd1']), PipeCommand(args=['cmd2'])])"
            ),
        ),
    ],
)
def test_command_repr(cmd, expected_repr):
    assert repr(cmd) == expected_repr


@parametrize(
    "args, kwargs, expected_call",
    [
        param(["ls"], {}, run_call_args(["ls"]), id="single_arg"),
        param(["ls", "-l", "-a"], {}, run_call_args(["ls", "-l", "-a"]), id="multiple_args"),
        param(
            [["ls", "-l", "-a"]], {}, run_call_args(["ls", "-l", "-a"]), id="single_list_of_args"
        ),
        param(
            [["ls"], ["-l", "-a"]],
            {},
            run_call_args(["ls", "-l", "-a"]),
            id="multiple_lists_of_args",
        ),
        param(
            ["ls", None, "-l", None, "-a"],
            {},
            run_call_args(["ls", "-l", "-a"]),
            id="none_valued_args_discarded",
        ),
        param(
            ["ls"],
            {"capture_output": False},
            run_call_args(["ls"], stdout=None, stderr=None),
            id="no_capture_output",
        ),
        param(["ls"], {"stdout": None}, run_call_args(["ls"], stdout=None), id="no_capture_stdout"),
        param(["ls"], {"stderr": None}, run_call_args(["ls"], stderr=None), id="no_capture_stderr"),
        param(
            ["ls"],
            {"combine_output": True},
            run_call_args(["ls"], stderr=subprocess.STDOUT),
            id="combine_output",
        ),
        param(["ls"], {"text": False}, run_call_args(["ls"], text=False), id="no_text"),
        param(["ls"], {"input": "test"}, run_call_args(["ls"], input="test"), id="input_as_str"),
        param(
            ["ls"],
            {"input": b"test", "text": False},
            run_call_args(["ls"], input=b"test", text=False),
            id="input_as_bytes",
        ),
        param(
            ["ls"],
            {"input": b"test"},
            run_call_args(["ls"], input="test"),
            id="coerce_input_to_str",
        ),
        param(
            ["ls"],
            {"input": "test", "text": False},
            run_call_args(["ls"], input=b"test", text=False),
            id="coerce_input_to_bytes",
        ),
        param(
            ["ls"],
            {"stdin": subprocess.DEVNULL},
            run_call_args(["ls"], stdin=subprocess.DEVNULL),
            id="set_stdin",
        ),
        param(["ls"], {"cwd": "."}, run_call_args(["ls"], cwd="."), id="set_cwd"),
        param(["ls"], {"timeout": 10}, run_call_args(["ls"], timeout=10), id="set_timeout"),
        param(
            ["ls"],
            {"encoding": "utf-8"},
            run_call_args(["ls"], encoding="utf-8"),
            id="set_encoding",
        ),
        param(
            ["ls"],
            {"errors": "strict"},
            run_call_args(["ls"], errors="strict"),
            id="set_errors",
        ),
    ],
)
def test_command_run__passes_arguments_to_subprocess_run(
    mock_subprocess_run: mock.MagicMock, args: list, kwargs: dict, expected_call: tuple
):
    sh.run(*args, **kwargs)
    assert mock_subprocess_run.call_args == expected_call


def test_command_run__extends_env(mock_subprocess_run: mock.MagicMock):
    env = {"a": "1", "b": "2"}
    expected_call = run_call_args(["ls"], env={**os.environ, **env})
    sh.run("ls", env=env)
    assert mock_subprocess_run.call_args == expected_call


def test_command_run__replaces_env(mock_subprocess_run: mock.MagicMock):
    env = {"a": "1", "b": "2"}
    expected_call = run_call_args(["ls"], env=env)
    sh.run("ls", env=env, replace_env=True)
    assert mock_subprocess_run.call_args == expected_call


@parametrize(
    "cmd, extra_args, overrides, expected_call",
    [
        param(sh.cmd("ls"), ["-l", "-a"], {}, run_call_args(["ls", "-l", "-a"])),
        param(
            sh.cmd("ls"),
            [],
            {"env": {"A": "B"}, "replace_env": True},
            run_call_args(["ls"], env={"A": "B"}),
        ),
        param(sh.cmd("ls"), [], {"cwd": "/tmp"}, run_call_args(["ls"], cwd="/tmp")),
        param(
            sh.cmd("ls"),
            [],
            {"stdin": subprocess.PIPE, "stdout": None, "stderr": None},
            run_call_args(["ls"], stdin=subprocess.PIPE, stdout=None, stderr=None),
        ),
        param(
            sh.cmd("ls"),
            [],
            {"capture_output": False},
            run_call_args(["ls"], stdout=None, stderr=None),
        ),
        param(
            sh.cmd("ls"),
            [],
            {"input": "test", "timeout": 10},
            run_call_args(["ls"], input="test", timeout=10),
        ),
        param(
            sh.cmd("ls"),
            [],
            {"encoding": "utf-8", "errors": "ignore", "text": False},
            run_call_args(["ls"], encoding="utf-8", errors="ignore", text=False),
        ),
    ],
)
def test_command_run__overrides_defaults(
    mock_subprocess_run: mock.MagicMock,
    cmd: sh.Command,
    extra_args: list,
    overrides: dict,
    expected_call: tuple,
):
    cmd.run(*extra_args, **overrides)
    assert mock_subprocess_run.called
    assert mock_subprocess_run.call_args == expected_call


@parametrize(
    "cmd, mock_side_effect, expected_call_args_list",
    [
        param(
            sh.cmd("cmd1").pipe("cmd2").pipe("cmd3"),
            [
                subprocess.CompletedProcess(args=["cmd1"], returncode=0),
                subprocess.CompletedProcess(args=["cmd2"], returncode=0),
                subprocess.CompletedProcess(args=["cmd3"], returncode=0),
            ],
            [["cmd1"], ["cmd2"], ["cmd3"]],
            id="pipe_run_3",
        ),
        param(
            sh.cmd("cmd1").pipe("cmd2").pipe("cmd3"),
            [
                subprocess.CalledProcessError(cmd=["cmd1"], returncode=1),
                subprocess.CalledProcessError(cmd=["cmd2"], returncode=1),
                subprocess.CompletedProcess(args=["cmd3"], returncode=0),
            ],
            [["cmd1"], ["cmd2"], ["cmd3"]],
            id="pipe_run_3",
        ),
        param(
            sh.cmd("cmd1").and_("cmd2").and_("cmd3"),
            [subprocess.CompletedProcess(args=["cmd1"], returncode=1)],
            [["cmd1"]],
            id="and_run_1",
        ),
        param(
            sh.cmd("cmd1").and_("cmd2").and_("cmd3"),
            [
                subprocess.CompletedProcess(args=["cmd1"], returncode=0),
                subprocess.CompletedProcess(args=["cmd2"], returncode=1),
            ],
            [["cmd1"], ["cmd2"]],
            id="and_run_2",
        ),
        param(
            sh.cmd("cmd1").and_("cmd2").and_("cmd3"),
            [
                subprocess.CompletedProcess(args=["cmd1"], returncode=0),
                subprocess.CompletedProcess(args=["cmd2"], returncode=0),
                subprocess.CompletedProcess(args=["cmd3"], returncode=0),
            ],
            [["cmd1"], ["cmd2"], ["cmd3"]],
            id="and_run_3",
        ),
        param(
            sh.cmd("cmd1").or_("cmd2").or_("cmd3"),
            [subprocess.CompletedProcess(args=["cmd1"], returncode=0)],
            [["cmd1"]],
            id="or_run_1",
        ),
        param(
            sh.cmd("cmd1").or_("cmd2").or_("cmd3"),
            [
                subprocess.CompletedProcess(args=["cmd1"], returncode=1),
                subprocess.CompletedProcess(args=["cmd2"], returncode=0),
            ],
            [["cmd1"], ["cmd2"]],
            id="or_run_2",
        ),
        param(
            sh.cmd("cmd1").or_("cmd2").or_("cmd3"),
            [
                subprocess.CompletedProcess(args=["cmd1"], returncode=1),
                subprocess.CompletedProcess(args=["cmd2"], returncode=1),
                subprocess.CompletedProcess(args=["cmd3"], returncode=0),
            ],
            [["cmd1"], ["cmd2"], ["cmd3"]],
            id="or_run_3",
        ),
        param(
            sh.cmd("cmd1").or_("cmd2").or_("cmd3"),
            [
                subprocess.CalledProcessError(cmd=["cmd1"], returncode=1),
                subprocess.CalledProcessError(cmd=["cmd2"], returncode=1),
                subprocess.CompletedProcess(args=["cmd3"], returncode=1),
            ],
            [["cmd1"], ["cmd2"], ["cmd3"]],
            id="or_run_3_errors",
        ),
        param(
            sh.cmd("cmd1").after("cmd2").after("cmd3"),
            [
                subprocess.CompletedProcess(args=["cmd1"], returncode=1),
                subprocess.CompletedProcess(args=["cmd2"], returncode=1),
                subprocess.CompletedProcess(args=["cmd3"], returncode=1),
            ],
            [["cmd1"], ["cmd2"], ["cmd3"]],
            id="after_run_3_failures",
        ),
        param(
            sh.cmd("cmd1").after("cmd2").after("cmd3"),
            [
                subprocess.CalledProcessError(cmd=["cmd1"], returncode=1),
                subprocess.CalledProcessError(cmd=["cmd2"], returncode=1),
                subprocess.CompletedProcess(args=["cmd3"], returncode=1),
            ],
            [["cmd1"], ["cmd2"], ["cmd3"]],
            id="after_run_3_errors",
        ),
        param(
            sh.cmd("cmd1").after("cmd2").after("cmd3"),
            [
                subprocess.CompletedProcess(args=["cmd1"], returncode=0),
                subprocess.CompletedProcess(args=["cmd2"], returncode=0),
                subprocess.CompletedProcess(args=["cmd3"], returncode=0),
            ],
            [["cmd1"], ["cmd2"], ["cmd3"]],
            id="after_run_3_successes",
        ),
    ],
)
def test_command_run__calls_parent_command_run(
    mock_subprocess_run: mock.MagicMock,
    cmd: sh.Command,
    mock_side_effect: list,
    expected_call_args_list: list,
):
    if mock_side_effect:
        mock_subprocess_run.side_effect = mock_side_effect

    result = cmd.run()
    assert len(mock_subprocess_run.call_args_list) == len(expected_call_args_list)
    assert result.args == expected_call_args_list[-1]

    for i, call_args in enumerate(expected_call_args_list):
        call_cmd = mock_subprocess_run.call_args_list[i]
        assert call_args == call_cmd[0][0]


def test_command_run__pipes_parent_stdout_to_child(mock_subprocess_run: mock.MagicMock):
    cmd1_stdout = "cmd1_stdout"
    mock_subprocess_run().stdout = cmd1_stdout

    cmd = sh.cmd("cmd1").pipe("cmd2")
    cmd.run()

    call_cmd2 = mock_subprocess_run.call_args_list[-1]
    assert call_cmd2[0][0] == ["cmd2"]
    assert call_cmd2[1]["input"] == cmd1_stdout


def test_command_pipe__sets_parent():
    cmd1 = sh.cmd("cmd1")
    cmd2 = cmd1.pipe("cmd2")
    cmd3 = cmd2.pipe("cmd3")
    cmd4 = cmd3.pipe("cmd4")

    assert cmd2.parent.command is cmd1
    assert cmd3.parent.command is cmd2
    assert cmd4.parent.command is cmd3


def test_command_pipe__returns_child_command():
    parent_cmd = sh.cmd("parent")
    child_kwargs = {
        "stdin": None,
        "input": b"test",
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
    child = parent_cmd.pipe("child", "cmd", **child_kwargs, **child_popen_kwargs)

    assert child.args == ["child", "cmd"]
    for attr, value in child_kwargs.items():
        assert getattr(child, attr) == value
    assert child.popen_kwargs == child_popen_kwargs
    assert child.parent.command is parent_cmd


@parametrize(
    "cmd, expected_shell_cmd",
    [
        param(sh.cmd("ls"), "ls"),
        param(sh.cmd("ps").pipe("grep", "foo bar"), "ps | grep 'foo bar'"),
        param(
            sh.cmd("ps").pipe("grep", "foo bar").pipe("grep", "test"),
            "ps | grep 'foo bar' | grep test",
        ),
        param(sh.cmd("cmd1").and_("cmd2", "a b").and_("cmd3"), "cmd1 && cmd2 'a b' && cmd3"),
        param(sh.cmd("cmd1").or_("cmd2", "a b").or_("cmd3"), "cmd1 || cmd2 'a b' || cmd3"),
        param(sh.cmd("cmd1").after("cmd2", "a b").after("cmd3"), "cmd1 ; cmd2 'a b' ; cmd3"),
        param(
            sh.cmd("cmd1").pipe("cmd2", "a b").and_("cmd3").or_("cmd4").after("cmd5"),
            "cmd1 | cmd2 'a b' && cmd3 || cmd4 ; cmd5",
        ),
    ],
)
def test_command_shell_cmd__returns_full_chained_command(cmd: sh.Command, expected_shell_cmd: str):
    assert cmd.shell_cmd == expected_shell_cmd
