import typing as t
from unittest import mock

import pytest

import shelmet as sh


parametrize = pytest.mark.parametrize


@pytest.fixture()
def mock_command() -> t.Generator[mock.MagicMock, None, None]:
    with mock.patch.object(sh.command, "Command", spec=sh.command.Command) as _mock_command:
        yield _mock_command


def test_run__creates_command_and_call_run(mock_command):
    args = ["ls", "-la"]
    kwargs: t.Dict[str, t.Any] = {
        "stdin": None,
        "input": "test",
        "stdout": None,
        "stderr": None,
        "capture_output": False,
        "combine_output": True,
        "cwd": "/",
        "timeout": 10,
        "check": False,
        "encoding": "utf-8",
        "errors": "ignore",
        "text": False,
        "env": {"A": "B"},
        "replace_env": True,
    }
    popen_kwargs = {"umask": 1}

    sh.run(*args, **kwargs, **popen_kwargs)

    assert mock_command.called
    assert mock_command.call_args == mock.call(*args, **kwargs, **popen_kwargs)

    mock_run: mock.MagicMock = mock_command.return_value.run
    assert mock_run.called
    assert mock_run.call_args == mock.call()
