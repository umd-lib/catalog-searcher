from http import HTTPStatus
from pathlib import Path
from typing import Callable

import httpretty
import pytest
from environs import Env

from catalog_searcher.search.alma import AlmaSearch
from catalog_searcher.search.cql import cql


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
def alma_search_url(alma_search: AlmaSearch) -> str:
    return alma_search.sru_url_template.expand(
        institutionCode=alma_search.institution_code,
        recordSchema='mods',
        query=cql('alma.all_for_ui', '=', alma_search.query) & ('alma.mms_tagSuppressed', '=', 'false'),
        maximumRecords=alma_search.per_page,
        startRecord=(alma_search.page * alma_search.per_page) + 1,
    )


@pytest.fixture
def alma_search_request_args(shared_datadir: Path, alma_search_url: str) -> dict[str, str]:
    return {
        'uri': alma_search_url,
        'method': httpretty.GET,
        'adding_headers': {
            'Content-Type': 'application/xml',
        },
        'body': (shared_datadir / 'alma_response.xml').read_text(),
    }


@pytest.fixture
def register_bad_request() -> Callable:
    def _register_bad_request(url: str, method: str = httpretty.GET):
        httpretty.register_uri(
            uri=url,
            method=method,
            status=HTTPStatus.BAD_REQUEST
        )
    return _register_bad_request
