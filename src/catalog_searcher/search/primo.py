import logging
import re
from typing import Any, Iterable, Mapping, TypeVar

import requests
from environs import Env
from uritemplate import URITemplate

from catalog_searcher.search import Search, SearchError, SearchResponse, SearchResult

logger = logging.getLogger(__name__)


class PrimoSearch(Search):

    general_formats_map = {
        'null': 'other'
    }

    def __init__(self, env: Env, endpoint: str, query: str, page: int, per_page: int):
        self.endpoint = endpoint
        self.query = query
        self.page = page
        self.per_page = per_page
        self.api_key = env.str('ALMA_API_KEY')
        self.link_resolver_template = URITemplate(env.str('LINK_RESOLVER_TEMPLATE'))
        with env.prefixed('PRIMO_'):
            self.vid = env.str('VID')
            self.book_search_api_url_template = URITemplate(env.str('BOOK_SEARCH_API_URL_TEMPLATE'))
            self.article_search_api_url_template = URITemplate(env.str('ARTICLE_SEARCH_API_URL_TEMPLATE'))
            self.item_url_template = URITemplate(env.str('ITEM_URL_TEMPLATE'))
            self.book_search_url_template = URITemplate(env.str('BOOK_SEARCH_URL_TEMPLATE'))
            self.article_search_url_template = URITemplate(env.str('ARTICLE_SEARCH_URL_TEMPLATE'))

    def search(self) -> SearchResponse:
        # The bento search starts page numbering at 0 (this is a carryover from the
        # original searchumd behavior), so we need to use "page * page_size" instead
        # of the more usual "(page - 1) * page_size" to calculate the record offset
        # for the first page.
        offset = self.page * self.per_page

        if self.endpoint == 'articles':
            api_url_template = self.article_search_api_url_template
            search_url_template = self.article_search_url_template
        else:
            api_url_template = self.book_search_api_url_template
            search_url_template = self.book_search_url_template

        api_search_url = api_url_template.expand(
            vid=self.vid,
            q=self.q,
            offset=offset,
            limit=self.per_page,
        )
        headers = {
            'Authorization': f'apikey {self.api_key}'
        }
        try:
            response = requests.get(api_search_url, headers=headers)
        except ConnectionError as e:
            logger.error(f'Search error at url {api_search_url}\n{e}')
            raise SearchError('Search error', endpoint=self.endpoint)

        if not response.ok:
            logger.error(f'Received {response.status_code} with q={self.query}')
            raise SearchError(f'Received {response.status_code} for q={self.query}', endpoint=self.endpoint)

        data = response.json()

        return SearchResponse(
            results=[self.parse_result(doc) for doc in data['docs']],
            total=data['info']['total'],
            module_link=search_url_template.expand(vid=self.vid, query=self.q),
            raw={'request_url': api_search_url, 'data': data},
        )

    def parse_result(self, item: Mapping[str, Any]) -> SearchResult:
        if 'delivery' in item:
            open_url = item['delivery'].get('almaOpenurl', '')
        display = item['pnx'].get('display', {})
        links = item['pnx'].get('links', {})
        control = item['pnx'].get('control', {})
        addata = item['pnx'].get('addata', {})
        doi = first(get_values(addata, 'doi'))
        mms = first(get_values(display, 'mms'))
        record_id = first(get_values(control, 'recordid'))

        if 'linktohtml' in links:
            link = parse_field(links['linktohtml'][0]).get('U', '')
        elif mms is not None:
            link = self.item_url_template.expand(
                docid=f'alma{mms}',
                vid=self.vid,
                query=self.q,
            )
        elif doi is not None:
            atitle = first(get_values(addata, 'atitle'))
            jtitle = first(get_values(addata, 'jtitle'))
            rft_volume = first(get_values(addata, 'volume'))
            link = self.link_resolver_template.expand(
                rft_id=f'{doi}',
                atitle=f'{atitle}',
                jtitle=f'{jtitle}',
                rft_volume=f'{rft_volume}',
            )
        elif record_id is not None:
            link = self.item_url_template.expand(
                docid=f'{record_id}',
                vid=self.vid,
                query=self.q,
            )
        elif open_url is not None:
            link = open_url
        else:
            link = ''

        creator_data = get_values(display, 'creator', 'contributor')
        creator_fields = [parse_field(v) for v in creator_data]
        creators = [f.get('Q', f.get('', '')) for f in creator_fields]

        return SearchResult(
            title=first(get_values(display, 'vertitle')) or first(get_values(display, 'title')) or '',
            date=first(get_values(display, 'date', 'creationdate')) or '',
            author='; '.join(creators),
            description=first(get_values(display, 'description', 'contents')) or '',
            item_format=get_item_format(self, first(get_values(display, 'type'))) or 'other',
            link=link,
        )

    @property
    def q(self) -> str:
        return ','.join(('any', 'contains', self.query))


def get_item_format(self, raw_type: str) -> str:
    if raw_type in self.general_formats_map:
        return self.general_formats_map[raw_type]
    return raw_type


def get_values(metadata: Mapping[str, list[str]], *keys) -> list[str]:
    """Return the value in metadata for the first key in keys
    that exists. If none of the keys are found, returns an empty
    list."""
    for key in keys:
        try:
            return metadata[key]
        except KeyError:
            pass
    return []


field_match = re.compile(r'\$\$(.)([^$]*)')


def parse_field(field: str) -> dict[str, str]:
    """Parse a field containing `$$X...` tagged metadata and return
    a dictionary mapping the tag letter to the tagged value. For
    example:

        ```pycon
        >>> parse_field('$$ADoe, John$$BJohn Doe, author.')
        {'A': 'Doe, John', 'B': 'John Doe, author.'}
        ```

    If there is additional text data before the first `$$X` tag,
    that text is stored with the empty string as its key:

        ```pycon
        >>> parse_field('Jane Doe, publisher$$QJane Doe')
        {'': 'Jane Doe, publisher', 'Q': 'Jane Doe'}
        ```

    If the field is empty, return an empty dictionary:

        ```pycon
        >>> parse_field('')
        {}
        ```
    """
    if field == '':
        return {}
    if '$' not in field:
        return {'': field}
    data = dict(re.findall(field_match, field))
    if not field.startswith('$'):
        # there is a value before the first "$$X" tag
        data[''] = field[:field.index('$')]
    return data


T = TypeVar('T')


def first(it: Iterable[T]) -> T | None:
    """Return the first item in the iterable, or `None`."""
    try:
        return next(iter(it))
    except StopIteration:
        return None
