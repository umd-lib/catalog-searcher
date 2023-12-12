import dataclasses
import logging
from typing import Any, Mapping

import furl
import requests
from environs import Env
from requests import ConnectionError
from requests.auth import HTTPBasicAuth

from catalog_searcher.search import Search, SearchError, SearchResponse, SearchResult, with_key

logger = logging.getLogger(__name__)


class WorldcatSearch(Search):
    """Search class that uses the OCLC Discovery API. See:
    https://developer.api.oclc.org/worldcat-discovery#/Bibliographic%20Resources/search-bibs-details
    """

    general_formats_map = {
        'Archv': 'archival_material',
        'Artcl': 'article',
        'ArtChap': 'article',
        'Music': 'audio',
        'AudioBook': 'audio_book',
        'Book': 'book',
        'CD': 'cd',
        'CompFile': 'computer_file',
        'DVD': 'dvd',
        'Image': 'image',
        'Jrnl': 'journal',
        'LP': 'lp',
        'Map': 'map',
        'News': 'newspaper',
        'MsScr': 'score',
        'Thsis': 'thesis',
        'Video': 'video_recording',
        'Book_Digital': 'e_book',
        'Music_Digital': 'e_music',
        'Video_Digital': 'e_book',
        'Web': 'article',
        'null': 'other'
    }

    def __init__(self, env: Env, endpoint: str, query: str, page: int, per_page: int):
        with env.prefixed('WORLDCAT_'):
            self.search_url = furl.furl(env.str('API_BASE'))
            self.api_key = env.str('CLIENT_ID')
            self.api_secret = env.str('SECRET')
            self.book_item_types = env.str('BOOKS_ITEM_TYPES')
            self.article_item_types = env.str('ARTICLES_ITEM_TYPES')
            self.article_item_subtypes = env.str('ARTICLES_ITEM_SUBTYPES')
            self.subtypes_url = env.str('SUBTYPES_URL')
            self.no_results_url = env.str('NO_RESULTS_URL')
            self.module_url = env.str('MODULE_URL')
        self.endpoint = endpoint
        self.query = query
        self.page = page
        self.per_page = per_page
        # The bento search starts page numbering at 0 (this is a carryover from the
        # original searchumd behavior), so we need to use "page * page_size" instead
        # of the more usual "(page - 1) * page_size" to calculate the record offset
        # for the first page.
        self.offset = page * self.per_page

    def search(self) -> SearchResponse:
        """Run the search, and returns a dictionary representing the API response. If there are any
        errors performing the search, raises a `SearchError`."""
        logger.debug(f'Pagination debug offset={self.offset} page={self.page} limit={self.per_page}')

        # Prepare OCLC API search
        params = {
            'dbIds': 638,
            'q': self.query,
            'limit': self.per_page,
            'offset': self.offset,
            'orderBy': 'library',
            'groupRelatedEditions': 'true',
        }

        match self.endpoint:
            case 'articles':
                params['itemType'] = self.article_item_types
                params['itemSubType'] = self.article_item_subtypes
            case _:
                # Default to books-and-more searcher
                params['itemType'] = self.book_item_types

        headers = {
            'Authorization': 'Bearer ' + self.get_auth_token()
        }

        # Execute OCLC API search
        try:
            response = requests.get(self.search_url.url, params=params, headers=headers)
        except ConnectionError as e:
            logger.error(f'Search error at url {self.search_url.url}, params={params}\n{e}')
            raise SearchError('Search error', endpoint=self.endpoint)

        if not response.ok:
            logger.error(f'Received {response.status_code} with q={self.query}')
            raise SearchError(f'Received {response.status_code} for q={self.query}', endpoint=self.endpoint)

        logger.debug(f'Submitted url={self.search_url.url}, params={params}')
        logger.debug(f'Received response {response.status_code}')

        json_response = response.json()
        total = int(json_response.get('numberOfRecords', 0))

        return SearchResponse(
            results=[dataclasses.asdict(self.parse_result(item)) for item in json_response.get('detailedRecords', [])],
            total=total,
            module_link=self.module_link,
            raw=json_response,
        )

    def parse_result(self, item: Any) -> SearchResult:
        return SearchResult(
            title=item['title'],
            date=item.get('date', ''),
            author=item.get('creator', ''),
            description=item.get('summary', ''),
            item_format=self.get_item_format(item),
            link=self.get_preferred_link(item),
        )

    def get_preferred_link(self, item: Mapping[str, Any]) -> str:
        """Get the preferred link for a single item. If the result has an OCLC number,
        return a `umaryland.on.worldcat` URL. If the result has a DOI URI in its
        locations, return that. Otherwise, return the last URL from the locations.
        Finally, if there are no locations with URIs, return a generic URL."""
        url = None
        oclc_number = item.get('oclcNumber', None)
        if oclc_number is not None:
            return 'https://umaryland.on.worldcat.org/oclc/' + oclc_number

        locations = item.get('digitalAccessAndLocations', [])
        for location in filter(with_key('uri'), locations):
            url = location['uri']
            # DOI is preferred so break and return.
            if url.startswith('https://doi.org/'):
                return url

        if url is not None:
            return url

        return 'https://umaryland.on.worldcat.org/discovery'

    def get_item_format(self, item: Mapping[str, Any]) -> str:
        """Get the item format for a single item. Looks up the format in the
        `general_formats_map`. If there is no matching format found, returns
        "other"."""
        general_format = item.get('generalFormat', '')
        specific_format = item.get('specificFormat', '')
        if general_format in ['Book', 'Music', 'Video'] and specific_format == 'Digital':
            format_key = general_format + '_' + specific_format
        else:
            format_key = general_format
        try:
            return self.general_formats_map[format_key]
        except KeyError as key_error:
            logger.error(f'Missing format {key_error}')
            return 'other'

    def get_auth_token(self) -> str:
        try:
            response = requests.post(
                url='https://oauth.oclc.org/token',
                params={
                    'scope': 'WorldCatDiscoveryAPI',
                    'grant_type': 'client_credentials'
                },
                auth=HTTPBasicAuth(self.api_key, self.api_secret),
            )
        except ConnectionError as e:
            logger.error(f'Auth error {e}')
            raise RuntimeError('Backend auth error') from e

        if not response.ok:
            logger.error(f'Auth token error: {response}')
            raise RuntimeError('Auth token error')

        token = response.json().get('access_token', None)
        if token is None or token == '':
            raise RuntimeError('Auth token error')

        return str(token)

    @property
    def module_link(self) -> str:
        if self.endpoint == 'articles':
            return self.module_url + '?' + self.subtypes_url + '&queryString=' + self.query
        else:
            return self.module_url + '?expandSearch=off&queryString=' + self.query
