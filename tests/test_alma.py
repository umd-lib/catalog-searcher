from http import HTTPStatus
from pathlib import Path
from typing import Callable

import httpretty
import pytest
import requests
from environs import Env
from pytest import MonkeyPatch

from catalog_searcher.search import SearchError
from catalog_searcher.search.alma import AlmaSearch


@pytest.fixture
def search(env: Env) -> AlmaSearch:
    return AlmaSearch(env=env, endpoint='books-and-more', query='maryland', page=1, per_page=3)


@pytest.fixture
def register_search_url(search: AlmaSearch) -> Callable:
    def _register_search_url(body: str = '', status: int = HTTPStatus.OK):
        if status >= HTTPStatus.BAD_REQUEST:
            # we are mocking an error response, omit the body form the response
            httpretty.register_uri(
                uri=search.sru_url_template.expand(institutionCode=search.institution_code),
                method=httpretty.GET,
                status=status,
            )
        else:
            httpretty.register_uri(
                uri=search.sru_url_template.expand(institutionCode=search.institution_code),
                method=httpretty.GET,
                status=status,
                adding_headers={'Content-Type': 'application/json'},
                body=body,
            )
    
    return _register_search_url


@httpretty.activate
def test_alma_search(datadir: Path, register_search_url: Callable, search: AlmaSearch):
    register_search_url(body=(datadir / 'response.xml').read_text())
    
    response = search()

    assert response.total == 108
    assert len(response.results) == 3
    assert response.results[0].title == 'Advances in the theory of Riemann surfaces: proceedings of the 1969 Stony Brook conference'
    assert response.results[0].date == '1971'
    assert response.results[0].author == 'Ahlfors, Lars Valerian, 1907-'
    assert response.results[0].description == (
        'Edited by Lars V. Ahlfors [and others]; '
        'Proceedings of the 2d of a series of meetings; proceedings of the 3d are entered under Conference on Discontinuous Groups and Riemann Surfaces, University of Maryland, 1973.; '
        'Includes bibliographical references.'
    )


@httpretty.activate
def test_alma_search_bad_request(register_search_url: Callable, search: AlmaSearch):
    register_search_url(status=HTTPStatus.BAD_REQUEST)

    with pytest.raises(SearchError):
        search()


@httpretty.activate
def test_worldcat_search_connection_error(search: AlmaSearch, monkeypatch: MonkeyPatch, raise_connection_error: Callable):
    monkeypatch.setattr(requests, 'get', raise_connection_error)
    
    with pytest.raises(SearchError):
        search()
