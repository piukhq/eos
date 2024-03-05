#!/bin/sh

echo "Collecting statics"
python ./manage.py collectstatic --noinput

echo "Starting gunicorn"
exec "$@"
