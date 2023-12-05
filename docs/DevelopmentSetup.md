# Development Setup

## Introduction

This page describes how to set up a development environment, and other
information useful for developers to be aware of.

## Prerequisites

* Python 3.10

### Installing Python with pyenv

The following instructions assume that "pyenv" is installed to enable the
setup of an isolated Python environment.

See the following for setup instructions:

* https://github.com/pyenv/pyenv

Once "pyenv" has been installed, install Python 3.10:

```bash
pyenv install 3.10
```

## Installation for development

1. Clone the "catalog-searcher" Git repository:

    ```bash
    git clone https://github.com/umd-lib/catalog-searcher.git
    ```

2. Switch to the "catalog-searcher" directory:

    ```bash
    cd catalog-searcher
    ```

3. Set up and activate the virtual environment:

    ```bash
    python -m venv .venv --prompt 'catalog-searcher-py3.10'
    source .venv/bin/activate
    ```

4. Run `pip install` to download dependencies, including those required
   to run the test suite:

    ```bash
    pip install -e '.[test]'
    ```

5. Verify the install by running the tests with [pytest]:

    ```bash
    pytest
    ```

## Running the Webapp

Create a `.env` file, then manually update environment variables:

```bash
cp env-template .env
```

To start the app:

```bash
python -m flask run
```

The app will be available at <http://localhost:5000>

## Running in Docker

```bash
docker build -t docker.lib.umd.edu/catalog-searcher .
docker run -it --rm -p 5000:5000 --env-file=.env --read-only docker.lib.umd.edu/catalog-searcher
```

### Building for Kubernetes

```bash
docker buildx build . --builder=kube -t docker.lib.umd.edu/catalog-searcher:VERSION --push
```

## Code Style

Application code style should generally conform to the guidelines in [PEP 8].

This repository is configured to use the [ruff] linter to check code style.
The enabled rule sets are the pycodestyle errors (`E`) and warnings (`W`).

```bash
ruff check
```

[PEP 8]: https://www.python.org/dev/peps/pep-0008/
[pytest]: https://pytest.org/
[ruff]: https://docs.astral.sh/ruff/
