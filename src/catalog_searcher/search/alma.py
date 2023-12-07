import logging
from collections import defaultdict
from io import BytesIO
from typing import Sequence

import requests
from environs import Env
from furl import furl
from lxml import etree
from pymods import Genre, MODSReader, MODSRecord
from uritemplate import URITemplate

from catalog_searcher.search import Search, SearchError, SearchResponse, SearchResult
from catalog_searcher.search.cql import cql

logger = logging.getLogger(__name__)


class AlmaSearch(Search):
    xmlns = {
        'mods': 'http://www.loc.gov/mods/v3',
        'srw': 'http://www.loc.gov/zing/srw/',
    }

    def __init__(self, env: Env, endpoint: str, query: str, page: int, per_page: int):
        self.endpoint = endpoint
        self.query = query
        self.page = page
        self.per_page = per_page
        with env.prefixed('ALMA_'):
            self.sru_url_template = URITemplate(env.str('SRU_URL_TEMPLATE'))
            self.institution_code = env.str('INSTITUTION_CODE')
        with env.prefixed('PRIMO_'):
            self.search_url_template = URITemplate(env.str('SEARCH_URL_TEMPLATE'))
            self.item_url_template = URITemplate(env.str('ITEM_URL_TEMPLATE'))

    def search(self) -> SearchResponse:
        # The bento search starts page numbering at 0 (this is a carryover from the
        # original searchumd behavior), so we need to use "page * page_size" instead
        # of the more usual "(page - 1) * page_size" to calculate the record offset
        # for the first page. In addition, the ALMA SRU uses a 1-base "startRecord"
        # index instead of a 0-based offset, so we have to add 1 to our result.
        start_record = (self.page * self.per_page) + 1

        cql_query = cql('alma.all_for_ui', '=', self.query) & ('alma.mms_tagSuppressed', '=', 'false')
        if self.endpoint == 'articles':
            cql_query = cql('alma.genre_form', '=', 'article') & cql_query

        sru_request_url = self.sru_url_template.expand(
            institutionCode=self.institution_code,
            recordSchema='mods',
            query=cql_query,
            maximumRecords=self.per_page,
            startRecord=start_record,
        )
        try:
            response = requests.get(sru_request_url)
        except ConnectionError as e:
            logger.error(f'Search error at url {sru_request_url}\n{e}')
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
                'request_url': sru_request_url,
                'request_params': dict(furl(sru_request_url).args),
                'xml_response': response.text,
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
            link=self.get_preferred_link(item),
        )

    @property
    def module_link(self) -> str:
        return self.search_url_template.expand(query=self.query, vid='01USMAI_SMCM:THSLC1')

    def get_preferred_link(self, item: MODSRecord) -> str:
        record_identifier = item.find('mods:recordInfo/mods:recordIdentifier', namespaces=self.xmlns)
        if record_identifier is not None:
            docid = 'alma' + record_identifier.text
        else:
            docid = ''
        return self.item_url_template.expand(docid=docid, query=self.query, vid='01USMAI_SMCM:THSLC1')


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
