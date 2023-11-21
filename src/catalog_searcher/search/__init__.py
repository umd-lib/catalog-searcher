from abc import ABC
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, NamedTuple

from environs import Env


def with_key(key: str) -> Callable[[Mapping], bool]:
    def _with_key(item: Mapping[str, Any]) -> bool:
        return key in item and item[key] is not None
    return _with_key


class SearchError(Exception):
    def __init__(self, *args, endpoint: str = ''):
        super().__init__(*args)
        self.endpoint = endpoint


@dataclass
class SearchResult:
    title: str
    date: str = ''
    author: str = ''
    description: str = ''
    item_format: str = ''
    link: str = ''


class SearchResponse(NamedTuple):
    results: list
    total: int
    module_link: str
    raw: Mapping[str, Any]


class Search(ABC):
    """Abstract base class for search implementations."""
    def __init__(self, env: Env, endpoint: str, query: str, page: int, per_page: int):
        raise NotImplementedError
    
    def search(self) -> SearchResponse:
        raise NotImplementedError

    def __call__(self, *args, **kwargs) -> SearchResponse:
        """Alias for `search()`"""
        return self.search(*args, **kwargs)
    
    def parse_result(self, item: Any) -> SearchResult:
        raise NotImplementedError
