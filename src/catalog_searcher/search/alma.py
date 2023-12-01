import logging
from collections import defaultdict
from io import BytesIO
from typing import Sequence

import requests
from environs import Env
from furl import furl
from lxml import etree
from pymods import Genre, MODSReader, MODSRecord

from catalog_searcher.search import Search, SearchError, SearchResponse, SearchResult
from catalog_searcher.search.cql import cql

logger = logging.getLogger(__name__)


class AlmaSearch(Search):
    xmlns = {
        'srw': 'http://www.loc.gov/zing/srw/',
    }

    def __init__(self, env: Env, endpoint: str, query: str, page: int, per_page: int):
        self.endpoint = endpoint
        self.query = query
        self.page = page
        self.per_page = per_page
        with env.prefixed('ALMA_'):
            self.sru_base_url = env.str('SRU_BASE_URL')

    def search(self) -> SearchResponse:
        # ALMA SRU uses a 1-base "startRecord" index instead of a 0-based offset
        start_record = (self.page - 1) * self.per_page + 1
        
        cql_query = cql('alma.all_for_ui', '=', self.query) & ('alma.mms_tagSuppressed', '=', 'false')
        if self.endpoint == 'articles':
            cql_query = cql('alma.genre_form', '=', 'article') & cql_query

        params = {
            'version': '1.2',
            'operation': 'searchRetrieve',
            'recordSchema': 'mods',
            'query': str(cql_query),
            'maximumRecords': self.per_page,
            'startRecord': start_record,
        }
        try:
            response = requests.get(self.sru_base_url, params=params)
        except ConnectionError as e:
            logger.error(f'Search error at url {self.sru_base_url}, params={params}\n{e}')
            raise SearchError('Search error', endpoint=self.endpoint)

        if not response.ok:
            logger.error(f'Received {response.status_code} with q={self.query}')
            raise SearchError(f'Received {response.status_code} for q={self.query}', endpoint=self.endpoint)

        doc = etree.fromstring(response.content)
        total = int(doc.xpath('//srw:numberOfRecords/text()', namespaces=self.xmlns, smart_strings=False)[0])

        return SearchResponse(
            results=[self.parse_result(record) for record in MODSReader(BytesIO(response.content))],
            total=total,
            module_link=self.module_link,
            raw={
                'request_url': furl(url=self.sru_base_url, args=params).url,
                'request_params': params,
                #'xml_response': response.text,
            },
        )

    def parse_result(self, item: MODSRecord) -> SearchResult:
        logger.debug(f'  form: {item.form}')
        logger.debug(f'  issuance: {item.issuance}')
        logger.debug(f'  genres: {[(g.authority, g.text) for g in item.genre]}')

        item_format = get_item_format(item)
        logger.debug(item_format)

        return SearchResult(
            title=item.titles[0],
            author='; '.join(name.text for name in item.names),
            date='; '.join(date.text for date in item.dates or []),
            description='; '.join(note.text for note in item.note),
            item_format=item_format,
            link=self.module_link,
        )

    @property
    def module_link(self) -> str:
        return "TODO"


def get_item_format(item: MODSRecord) -> str:
    genres = GenreLookup().parse(item.genre)

    if 'monographic' in item.issuance:
        if 'videorecording' in item.form or 'videorecording' in genres.marcgt:
            return 'video_recording'
        if 'sound recording' in item.form:
            return 'sound recording'
        if 'map' in item.form or 'map' in genres.marcgt:
            return 'map'
        if 'computer' in item.form or 'online resource' in item.form or 'electronic resource' in item.form:
            return 'e_book'
        if 'print' in item.form:
            return 'book'
        
    if 'serial' in item.issuance:
        if 'newspaper' in genres.marcgt:
            return 'newspaper'
        if 'periodical' in genres.marcgt or 'Periodicals.' in genres.fast or 'series' in genres.marcgt:
            return 'journal'
    
    if 'integrating resource' in item.issuance:
        if 'database' in genres.marcgt:
            return 'database'
    
    return 'other'


class GenreLookup:
    def __init__(self):
        self.genres = defaultdict(list)

    def parse(self, genres: Sequence[Genre]):
        for genre in filter(lambda g: g.authority is not None, genres):
            self.genres[genre.authority].append(genre.text)
        return self

    def __getattr__(self, __name: str) -> list[str]:
        return self.genres.get(__name, [])
        