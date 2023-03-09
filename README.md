# Legacy worldcat-searcher

Python 3 Flask application to search the deprecated beta OCLC Discovery API.

Find this API here: <https://beta.worldcat.org/discovery/bib/search>

## Requires

* Python 3.10.8

### Development Setup

See [docs/DevelopmentSetup.md](docs/DevelopmentSetup.md).

### Running in Docker

This should be tagged with the legacy-* prefix.

```bash
$ docker build -t docker.lib.umd.edu/legacy-worldcat-searcher .
$ docker run -it --rm -p 5000:5000 --env-file=.env --read-only docker.lib.umd.edu/legacy-worldcat-searcher
```

### Building for Kubernetes

When building for production, do use the legacy-* prefix to differenciate
from the non-beta version.

```bash
$ docker buildx build . --builder=kube -t docker.lib.umd.edu/legacy-worldcat-searcher:VERSION --push
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
  "endpoint":"books-and-more",
  "module_link":"https://umaryland.on.worldcat.org/search?queryString=cheese making",
  "page":0,
  "per_page":3,
  "query":"cheese making",
  "results":
  [
    {
      "author":"Gabriel Henry",
      "date":"1897",
      "description":null,
      "item_format":"e_book",
      "link":"https://umaryland.on.worldcat.org/oclc/890903730",
      "title":"Cheese making"
    },
    {
      "author":"John Wright Decker",
      "date":"1895","description":null,
      "item_format":"e_book",
      "link":"https://proxy-um.researchport.umd.edu/login?url=https://doi.org/10.5962/bhl.title.58759",
      "title":"Cheddar cheese making."
    },{
      "author":"Don Radke",
      "date":"1974",
      "description":"Rediscover the fun of cheese making at home.",
      "item_format":"book","link":"https://umaryland.on.worldcat.org/oclc/874088",
      "title":"Cheese making at home: the complete illustrated guide."
    }
  ],
  "total":14648,
  "version":"legacy"
  }
```

[Flask's debug mode]: https://flask.palletsprojects.com/en/2.2.x/cli/?highlight=debug%20mode

## License

See the [LICENSE](LICENSE.txt) file for license rights and limitations.
