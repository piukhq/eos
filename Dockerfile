FROM ghcr.io/binkhq/python:3.11-poetry AS build

WORKDIR /src
ADD . .

RUN poetry build

# RUN poetry export -f requirements.txt -o requirements.txt

FROM ghcr.io/binkhq/python:3.11

WORKDIR /app
COPY --from=build /src/dist/*.whl .
COPY --from=build /src/manage.py .
RUN export wheel=$(find -type f -name "*.whl") && \
    pip install "$wheel" && rm $wheel

ENTRYPOINT [ "/app/entrypoint.sh" ]
CMD [ "gunicorn", "--workers=2", "--error-logfile=-", "--access-logfile=-", \
        "--bind=0.0.0.0:9000", "app.wsgi:application" ]
