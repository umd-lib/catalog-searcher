from pathlib import Path
from typing import Callable

import httpretty
import pytest
import requests
from environs import Env

from catalog_searcher.search import SearchError
from catalog_searcher.search.primo import PrimoSearch, parse_field


@httpretty.activate
def test_primo_article_search(primo_article_search, primo_article_search_request_args):
    httpretty.register_uri(**primo_article_search_request_args)
    response = primo_article_search()
    assert response.total == 377254
    assert len(response.results) == 3
    assert response.results[0].title == 'Maryland'
    assert response.results[0].author == 'Haines, Chelsea E.'
    assert response.results[0].description == (
        'The equity of Maryland’s P–12 education formula has long been scrutinized and challenged in court. '
        'Changes to Maryland’s P–12 funding formula occurred following a successful legislative override during the '
        '2021 session following the governor’s 2020 veto of the Blueprint for Maryland’s Future Act. '
        'The new P–12 formula includes 13 categories: Foundation Aid, Transportation Aid, Compensatory Education Aid, '
        'English Learner Aid, Special Education Aid, Guaranteed Tax Base Aid, Comparable Wage Index Aid, Post College '
        'and Career Readiness Pathways Aid, Concentration of Poverty Aid, Transitional Supplemental Instruction Aid, '
        'Prekindergarten Aid, and Career Ladder Aid. Funding formula changes were implemented in FY2023, following '
        'delays in reporting and the COVID-19 pandemic. No changes were made to higher education funding formulas. '
        'The state allocated $7.3 billion for P–12 education in FY2022, 15.2% of the state budget. The state allocated '
        '$4.8 billion for higher education in FY2022, 7.9% of the state budget. FY2023 allocations for higher '
        'education will include a $59.5 million settlement for Maryland’s historically Black colleges and universities.'
    )
    assert response.results[0].item_format == "article"


@httpretty.activate
def test_primo_book_search(primo_book_search: PrimoSearch, primo_book_search_request_args: str):
    httpretty.register_uri(**primo_book_search_request_args)
    response = primo_book_search()

    assert response.total == 387
    assert len(response.results) == 3
    assert response.results[0].title == 'Feriado '
    # noqa
    assert response.results[0].author == 'Araujo, Diego; Skartveit, Hanne-Lovise; Luna Films; Centro de Estudios para la Producción Audiovisual (Argentina); Abaca Films'  # noqa: E501


@httpretty.activate
def test_primo_search_bad_request(
    register_bad_request: Callable,
    primo_article_search: PrimoSearch,
    primo_article_search_url: str,
):
    register_bad_request(primo_article_search_url)

    with pytest.raises(SearchError):
        primo_article_search()


def test_primo_search_connection_error(
    primo_article_search: PrimoSearch,
    monkeypatch: pytest.MonkeyPatch,
    raise_connection_error: Callable,
):
    monkeypatch.setattr(requests, 'get', raise_connection_error)

    with pytest.raises(SearchError):
        primo_article_search()


@pytest.mark.parametrize(
    ('field', 'expected_dict'),
    [
        ('', {}),
        ('$$Afoo', {'A': 'foo'}),
        ('$$Afoo$$B123', {'A': 'foo', 'B': '123'}),
        ('$$Afoo$$B123$$C', {'A': 'foo', 'B': '123', 'C': ''}),
        ('foo$$Qbar', {'': 'foo', 'Q': 'bar'}),
        ('notags', {'': 'notags'}),
    ]
)
def test_parse_field(field, expected_dict):
    assert parse_field(field) == expected_dict
