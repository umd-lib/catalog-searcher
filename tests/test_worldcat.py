import json
from http import HTTPStatus
from typing import Any, Callable

import httpretty
import pytest
import requests
from environs import Env
from pytest import MonkeyPatch
from requests import ConnectionError

from catalog_searcher.search import SearchError
from catalog_searcher.search.worldcat import WorldcatSearch


@pytest.fixture
def response_body(datadir) -> str:
    return (datadir / 'response.json').read_text()


@pytest.fixture
def no_records_response_body(datadir) -> str:
    return (datadir / 'no_records_response.json').read_text()


@pytest.fixture
def search(env: Env) -> WorldcatSearch:
    return WorldcatSearch(env, endpoint='books-and-more', query='maryland', page=1, per_page=3)


def register_auth_url(token: str = 'TOKEN', status: int = HTTPStatus.OK):
    if status >= HTTPStatus.BAD_REQUEST:
        # we are mocking an error response, omit the token from the body
        httpretty.register_uri(
            uri='https://oauth.oclc.org/token',
            method=httpretty.POST,
            status=status,
        )
    else:
        httpretty.register_uri(
            uri='https://oauth.oclc.org/token',
            method=httpretty.POST,
            status=status,
            adding_headers={'Content-Type': 'application/json'},
            body=json.dumps({'access_token': token}),
        )


@pytest.fixture
def register_search_url(search: WorldcatSearch) -> Callable:
    def _register_search_url(body: str = '', status: int = HTTPStatus.OK):
        if status >= HTTPStatus.BAD_REQUEST:
            # we are mocking an error response, omit the body form the response
            httpretty.register_uri(
                uri=search.search_url.url,
                method=httpretty.GET,
                status=status,
            )
        else:
            httpretty.register_uri(
                uri=search.search_url.url,
                method=httpretty.GET,
                status=status,
                adding_headers={'Content-Type': 'application/json'},
                body=body,
            )

    return _register_search_url


@httpretty.activate
def test_worldcat_search(register_search_url: Callable, response_body: str, search: WorldcatSearch):
    register_auth_url()
    register_search_url(body=response_body)

    response = search()

    assert response.total == 868034
    assert response.module_link == 'https://umaryland.on.worldcat.org/search?expandSearch=off&queryString=maryland'
    assert response.results[0]['title'] == "Michie's annotated code of the public general laws of Maryland"
    assert response.results[0]['link'] == 'https://umaryland.on.worldcat.org/oclc/886895'


@httpretty.activate
def test_worldcat_no_records_response(
    register_search_url: Callable,
    no_records_response_body: str,
    search: WorldcatSearch,
):
    register_auth_url()
    register_search_url(body=no_records_response_body)

    response = search()
    assert response.total == 0
    assert response.results == []


@httpretty.activate
def test_worldcat_search_bad_request(register_search_url: Callable, search: WorldcatSearch):
    register_auth_url()
    register_search_url(status=HTTPStatus.BAD_REQUEST)

    with pytest.raises(SearchError):
        search()


def raise_connection_error(*_args, **_kwargs):
    raise ConnectionError


@httpretty.activate
def test_worldcat_search_connection_error(search: WorldcatSearch, monkeypatch: MonkeyPatch):
    register_auth_url()

    monkeypatch.setattr(requests, 'get', raise_connection_error)
    with pytest.raises(SearchError):
        search()


def test_auth_connection_error(search: WorldcatSearch, monkeypatch: MonkeyPatch):
    monkeypatch.setattr(requests, 'post', raise_connection_error)
    with pytest.raises(RuntimeError):
        search.get_auth_token()


@httpretty.activate
def test_auth_bad_request(search: WorldcatSearch):
    register_auth_url(status=HTTPStatus.BAD_REQUEST)
    with pytest.raises(RuntimeError):
        search.get_auth_token()


@httpretty.activate
def test_auth_none_token(search: WorldcatSearch):
    register_auth_url(token=None)
    with pytest.raises(RuntimeError):
        search.get_auth_token()


@httpretty.activate
def test_auth_empty_token(search: WorldcatSearch):
    register_auth_url(token='')
    with pytest.raises(RuntimeError):
        search.get_auth_token()

@pytest.mark.parametrize(
    ('general_format', 'specific_format', 'expected_format'),
    [
        ('Book', 'Digital', 'e_book'),
        ('Jrnl', '', 'journal'),
        ('QWERTY', '', 'other'),
    ]
)
def test_item_format(search: WorldcatSearch, general_format: str, specific_format: str, expected_format: str):
    stub_item = {
        'generalFormat': general_format,
        'specificFormat': specific_format,
    }
    assert search.get_item_format(stub_item) == expected_format


@pytest.mark.parametrize(
    ('stub_item', 'expected_url'),
    [
        # this result has an OCLC number
        (
            {
                "oclcNumber": "886895",
                "digitalAccessAndLocations": [
                    {"uri": "https://doi.org/gpo123333"},
                    {"uri": "https://purl.fdlp.gov/GPO/gpo123333"},
                    {"uri": "https://www.maryland.va.gov/publications/PatientFlyer2019.pdf"}
                ],
            },
            'https://umaryland.on.worldcat.org/oclc/886895',
        ),
        # this result doesn't have an OCLC number, but does have a DOI link
        (
            {
                "digitalAccessAndLocations": [
                    {"uri": "https://doi.org/gpo123333"},
                    {"uri": "https://purl.fdlp.gov/GPO/gpo123333"},
                    {"uri": "https://www.maryland.va.gov/publications/PatientFlyer2019.pdf"}
                ],
            },
            'https://doi.org/gpo123333',
        ),
        # this is a result that doesn't have an OCLC number or a DOI link
        (
            {
                "digitalAccessAndLocations": [
                    {"uri": "https://purl.fdlp.gov/GPO/gpo123333"},
                    {"uri": "https://www.maryland.va.gov/publications/PatientFlyer2019.pdf"}
                ],
            },
            'https://www.maryland.va.gov/publications/PatientFlyer2019.pdf',
        ),
    ]
)
def test_result_link(search: WorldcatSearch, stub_item: dict[str, Any], expected_url: str):
    assert search.get_preferred_link(stub_item) == expected_url


def test_result_no_link(search: WorldcatSearch):
    assert search.get_preferred_link({}) == 'https://umaryland.on.worldcat.org/discovery'
