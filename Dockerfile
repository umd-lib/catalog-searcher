# Dockerfile for the generating worldcat-searcher application Docker image
#
# To build:
#
# docker build -t docker.lib.umd.edu/worldcat-searcher:<VERSION> -f Dockerfile .
#
# where <VERSION> is the Docker image version to create.
FROM python:3.10.8-slim

LABEL MAINTAINER SSDR "lib-ssdr@umd.edu"

EXPOSE 5000

# We copy just the requirements.txt first to leverage Docker cache
COPY ./requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt && rm /tmp/requirements.txt

COPY . /tmp/worldcat-searcher
RUN pip install /tmp/worldcat-searcher && rm -rf /tmp/worldcat-searcher

CMD ["python", "-m", "worldcat_searcher.app"]
