FROM python:3

LABEL MAINTAINER SSDR "lib-ssdr@umd.edu"

EXPOSE 5000

# We copy just the requirements.txt first to leverage Docker cache
COPY ./requirements.txt /app/requirements.txt

WORKDIR /app

RUN pip install -r requirements.txt

COPY ./src/app.py /app/app.py

ENTRYPOINT [ "python" ]

CMD [ "app.py" ]
