from http import HTTPStatus

import httpretty
import pytest

import catalog_searcher.app
from catalog_searcher.app import app as catalog_searcher_app
from catalog_searcher.app import get_pagination_links, get_search_class
from catalog_searcher.search import Search, SearchError
from catalog_searcher.search.alma import AlmaSearch
from catalog_searcher.search.worldcat import WorldcatSearch


@pytest.fixture()
def app():
    return catalog_searcher_app


@pytest.fixture()
def client(app):
    return app.test_client()


def test_get_root(client):
    response = client.get('/')
    assert response.json == {'status': 'ok'}


def test_get_ping(client):
    response = client.get('/ping')
    assert response.json == {'status': 'ok'}


def test_search_no_query(client):
    response = client.get('/search')
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_search_bad_page(client):
    response = client.get('/search?q=maryland&page=one')
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_search_bad_per_page(client):
    response = client.get('/search?q=maryland&per_page=five')
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_search_bad_backend(client):
    response = client.get('/search?q=maryland&backend=foo')
    assert response.status_code == HTTPStatus.BAD_REQUEST


@httpretty.activate
def test_search(client, shared_datadir, register_search_url):
    register_search_url(body=(shared_datadir / 'alma_response.xml').read_text())
    response = client.get('/search?q=maryland&backend=alma')
    assert response.status_code == HTTPStatus.OK
    assert response.content_type == 'application/json'
    api_response = response.json
    assert api_response['total'] == 108
    assert len(api_response['results']) == 3
    assert api_response['backend'] == 'alma'
    assert api_response['page'] == 1
    assert api_response['per_page'] == 3
    assert api_response['query'] == 'maryland'
    assert 'prev_page' not in api_response


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
        ('worldcat', WorldcatSearch),
    ]
)
def test_get_search_class(backend, expected_class):
    search_class = get_search_class(backend)
    assert search_class is expected_class


def test_get_pagination_links():
    links = get_pagination_links('http://example.com?page=3', last_page=5)
    assert links['first_page'] == 'http://example.com?page=1'
    assert links['prev_page'] == 'http://example.com?page=2'
    assert links['next_page'] == 'http://example.com?page=4'
    assert links['last_page'] == 'http://example.com?page=5'
