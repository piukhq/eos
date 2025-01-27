"""
Django settings for eos project.

Generated by 'django-admin startproject' using Django 3.1.6.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.1/ref/settings/
"""
import logging
import os
import sys
import typing as t
from pathlib import Path

import dj_database_url
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

logger = logging.getLogger(__name__)

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.1/howto/deployment/checklist/


class ConfigVarRequiredError(Exception):
    pass


def getenv(key: str, default: t.Union[str, None] = None, conv: t.Callable = str, required: bool = True) -> t.Any:
    """If `default` is None, then the var is non-optional."""
    var = os.getenv(key, default)
    if var is None and required is True:
        raise ConfigVarRequiredError(f"Configuration variable '{key}' is required but was not provided.")
    elif var is not None:
        return conv(var)
    else:
        return None


def delimited_list_conv(s: str, *, sep: str = ",") -> t.List[str]:
    return [_.strip() for _ in s.split(sep) if _]


def boolconv(s: str) -> bool:
    return s.lower() in ["true", "t", "yes"]


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "=@%7ks9yhdz^n-qa5-w%8nl0)p6064=yc6)dpfoljxu9gqd5t%"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = getenv("DEBUG", "False", conv=boolconv)

ALLOWED_HOSTS = ["*"]

CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1",
    "https://*.bink.com",
    "https://*.bink.sh",
]

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Application definition

INSTALLED_APPS = [
    "eos.apps.EosAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "mids",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "eos.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "eos.wsgi.application"


# Database
# https://docs.djangoproject.com/en/3.1/ref/settings/#databases

PG_OPTIONS = {"application_name": "eos"}

if os.getenv("EOS_DATABASE_URI"):
    DATABASES = {
        "default": dj_database_url.config(
            env="EOS_DATABASE_URI",
            conn_max_age=600,
            engine="django.db.backends.postgresql",
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": getenv("DATABASE_NAME", default="eos"),
            "USER": getenv("DATABASE_USER"),
            "PASSWORD": getenv("DATABASE_PASSWORD", required=False),
            "HOST": getenv("DATABASE_HOST", default="127.0.0.1"),
            "PORT": getenv("DATABASE_PORT", default="5432"),
            "OPTIONS": PG_OPTIONS,
        },
    }

# Password validation
# https://docs.djangoproject.com/en/3.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.1/topics/i18n/

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/

STATIC_URL = "/eos/static/"
STATIC_ROOT = "/tmp/static/"

TESTING = len(sys.argv) > 1 and sys.argv[1] == "test"

LOG_LEVEL = getenv("LOG_LEVEL", default="DEBUG")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "%(asctime)s :: %(name)s :: %(levelname)s :: %(message)s"},
    },
    "handlers": {
        "console": {
            "level": LOG_LEVEL,
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "null": {
            "class": "logging.NullHandler",
        },
    },
    "filters": {
        "require_debug_true": {"()": "django.utils.log.RequireDebugTrue"},
    },
    "loggers": {
        "": {
            "level": LOG_LEVEL,
            "handlers": ["console"],
        },
        "django.db.backends": {
            "filters": ["require_debug_true"],
            "level": logging.WARNING,
            "handlers": ["console"],
            "propagate": False,
        },
        **{
            field: {
                "level": LOG_LEVEL,
                "handlers": ["console"] if not TESTING else ["null"],
                "propagate": False,
            }
            for field in ("app", "mids", "asyncio")
        },
    },
}

SITE_HEADER = "AMEX MID Onboarding"

TEST_RUNNER_SET = getenv("TEST_RUNNER", conv=boolconv, required=False)
KEY_VAULT = getenv("KEY_VAULT", required=True)
AMEX_API_HOST = getenv("AMEX_API_HOST", required=False)
AMEX_CLIENT_ID = getenv("AMEX_CLIENT_ID", required=False)
AMEX_CLIENT_SECRET = getenv("AMEX_CLIENT_SECRET", required=False)


REDIS_URL = getenv("REDIS_URL")

SENTRY_DSN = getenv("SENTRY_DSN", required=False)
SENTRY_ENV = getenv("SENTRY_ENV", default="unset").lower()

if SENTRY_DSN is not None:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=SENTRY_ENV,
        integrations=[DjangoIntegration()],
    )

# Custom authentication


# AzureAD SSO

SSO_ENABLED = getenv("SSO_ENABLED", default="true", conv=boolconv)

OAUTH_TENANT_ID = getenv("OAUTH_TENANT_ID", required=SSO_ENABLED)
OAUTH_CLIENT_ID = getenv("OAUTH_CLIENT_ID", required=SSO_ENABLED)
OAUTH_CLIENT_SECRET = getenv("OAUTH_CLIENT_SECRET", required=SSO_ENABLED)
OAUTH_REDIRECT_URI = getenv(
    "OAUTH_REDIRECT_URI",
    required=SSO_ENABLED,
    default="http://localhost:9000/eos/admin/oidc/callback/",
)

# if SSO is disabled, we use Django's default auth backend
if SSO_ENABLED:
    AUTHENTICATION_BACKENDS = ["eos.auth.AutoUserCreationBackend"]
