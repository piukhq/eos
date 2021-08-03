FROM ghcr.io/binkhq/python:3.8

WORKDIR /app
ADD . .

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    pip install --no-cache-dir pipenv==2018.11.26 gunicorn && \
    pipenv install --system --deploy --ignore-pipfile && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists


ENTRYPOINT ["/app/entrypoint.sh"]
CMD [ "gunicorn", "--workers=2", "--threads=2", "--error-logfile=-", \
    "--access-logfile=-", "--bind=0.0.0.0:9000", "app.wsgi:application" ]
