# Eos

Sibling of Selene. Manager of Amex MID on/off-boarding.

Accepts "batch" CSV files in the following format allowing actions to be performed on the Amex MID on/off-boarding API:

```
mid,start_date,end_date,merchant_slug,provider_slug,action
4548436161,2021-01-01,2999-12-31,bink_test_merchant,amex,a
5934398301,2021-01-01,2999-12-31,bink_test_merchant,amex,a
3945029385,2021-01-01,2999-12-31,bink_test_merchant,amex,d
```

Processing of individual items corresponding to individual calls to the onboarding API are handled by an RQ worker.

## Prerequisites

- [pipenv](https://docs.pipenv.org)

## Project design overview

This is a vanilla Django project leaning heavily on the `django.contrib.admin` app. It makes use of an RQ (Redis) queue to process API call tasks to the Amex API.

## Project Setup

Pipenv is used for managing project dependencies and execution.

### Virtual Environment

To create a virtualenv and install required software packages:

```bash
pipenv install --dev
```

Project configuration is done through environment variables. A convenient way to set these is in a `.env` file in the project root. This file will be sourced by Pipenv when `pipenv run` and `pipenv shell` are used.

To make a `.env` file from the example below:

```bash
DEBUG=True
DATABASE_HOST=localhost
DATABASE_USER=<username>
DATABASE_PASSWORD=<password> (if required)
KEY_VAULT=https://bink-uksouth-dev-com.vault.azure.net/
AMEX_API_HOST=https://api.dev2s.americanexpress.com
AMEX_CLIENT_ID=<client_id - optional if in the vault>
AMEX_CLIENT_SECRET=<client_secret - optional if in the vault>
REDIS_HOST=localhost
REDIS_DB=0
```

Other Django settings may be overridable in the .env file. See the `eos.settings` module.

### Database

The default database is called eos. Be sure to create a new postgres database and run the migrations prior to running the development server.

```
postgres=# CREATE DATABASE eos;
```

```bash
cd eos
pipenv run python manage.py migrate
```

### Development Server

The Django development server is used for running the project locally. This should be replaced with a WSGI-compatible server for deployment to a live environment.

To run the django development server:

```bash
pipenv run python manage.py runserver
```


### Unit Tests

To execute a full test run:

```bash
cd eos
pipenv run python manage.py test
```

## Deployment

There is a Dockerfile provided in the project root. Build an image from this to get a deployment-ready version of the project.