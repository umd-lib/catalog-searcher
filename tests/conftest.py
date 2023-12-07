from http import HTTPStatus
from typing import Callable

import httpretty
import pytest
from environs import Env

from catalog_searcher.search.alma import AlmaSearch


@pytest.fixture
def env(shared_datadir) -> Env:
    env = Env()
    env.read_env(shared_datadir / 'env')
    return env


@pytest.fixture
def raise_connection_error() -> Callable:
    def _raise_connection_error(*_args, **_kwargs):
        raise ConnectionError

    return _raise_connection_error


@pytest.fixture
def alma_search(env: Env) -> AlmaSearch:
    return AlmaSearch(env=env, endpoint='books-and-more', query='maryland', page=0, per_page=3)


@pytest.fixture
def register_search_url(alma_search: AlmaSearch) -> Callable:
    def _register_search_url(body: str = '', status: int = HTTPStatus.OK):
        if status >= HTTPStatus.BAD_REQUEST:
            # we are mocking an error response, omit the body form the response
            httpretty.register_uri(
                uri=alma_search.sru_url_template.expand(institutionCode=alma_search.institution_code),
                method=httpretty.GET,
                status=status,
            )
        else:
            httpretty.register_uri(
                uri=alma_search.sru_url_template.expand(institutionCode=alma_search.institution_code),
                method=httpretty.GET,
                status=status,
                adding_headers={'Content-Type': 'application/json'},
                body=body,
            )

    return _register_search_url
