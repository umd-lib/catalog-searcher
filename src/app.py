import json
import logging
import furl
import os
import requests

from flask import Flask, request
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
from waitress import serve
from paste.translogger import TransLogger
from authliboclc import wskey, user

# Employs the OCLC Discovery API. See:
# https://developer.api.oclc.org/worldcat-discovery#/Bibliographic%20Resources/search-bibs-details

load_dotenv('../.env')

env = {}
for key in ('WORLDCAT_AUTHENTICATING_INSTITUTION_ID',
            'WORLDCAT_DISCOVERY_API_WSKEY',
            'WORLDCAT_DISCOVERY_API_SECRET',
            'WORLDCAT_OPEN_URL_RESOLVER_WSKEY',
            'WORLDCAT_CONTEXT_INSTITUTIONAL_ID',
            'RESOLVER_SERVICE_LINK', 'NO_RESULTS_URL',
            'MODULE_URL', 'WORLDCAT_API_BASE'):
    env[key] = os.environ.get(key)
    if env[key] is None:
        raise RuntimeError(f'Missing environment variable: {key}')

search_url = furl.furl(env['WORLDCAT_API_BASE'])
key = env['WORLDCAT_DISCOVERY_API_WSKEY']
client_secret = env['WORLDCAT_DISCOVERY_API_SECRET']
institutional_id = env['WORLDCAT_AUTHENTICATING_INSTITUTION_ID']
context_id = env['WORLDCAT_CONTEXT_INSTITUTIONAL_ID']
resolver_wskey = env['WORLDCAT_OPEN_URL_RESOLVER_WSKEY']
resolver_service_link = env['RESOLVER_SERVICE_LINK']

no_results_url = env['NO_RESULTS_URL']
module_url = env['MODULE_URL']

debug = os.environ.get('FLASK_ENV')

logger = logging.getLogger('worldcat-searcher')
loggerWaitress = logging.getLogger('waitress')

if debug:
    logger.setLevel(logging.DEBUG)
    loggerWaitress.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)
    loggerWaitress.setLevel(logging.INFO)

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False


@app.route('/')
def root():
    return {'status': 'ok'}


@app.route('/ping')
def ping():
    return {'status': 'ok'}


@app.route('/search')
def search():
    args = request.args

    # Defaulting to books and more search. Confirm with stakeholders.
    endpoint = 'books-and-more'
    if 'endpoint' in args and args['endpoint'] == 'articles':
        endpoint = 'articles'

    # Check query param
    if 'q' not in args or args['q'] == '':
        return {
            'endpoint': endpoint,
            'error': {
                'msg': 'q parameter is required',
            },
        }, 400
    query = args['q']

    limit = 3
    if 'per_page' in args and args['per_page'] != "":
        limit = int(args['per_page'])

    offset = 0
    page = 1
    if 'page' in args and args['page'] != "":
        page = int(args['page'])
        if page > 1:
            offset = limit * (page - 1) + 1

    logger.debug(f'Pagination debug offset={offset} page={page} limit={limit}')

    # Prepare OCLC API search
    params = {
        'q': query,
        'limit': limit,
        'itemsPerPage': 10,
        'offset': offset,
        'startIndex': offset,
        'sortBy': 'library_plus_relevance',
        'dbIds': '638'
        # 'orderBy': 'library',
        # 'groupRelatedEditions': 'true',
    }

    token = authorize_oclc()

    if token is None or token == '':
        return {
            'error': {
                'msg': 'Auth token error',
            }
        }

    module_link = module_url + '?queryString=' + query

    if endpoint == 'articles':
        params['itemType'] = 'artchap'

    headers = {
        'Authorization': 'Bearer ' + token
    }

    # Execute OCLC API search
    try:
        response = requests.get(search_url.url, params=params, headers=headers)
    except Exception as err:
        logger.error(f'Search error at url'
                     '{search_url.url}, params={params}\n{err}')
        return {
            'endpoint': endpoint,
            'results': [],
            'error': {
                'msg': f'Search error',
            },
        }, 500

    if response.status_code not in [200, 206]:
        logger.error(f'Received {response.status_code} with q={query}')
        return {
            'endpoint': endpoint,
            'results': [],
            'error': {
                'msg': f'Received {response.status_code} for q={query}',
            },
        }, 500

    logger.debug(f'Submitted url={search_url.url}, params={params}')
    logger.debug(f'Received response {response.status_code}')

    json_raw = json.loads(response.text)

    if '@graph' in json_raw:
        graph = json_raw['@graph'][0]

    total_records = get_total_records(graph)

    api_response = {
        'endpoint': endpoint,
        'version': "legacy",
        'query': query,
        'per_page': limit,
        'page': page,
        'total': total_records,
        'module_link': module_link,
    }

    if debug:
        api_response['raw'] = graph
    if total_records != 0 and 'discovery:hasPart' in graph:
        json_content = graph['discovery:hasPart']
        api_response['results'] = build_response(json_content, limit, endpoint)
    else:
        api_response['error'] = build_no_results()
        api_response['results'] = []
    return api_response


def authorize_oclc():
    scope = 'WorldCatDiscoveryAPI'
    my_wskey = wskey.Wskey(
        key=key,
        secret=client_secret,
        options={
            'services': ['WorldCatDiscoveryAPI']
        }
    )

    access_token = my_wskey.get_access_token_with_client_credentials(
        authenticating_institution_id=institutional_id,
        context_institution_id=context_id
    )

    return access_token.access_token_string


def build_no_results():
    return {
        'msg': 'No Results',
        'no_results_url': no_results_url,
    }


def build_response(json_content, limit, endpoint):
    results = []
    limit_check = 0
    for item in json_content:
        if 'schema:about' in item:
            item_format = get_item_format(item['schema:about'])
            item_name = get_item_title(item['schema:about'])
            item_date = get_item_date(item['schema:about'])
            item_author = get_item_author(item['schema:about'])
            item_url = get_resource_url(item)
            item_desc = get_description(item['schema:about'])

        if item_name is not None:
            results.append({
                'title': item_name,
                'date': item_date,
                'author': item_author,
                'item_format': item_format,
                'link': item_url,
                'description': item_desc
            })
            limit_check = limit_check + 1

        if limit_check >= limit:
            break
    return results


def get_total_records(json_content):
    if 'discovery:totalResults' not in json_content:
        return None
    return int(json_content['discovery:totalResults']['@value'])


def get_resource_url(item):
    proxy_prefix = 'https://proxy-um.researchport.umd.edu/login?url='
    if 'schema:about' in item:
        about = item['schema:about']
        if 'schema:sameAs' in about:
            # seems some (but not all) articles hide the url here
            same_as = about['schema:sameAs']
            if '@id' in same_as:
                if 'doi.org/' in same_as['@id']:
                    return proxy_prefix + same_as['@id']
                
        if 'schema:url' in about:
            for url in about['schema:url']:
                # seems some books hide the url here
                if isinstance(url, str):
                    # it seems some of these are coming through as blank
                    # strings rather than arrays
                    continue
                if '@id' in url:
                    if 'doi.org/' in url['@id']:
                        # and really really prefer a DOI
                        return proxy_prefix + url['@id']

    # otherwise we construct a link from the oclc number
    # this is our catch-all
    oclc_num = None
    if 'http://www.w3.org/2007/05/powder-s#describedby' in item:
        described_by = item['http://www.w3.org/2007/05/powder-s#describedby']
        if 'library:oclcnum' in described_by:
            oclc_num = described_by['library:oclcnum']
    if oclc_num is not None and oclc_num.isnumeric():
        return 'https://umaryland.on.worldcat.org/oclc/' + oclc_num
    if '@id' in item:
        oclc_num = item['@id'].replace('http://www.worldcat.org/title/-/oclc/', '')
    if oclc_num is not None and oclc_num.isnumeric():
        return 'https://umaryland.on.worldcat.org/oclc/' + oclc_num
    # if we really have to, fallback to search URL
    return 'https://umaryland.on.worldcat.org/discovery'


def get_description(content):
    if 'schema:description' in content:
        desc = content['schema:description']
        if '@value' in desc:
            return desc['@value']
    return None


def get_item_title(content):
    if 'schema:name' in content:
        name = content['schema:name']
        if '@value' in name:
            return name['@value']
        if name is not None:
            return name
    return None


def get_item_date(content):
    if 'schema:datePublished' in content:
        date = content['schema:datePublished']
        if date is not None:
            return date
    return None


def get_item_author(content):
    if 'schema:author' in content:
        author = content['schema:author']
        if 'schema:name' in author:
            return author['schema:name']

    if 'schema:creator' in content:
        creator = content['schema:creator']
        if 'schema:name' in creator:
            return creator['schema:name']
    return None


def get_item_format(schema_about):
    general_formats_map = {
        'http://purl.org/library/ArchiveMaterial': 'archival_material',
        'http://schema.org/Article': 'article',
        'schema:Article': 'article',
        'schema:ScholarlyArticle': 'article',
        'http://bibliograph.net/AudioBook': 'audio_book',
        'http://schema.org/Book': 'book',
        'http://schema.org/Hardcover': 'book',
        'http://bibliograph.net/LargePrintBook': 'book',
        'http://schema.org/Paperback': 'book',
        'http://bibliograph.net/PrintBook': 'book',
        'http://bibliograph.net/CD': 'cd',
        'http://www.productontology.org/id/Compact_Disc': 'cd',
        'http://bibliograph.net/ComputerFile': 'computer_file',
        'http://bibliograph.net/DVD': 'dvd',
        'http://www.productontology.org/doc/DVD': 'dvd',
        'http://schema.org/EBook': 'e_book',
        'http://bibliograph.net/Image': 'image',
        'http://www.productontology.org/doc/Image': 'image',
        'http://purl.org/library/VisualMaterial': 'image',
        'http://schema.org/Periodical': 'journal',
        'http://purl.org/library/Serial': 'journal',
        'http://bibliograph.net/LPRecord': 'lp',
        'http://www.productontology.org/id/LP_record': 'lp',
        'http://bibliograph.net/Atlas': 'map',
        'http://schema.org/Map': 'map',
        'http://bibliograph.net/Newspaper': 'newspaper',
        'http://bibliograph.net/MusicScore': 'score',
        'http://purl.org/ontology/mo/Score': 'score',
        'http://www.productontology.org/id/Sheet_music': 'score',
        'http://bibliograph.net/Thesis': 'thesis',
        'http://www.productontology.org/id/Thesis': 'thesis',
        'Streaming audio': 'e_music',
        'Downloadable audio file': 'e_music',
        'Internet videos': 'e_video',
        'Streaming videos': 'e_video',
        'schema:Book': 'book',
        'schema:EBook': 'e_book',
        'http://www.w3.org/2006/gen/ont#InformationResource': 'other',
    }

    # this is called in the Ruby lib: https://github.com/OCLC-Developer-Network/worldcat-discovery-ruby/blob/d3c84863df2aa129a351fc0b365ea2ca68b3f2ec/lib/worldcat/discovery/bib.rb#L243
    book_format = None
    if 'schema:bookFormat' in schema_about:
        book_formats = schema_about['schema:bookFormat']
        try:
            format = book_formats['@id']
            book_format = general_formats_map[format]
        except KeyError as key_error:
            # Is KeyError catching really the only way to do this?
            # Seems ugly to me. But None and empty string validation
            # don't seem to always work for key checking in Python.
            book_format = None

    if book_format is not None:
        return book_format

    test_type = None
    if '@type' in schema_about:
        types = schema_about['@type']
        for type in types:
            try:
                test_type = general_formats_map[type]
            except KeyError as key_error:
                # Do nothing. See comment above.
                continue

    if test_type is not None:
        return test_type
    return 'other'


if __name__ == '__main__':
    # This code is not reached when running "flask run". However the Docker
    # container runs "python app.py" and host='0.0.0.0' is set to ensure
    # that flask listens on port 5000 on all interfaces.

    # Run waitress WSGI server
    serve(TransLogger(app, setup_console_handler=True),
          host='0.0.0.0', port=5000, threads=10)
