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

# Employs the OCLC Discovery API. See:
# https://developer.api.oclc.org/worldcat-discovery#/Bibliographic%20Resources/search-bibs-details

load_dotenv('../.env')

env = {}
for key in ('WORLDCAT_CLIENT_ID', 'WORLDCAT_SECRET', 'WORLDCAT_API_BASE',
            'WORLDCAT_BOOKS_ITEM_TYPES', 'WORLDCAT_ARTICLES_ITEM_TYPES',
            'WORLDCAT_ARTICLES_ITEM_SUBTYPES', 'NO_RESULTS_URL'):
    env[key] = os.environ.get(key)
    if env[key] is None:
        raise RuntimeError(f'Missing environment variable: {key}')

search_url = furl.furl(env['WORLDCAT_API_BASE'])
api_key = env['WORLDCAT_CLIENT_ID']
api_secret = env['WORLDCAT_SECRET']
book_item_types = env['WORLDCAT_BOOKS_ITEM_TYPES']
article_item_types = env['WORLDCAT_ARTICLES_ITEM_TYPES']
article_item_subtypes = env['WORLDCAT_ARTICLES_ITEM_SUBTYPES']
no_results_url = env['NO_RESULTS_URL']

basic = HTTPBasicAuth(api_key, api_secret)

debug = os.environ.get('FLASK_ENV') == 'development'

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
        'offset': offset,
        'orderBy': 'library',
        'groupRelatedEditions': 'true',
    }

    match endpoint:
        case 'articles':
            params['itemType'] = article_item_types
            params['itemSubType'] = article_item_subtypes
        case _:
            # Default to books-and-more searcher
            params['itemType'] = book_item_types

    token = authorize_oclc()

    if token is None or token == '':
        return {
            'error': {
                'msg': 'Auth token error',
            }
        }

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
            'error': {
                'msg': f'Search error',
            },
        }, 500

    if response.status_code not in [200, 206]:
        logger.error(f'Received {response.status_code} with q={query}')

        return {
            'endpoint': endpoint,
            'error': {
                'msg': f'Received {response.status_code} for q={query}',
            },
        }, 500

    logger.debug(f'Submitted url={search_url.url}, params={params}')
    logger.debug(f'Received response {response.status_code}')

    json_content = json.loads(response.text)
    total_records = get_total_records(json_content)

    api_response = {
        'endpoint': endpoint,
        'query': query,
        'per_page': limit,
        'page': page,
        'total': total_records,
    }

    if debug:
        api_response['raw'] = json_content

    if total_records != 0:
        api_response['results'] = build_response(json_content)
    else:
        api_response['error'] = build_no_results()

    return api_response


def authorize_oclc():
    params = {
        'scope': 'WorldCatDiscoveryAPI',
        'grant_type': 'client_credentials'
    }

    token = ''
    try:
        response = requests.post('https://oauth.oclc.org/token',
                                 params=params, auth=basic)
    except Exception as err:
        logger.error(f'Auth error {err}')

        return {
            'error': {
                'msg': 'Backend auth error',
            },
        }, 500

    auth = json.loads(response.text)
    token = auth['access_token']

    return token


def build_no_results():
    return {
        'msg': 'No Results',
        'no_results_url': no_results_url,
    }


def build_response(json_content):
    results = []
    if 'detailedRecords' in json_content:
        for item in json_content['detailedRecords']:
            general_format = item['generalFormat'] if 'generalFormat' \
                in item else 'null'
            specific_format = item['specificFormat'] if 'specificFormat' \
                in item else 'null'
            results.append({
                'title': item['title'],
                'date': item['date'] if 'date' in item else 'null',
                'author': item['creator'] if 'creator' in item else 'null',
                'format': build_item_format(general_format, specific_format),
                'link': build_resource_url(item)
            })
    return results


def get_total_records(json_content):
    if 'numberOfRecords' not in json_content:
        return None
    return int(json_content['numberOfRecords'])


def build_resource_url(item):
    url = None
    if 'digitalAccessAndLocations' in item and \
            item['digitalAccessAndLocations'] is not None:
        for locations in item['digitalAccessAndLocations']:
            if 'uri' in locations and locations['uri'] is not None:
                url = locations['uri']
                # DOI is preferred so break and return.
                if 'https://doi.org/' in url:
                    return url
    if url is not None:
        return url
    if 'oclcNumber' in item and item['oclcNumber'] is not None:
        return 'https://umaryland.on.worldcat.org/oclc/' + item['oclcNumber']
    return 'https://umaryland.on.worldcat.org/discovery'


def build_item_format(general_format, specific_format):
    f = general_format
    if general_format in ['Book', 'Music', 'Video'] \
            and specific_format == 'Digital':
        f = general_format + '_' + specific_format
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
        'null': 'other'
    }

    try:
        return general_formats_map[f]
    except KeyError as key_error:
        logger.error(f'Missing format {key_error}')
        return 'other'


if __name__ == '__main__':
    # This code is not reached when running "flask run". However the Docker
    # container runs "python app.py" and host='0.0.0.0' is set to ensure
    # that flask listens on port 5000 on all interfaces.

    # Run waitress WSGI server
    serve(TransLogger(app, setup_console_handler=True),
          host='0.0.0.0', port=5000, threads=10)
