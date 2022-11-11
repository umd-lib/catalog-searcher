# worldcat-searcher

Python 3 Flask application to search the OCLC Discovery API.

## Requires

* Python 3.10.8

## Running the Webapp

```bash
# create a .env file (then manually update environment variables)
$ cp env-template .env
```

### Development Setup

See [docs/DevelopmentSetup.md](docs/DevelopmentSetup.md).

### Running in Docker

```bash
$ docker build -t docker.lib.umd.edu/worldcat-searcher .
$ docker run -it --rm -p 5000:5000 --env-file=.env --read-only docker.lib.umd.edu/worldcat-searcher
```

### Endpoints

This will start the webapp listening on the default port 5000 on localhost
(127.0.0.1), and running in [Flask's debug mode].

Root endpoint (just returns `{status: ok}` to all requests):
<http://localhost:5000/>

/ping endpoint (just returns `{status: ok}` to all requests):
<http://localhost:5000/ping>

/search endpoints:

Books and More:

```bash
http://localhost:5000/search?endpoint=books-and-more&q={query}&page={page number}&per_page={results per page}
```

Articles:

```bash
http://localhost:5000/search?endpoint=articles&q={query}&page={page number}&per_page={results per page}
```

Example:

```bash
curl 'http://localhost:5000/search?q=cheese+making&endpoint=books-and-more&per_page=3&page=2'
{
  "endpoint": "world_cat_discovery_api_article",
  "page": 2,
  "per_page": 3,
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

[Flask's debug mode]: https://flask.palletsprojects.com/en/2.2.x/cli/?highlight=debug%20mode

## License

See the [LICENSE](LICENSE.txt) file for license rights and limitations.
