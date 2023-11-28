from typing import Callable

import pytest
from environs import Env


@pytest.fixture
def env(datadir) -> Env:
    env = Env()
    env.read_env(datadir / 'env')
    return env


@pytest.fixture
def raise_connection_error() -> Callable:
    def _raise_connection_error(*_args, **_kwargs):
        raise ConnectionError
    
    return _raise_connection_error
    