# catalog-searcher

Python 3 Flask application to search the catalog.

## Requires

* Python 3.10

## Running

```
$ catalog-searcher --help
Usage: catalog-searcher [OPTIONS]

  Run the catalog searcher web app using the waitress WSGI server

Options:
  -l, --listen [HOST]:PORT  Port (and optional host) to listen on. Defaults to
                            "0.0.0.0:5000".
  -t, --threads INTEGER     Maximum number of threads to use. Defaults to 10.
  -V, --version             Show the version and exit.
  --help                    Show this message and exit.
```

## Development Setup

See [docs/DevelopmentSetup.md](docs/DevelopmentSetup.md).

## API

* Root
  * Path: `/`
  * Methods: `GET`
  * Response (to all requests):
    * Status: `200 OK`
    * Content-Type: `application/json`
    * Body: `{status: ok}`
* Ping
  * Path: `/ping`
  * Methods: `GET`
  * Response (to all requests):
    * Status: `200 OK`
    * Content-Type: `application/json`
    * Body: `{status: ok}`
* Search
  * Path: `/search`
  * Methods: `GET`
  * Parameters:
    * `q` (**Required**): text of the query
    * `endpoint` (*Optional*): selects the type of search: `books-and-more` or
      `articles`; defaults to `books-and-more`
    * `page` (*Optional*): page of results to display; defaults to `0`
    * `per_page` (*Optional*): number of results to display on each page;
      defaults to `3`
    * `backend` (*Optional*): catalog backend implementation to use: `alma`,
      `primo`, or `worldcat`; defaults to `primo`
  * Responses:
    * Success:
      * Status: `200 OK`
      * Content-Type: `application/json`
      * JSON Schema: [api-response-schema.json](docs/api-response-schema.json)
    * Error: Missing or invalid request parameters
      * Status: `400 Bad Request`
      * Content-Type: `application/json`
    * Error: Problem contacting the backend or executing the search
      * Status: `500 Internal Server Error`
      * Content-Type: `application/json`

### Example

```bash
curl 'http://localhost:5000/search?q=cheese+making&per_page=3&page=2'
```

```json
{
  "endpoint": "world_cat_discovery_api_article",
  "first_page": "http://localhost:5000/search?q=cheese+making&per_page=3&page=1",
  "last_page": "http://localhost:5000/search?q=cheese+making&per_page=3&page=62015",
  "next_page": "http://localhost:5000/search?q=cheese+making&per_page=3&page=3",
  "page": 2,
  "per_page": 3,
  "prev_page": "http://localhost:5000/search?q=cheese+making&per_page=3&page=1",
  "query": "cheese making",
  "results": [
    {
      "author": "Francis T. Bond",
      "date": "1905",
      "format": "article",
      "link": "https://www.jstor.org/stable/20286827",
      "title": "Cheese-Making"
    },
    {
      "author": "Muiris O’Sullivan",
      "date": "2018",
      "format": "article",
      "link": "https://www.jstor.org/stable/26565827",
      "title": "CHEESE-MAKING"
    },
    {
      "author": "null",
      "date": "2019",
      "format": "article",
      "link": "https://umaryland.on.worldcat.org/oclc/8100216678",
      "title": "Cheese Making"
    }
  ],
  "total": 186043
}
```

## License

See the [LICENSE](LICENSE.txt) file for license rights and limitations.


[Flask's debug mode]: https://flask.palletsprojects.com/en/2.2.x/cli/?highlight=debug%20mode
