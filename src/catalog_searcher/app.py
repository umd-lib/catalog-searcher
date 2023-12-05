import logging
from http import HTTPStatus
from math import ceil

from environs import Env
from flask import Flask, request
from urlobject import URLObject

from catalog_searcher.search import Search, SearchError

env = Env()
env.read_env()

debug = env.bool('FLASK_DEBUG', default=False)
default_page = env.int('DEFAULT_PAGE', 1)
default_per_page = env.int('DEFAULT_PER_PAGE', 3)
default_backend = env.str('SEARCH_BACKEND', 'alma')

logging.basicConfig(
    level=logging.DEBUG if debug else logging.INFO,
    format='%(levelname)s:%(name)s:%(threadName)s:%(message)s',
)

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
        return error_response(endpoint, message='q parameter is required')
    query = args['q']

    try:
        per_page = int(args.get('per_page', default_per_page))
    except ValueError:
        return error_response(endpoint, message='per_page parameter value is invalid; must be an integer')

    try:
        page = int(args.get('page', default_page))
    except ValueError:
        return error_response(endpoint, message='page parameter value is invalid; must be an integer')
    
    backend = args.get('backend', default_backend)
    try:
        search_class = get_search_class(backend)
    except ValueError as e:
        return error_response(endpoint, message=str(e))

    try:
        response = search_class(env, endpoint, query, page, per_page).search()
    except SearchError as e:
        return error_response(endpoint, message=str(e), status=HTTPStatus.INTERNAL_SERVER_ERROR)
    
    last_page = ceil(response.total / per_page)
    
    api_response = {
        'results': response.results,
        'total': response.total,
        'endpoint': endpoint,
        'query': query,
        'page': page,
        'per_page': per_page,
        'module_link': response.module_link,
        'backend': backend,
        **get_pagination_links(request.url, last_page=last_page)
    }
    
    if debug:
        api_response['raw'] = response.raw

    return api_response


def get_search_class(backend: str) -> Search:
    match backend:
        case 'worldcat':
            from catalog_searcher.search.worldcat import WorldcatSearch
            return WorldcatSearch
        case 'alma':
            from catalog_searcher.search.alma import AlmaSearch
            return AlmaSearch
        case _:
            raise ValueError(f'unknown backend "{backend}"')


def get_pagination_links(request_url: str, last_page: int, first_page: int = 1, page_param: str = 'page') -> dict[str, str]:
    url = URLObject(request_url)
    page = int(url.query_dict.get(page_param, 1))
    links = {
        'first_page': url.set_query_param(page_param, first_page),
        'last_page': url.set_query_param(page_param, last_page),
    }
    if page > first_page:
        links['prev_page'] = url.set_query_param(page_param, page - 1)
    if page < last_page:
        links['next_page'] = url.set_query_param(page_param, page + 1)
    
    return links


def error_response(endpoint: str, message: str, status: int = HTTPStatus.BAD_REQUEST) -> tuple[dict, int]:
    """Utility function for returning a simple error response."""
    return {'endpoint': endpoint, 'error': {'msg': message}}, status
