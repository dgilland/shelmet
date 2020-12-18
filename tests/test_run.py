import os
import subprocess
import typing as t
from unittest import mock

import pytest
from pytest import param

from shelmet import sh


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
        text=text,
        env=env,
        **popen_kwargs,
    )


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
def test_run__should_pass_arguments_to_subprocess_run(
    mock_subprocess_run: mock.MagicMock, args: list, kwargs: dict, expected_call: tuple
):
    sh.run(*args, **kwargs)
    assert mock_subprocess_run.call_args == expected_call


def test_run__should_extend_env(mock_subprocess_run: mock.MagicMock):
    env = {"a": "1", "b": "2"}
    expected_call = run_call_args(["ls"], env={**os.environ, **env})
    sh.run("ls", env=env)
    assert mock_subprocess_run.call_args == expected_call


def test_run__should_replace_env(mock_subprocess_run: mock.MagicMock):
    env = {"a": "1", "b": "2"}
    expected_call = run_call_args(["ls"], env=env)
    sh.run("ls", env=env, replace_env=True)
    assert mock_subprocess_run.call_args == expected_call
