from unittest.mock import MagicMock

import pytest
from pymods import Genre, MODSRecord

from catalog_searcher.search.alma import GenreLookup, get_item_format


@pytest.mark.parametrize(
    ('issuance', 'form', 'genre', 'expected_format'),
    [
        (['monographic'], ['print'], [], 'book'),
        (['monographic'], ['computer'], [], 'e_book'),
        (['monographic'], ['online resource'], [], 'e_book'),
        (['monographic'], ['electronic resource'], [], 'e_book'),
        (['monographic'], ['videorecording'], [], 'video_recording'),
        (['monographic'], [], [('marcgt', 'videorecording')], 'video_recording'),
        (['monographic'], ['sound recording'], [], 'sound recording'),
        (['monographic'], ['map'], [], 'map'),
        (['serial'], [], [('marcgt', 'newspaper')], 'newspaper'),
        (['serial'], [], [('marcgt', 'periodical')], 'journal'),
        (['serial'], [], [('fast', 'Periodicals.')], 'journal'),
        (['serial'], [], [('marcgt', 'series')], 'journal'),
        (['integrating resource'], [], [('marcgt', 'database')], 'database'),
        ([], [], [], 'other'),
    ]
)
def test_get_item_format(issuance, form, genre, expected_format):
    genre_list = [MagicMock(spec=Genre, authority=g[0], text=g[1]) for g in genre]
    item = MagicMock(spec=MODSRecord, issuance=issuance, form=form, genre=genre_list)

    assert get_item_format(item) == expected_format


def test_genre_lookup():
    genre = [('marcgt', 'newspaper'), ('fast', 'Periodicals.')]
    genre_list = [MagicMock(spec=Genre, authority=g[0], text=g[1]) for g in genre]

    genres = GenreLookup().parse(genre_list)
    assert 'newspaper' in genres.marcgt
    assert 'Periodicals.' in genres.fast
    assert 'foobar' not in genres.marcgt
    assert 'newspaper' not in genres.foobar
