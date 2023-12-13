import json
from http import HTTPStatus
from pathlib import Path

import httpretty
import pytest
from flask import Flask
from flask.testing import FlaskClient
from jsonschema import Draft202012Validator
from jsonschema.protocols import Validator

import catalog_searcher.app
from catalog_searcher.app import app as catalog_searcher_app
from catalog_searcher.app import get_pagination_links, get_search_class
from catalog_searcher.search import Search, SearchError
from catalog_searcher.search.alma import AlmaSearch
from catalog_searcher.search.primo import PrimoSearch
from catalog_searcher.search.worldcat import WorldcatSearch


@pytest.fixture()
def app() -> Flask:
    return catalog_searcher_app


@pytest.fixture()
def client(app) -> FlaskClient:
    return app.test_client()


def test_get_root(client: FlaskClient):
    response = client.get('/')
    assert response.json == {'status': 'ok'}


def test_get_ping(client: FlaskClient):
    response = client.get('/ping')
    assert response.json == {'status': 'ok'}


def test_search_no_query(client: FlaskClient):
    response = client.get('/search')
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_search_bad_page(client: FlaskClient):
    response = client.get('/search?q=maryland&page=one')
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_search_bad_per_page(client: FlaskClient):
    response = client.get('/search?q=maryland&per_page=five')
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_search_bad_backend(client: FlaskClient):
    response = client.get('/search?q=maryland&backend=foo')
    assert response.status_code == HTTPStatus.BAD_REQUEST


@httpretty.activate
def test_search(client: FlaskClient, alma_search_request_args: dict[str, str]):
    httpretty.register_uri(**alma_search_request_args)
    response = client.get('/search?q=maryland&backend=alma')
    assert response.status_code == HTTPStatus.OK
    assert response.content_type == 'application/json'
    api_response = response.json
    assert api_response['total'] == 108
    assert len(api_response['results']) == 3
    assert api_response['backend'] == 'alma'
    assert api_response['page'] == 0
    assert api_response['per_page'] == 3
    assert api_response['query'] == 'maryland'
    assert 'prev_page' not in api_response


@pytest.fixture
def api_response_validator() -> Validator:
    schema_file = Path(__file__).parent.parent / 'docs/api-response-schema.json'
    with schema_file.open() as fh:
        schema = json.load(fh)
    return Draft202012Validator(schema)


@httpretty.activate
def test_primo_book_search_response_validates(
    client: FlaskClient,
    primo_book_search: PrimoSearch,
    primo_book_search_request_args: dict[str, str],
    api_response_validator: Validator,
):
    httpretty.register_uri(**primo_book_search_request_args)
    response = client.get(f'/search?q={primo_book_search.query}&backend=primo')
    assert api_response_validator.is_valid(response.json)


@httpretty.activate
def test_primo_article_search_response_validates(
    client: FlaskClient,
    primo_article_search: PrimoSearch,
    primo_article_search_request_args: dict[str, str],
    api_response_validator: Validator,
):
    httpretty.register_uri(**primo_article_search_request_args)
    response = client.get(f'/search?q={primo_article_search.query}&backend=primo')
    assert api_response_validator.is_valid(response.json)


def test_search_with_error(monkeypatch, client):
    class BadSearch(Search):
        def __init__(self, *_args, **_kwargs):
            pass

        def search(self):
            raise SearchError

    monkeypatch.setattr(catalog_searcher.app, 'get_search_class', lambda _: BadSearch)
    response = client.get('/search?q=maryland')
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


@pytest.mark.parametrize(
    ('backend', 'expected_class'),
    [
        ('alma', AlmaSearch),
        ('primo', PrimoSearch),
        ('worldcat', WorldcatSearch),
    ]
)
def test_get_search_class(backend, expected_class):
    search_class = get_search_class(backend)
    assert search_class is expected_class


def test_get_pagination_links():
    links = get_pagination_links('http://example.com?page=3', last_page=5)
    assert links['first_page'] == 'http://example.com?page=0'
    assert links['prev_page'] == 'http://example.com?page=2'
    assert links['next_page'] == 'http://example.com?page=4'
    assert links['last_page'] == 'http://example.com?page=5'
