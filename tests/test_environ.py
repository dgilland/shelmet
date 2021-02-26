import os

import pytest
from pytest import param

import shelmet as sh

from .utils import is_subdict


parametrize = pytest.mark.parametrize


@parametrize(
    "env",
    [
        param({"a": "1"}),
        param({"a": "1", "b": "2"}),
    ],
)
def test_environ__extends_envvars_and_restore_original(env: dict):
    orig_env = os.environ.copy()

    with sh.environ(env) as envvars:
        assert is_subdict(env, envvars)
        assert is_subdict(env, dict(os.environ))
        assert os.environ != orig_env
    assert os.environ == orig_env


@parametrize(
    "env",
    [
        param({"a": "1"}),
        param({"a": "1", "b": "2"}),
    ],
)
def test_environ__replaces_envvars_and_restores_original(env: dict):
    orig_env = os.environ.copy()

    with sh.environ(env, replace=True) as envvars:
        assert env == envvars
        assert env == os.environ
    assert os.environ == orig_env
