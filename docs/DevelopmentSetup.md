# Development Setup

## Introduction

This page describes how to set up a development environment, and other
information useful for developers to be aware of.

## Prerequisites

The following instructions assume that "pyenv" and "pyenv-virtualenv" are
installed to enable the setup of an isolated Python environment.

See the following for setup instructions:

* https://github.com/pyenv/pyenv
* https://github.com/pyenv/pyenv-virtualenv

Once "pyenv" and "pyenv-virtualenv" have been installed, install Python 3.8.2:

```bash
> pyenv install 3.10.8
```

## Installation for development

1) Clone the "worldcat-searcher" Git repository:

```bash
> git clone https://github.com/umd-lib/worldcat-searcher.git
```

2) Switch to the "worldcat-searcher" directory:

```bash
> cd worldcat-searcher
```

3) Set up the virtual environment:

```bash
> pyenv virtualenv 3.10.8 worldcat-searcher
> pyenv shell worldcat-searcher
```

4) Run "pip install" to download dependencies:

```bash
> pip3 install -r requirements.txt
```

## Running the Webapp

Create a .env file (then manually update environment variables):

```bash
$ cp env-template .env
```

To start the app:

```bash
> python3 -m flask run
```

## Code Style

Application code style should generally conform to the guidelines in
[PEP 8](https://www.python.org/dev/peps/pep-0008/). The "pycodestyle" tool
to check compliance with the guidelines can be run using:

```bash
> pycodestyle .
```
