import logging
from http import HTTPStatus
from math import ceil

from environs import Env
from flask import Flask, request
from furl import furl
from paste.translogger import TransLogger
from waitress import serve

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
    
    first_page = 1
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
    }
    url = furl(request.url)
    url.query.params['page'] = first_page
    api_response['first_page'] = str(url)
    url.query.params['page'] = last_page
    api_response['last_page'] = str(url)
    if page > first_page:
        url.query.params['page'] = page - 1
        api_response['prev_page'] = str(url)
    if page < last_page:
        url.query.params['page'] = page + 1
        api_response['next_page'] = str(url)
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


def error_response(endpoint: str, message: str, status: int = HTTPStatus.BAD_REQUEST) -> tuple[dict, int]:
    """Utility function for returning a simple error response."""
    return {'endpoint': endpoint, 'error': {'msg': message}}, status


if __name__ == '__main__':
    # This code is not reached when running "flask run". However, the Docker
    # container runs "python app.py" and host='0.0.0.0' is set to ensure
    # that flask listens on port 5000 on all interfaces.

    # Run waitress WSGI server
    serve(TransLogger(app, setup_console_handler=True),
          host='0.0.0.0', port=5000, threads=10)
