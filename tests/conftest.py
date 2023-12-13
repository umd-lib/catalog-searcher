from http import HTTPStatus
from pathlib import Path
from typing import Callable

import httpretty
import pytest
from environs import Env

from catalog_searcher.search.alma import AlmaSearch
from catalog_searcher.search.cql import cql
from catalog_searcher.search.primo import PrimoSearch


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
def primo_article_search(env):
    return PrimoSearch(env=env, endpoint='articles', query='maryland', page=0, per_page=3)


@pytest.fixture
def primo_article_search_url(primo_article_search):
    return primo_article_search.article_search_api_url_template.expand(
        vid=primo_article_search.vid,
        q=primo_article_search.query,
        offset=(primo_article_search.page * primo_article_search.per_page),
        limit=primo_article_search.per_page,
    )


@pytest.fixture
def primo_article_search_request_args(shared_datadir: Path, primo_article_search_url: str) -> dict[str, str]:
    return {
        'uri': primo_article_search_url,
        'method': httpretty.GET,
        'adding_headers': {
            'Content-Type': 'application/json',
        },
        'body': (shared_datadir / 'primo_article_search_response.json').read_text(),
    }


@pytest.fixture
def primo_book_search(env: Env) -> PrimoSearch:
    return PrimoSearch(env=env, endpoint='books-and-more', query='black metal', page=5, per_page=3)


@pytest.fixture
def primo_book_search_url(primo_book_search: PrimoSearch) -> str:
    return primo_book_search.book_search_api_url_template.expand(
        vid=primo_book_search.vid,
        q=primo_book_search.query,
        offset=(primo_book_search.page * primo_book_search.per_page),
        limit=primo_book_search.per_page,
    )


@pytest.fixture
def primo_book_search_request_args(shared_datadir: Path, primo_book_search_url) -> dict[str, str]:
    return {
        'uri': primo_book_search_url,
        'method': httpretty.GET,
        'adding_headers': {
            'Content-Type': 'application/json',
        },
        'body': (shared_datadir / 'primo_book_search_response.json').read_text(),
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
