from typing import Union

from cql import parse
from cql.parser import CQLBoolean, CQLRelation, CQLSearchClause, CQLTriple


class CQLExpression:
    """Wrapper class to allow for terse construction of CQL queries. The bitwise "and" (`&`)
    and "or" (`|`) operators are overloaded to construct complex expressions.

    Simple query clause, parsed from a string:

        ```pycon
        >>> query = cql('author = John')
        >>> print(query)
        author = John

    Simple query clause, with the parts provided as separate arguments. This lets the
    underlying cql-parser library do the escaping, if necessary:

        ```pycon
        >>> query = cql('title', '=', 'foo bar')
        >>> print(query)
        title = "foo bar"
        ```

    Complex query:

        ```pycon
        >>> complex_query = cql('title', '=', 'foo bar') & 'author = Smith' | 'author = Jones')
        >>> print(complex_query)
        (title = "foo bar" and author = Smith) or author = Jones
        ```

    Forcing evaluation order with parentheses:

        ```pycon
        >>> complex_query = cql('title', '=', 'foo bar') & (cql('author = Smith') | 'author = Jones'))
        >>> print(complex_query)
        title = "foo bar" and (author = Smith or author = Jones)
        ```

    Note the additional `cql()` around the first element in the parenthesized group. This is needed
    to ensure that that group will yield a `CQL` object by having a `CQL` object on the left side of
    `|` operator.
    """
    def __init__(self, cql: CQLSearchClause | CQLTriple):
        self._cql = cql

    @property
    def cql(self):
        return self._cql

    def __str__(self):
        return self.cql.toCQL()

    @classmethod
    def parse(cls, other) -> 'CQLExpression':
        if isinstance(other, str):
            cql_query = parse(other)
            if cql_query is None:
                raise ValueError
            return CQLExpression(cql_query.root)
        if isinstance(other, CQLSearchClause) or isinstance(other, CQLTriple):
            return CQLExpression(other)
        if isinstance(other, tuple) and len(other) == 3:
            index, relation, term = other
            return CQLExpression(CQLSearchClause(index=index, relation=CQLRelation(relation), term=term))
        if isinstance(other, CQLExpression):
            return other
        raise TypeError

    def __and__(self, other: Union['CQLExpression', CQLSearchClause, CQLTriple, tuple]) -> 'CQLExpression':
        return CQLExpression(CQLTriple(left=self.cql, operator=CQLBoolean('and'), right=self.parse(other).cql))

    def __or__(self, other: Union['CQLExpression', CQLSearchClause, CQLTriple, tuple]) -> 'CQLExpression':
        return CQLExpression(CQLTriple(left=self.cql, operator=CQLBoolean('or'), right=self.parse(other).cql))


def cql(*input) -> CQLExpression:
    if len(input) > 1:
        return CQLExpression.parse(input)
    return CQLExpression.parse(input[0])
