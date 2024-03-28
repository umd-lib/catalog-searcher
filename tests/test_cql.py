import pytest
from cql.parser import CQLBoolean, CQLRelation, CQLSearchClause, CQLTriple

from catalog_searcher.search.cql import CQLExpression, cql


def test_simple_query():
    query = cql('author = John')
    assert str(query) == 'author = John'


def test_simple_query_tuple():
    query = cql('title', '=', 'foo bar')
    assert str(query) == 'title = "foo bar"'


def test_complex_query():
    query = cql('title', '=', 'foo bar') & 'author = Smith' | 'author = Jones'
    assert str(query) == '(title = "foo bar" and author = Smith) or author = Jones'


def test_parentheses():
    query = cql('title', '=', 'foo bar') & (cql('author', '=', 'Smith') | ('author', '=', 'Jones'))
    assert str(query) == 'title = "foo bar" and (author = Smith or author = Jones)'


@pytest.mark.parametrize(
    ('other',),
    [
        # string
        ('author = Jones',),
        # tuple
        (('author', '=', 'Jones'),),
        # CQL object
        (cql('author', '=', 'Jones'),),
        # CQLSearchClause object
        (CQLSearchClause(index='author', relation=CQLRelation('='), term='Jones'),),
        # CQLTriple object
        (CQLTriple(left=cql('author', '=', 'Smith'), operator=CQLBoolean('or'), right=cql('author', '=', 'Jones')),),
    ]
)
def test_valid_boolean_other_types(other):
    query = cql('title', '=', 'foo') & other
    assert isinstance(query, CQLExpression)


@pytest.mark.parametrize(
    ('other',),
    [
        # number
        (123,),
        # list
        ([1, 2, 3],),
        # set
        ({1, 2, 3},),
        # dictionary
        ({'a': 1, 'b': 2, 'c': 3},),
    ]
)
def test_invalid_boolean_other_types(other):
    with pytest.raises(TypeError):
        cql('title', '=', 'foo') | other
