# Dockerfile for the generating catalog-searcher application Docker image
#
# To build:
#
# docker build -t docker.lib.umd.edu/catalog-searcher:<VERSION> -f Dockerfile .
#
# where <VERSION> is the Docker image version to create.
FROM python:3.10.8-slim

LABEL MAINTAINER SSDR "lib-ssdr@umd.edu"

EXPOSE 5000

# We copy just the requirements.txt first to leverage Docker cache
COPY ./requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt && rm /tmp/requirements.txt

COPY . /tmp/catalog-searcher
RUN pip install /tmp/catalog-searcher && rm -rf /tmp/catalog-searcher

CMD ["catalog-searcher"]
