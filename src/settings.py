"""
Django settings for StockHub inventory management system.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-xk9#mw2!5@qf3$n8^z6+y1cv0p4r7t"

DEBUG = True

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "src.inventory",
    "src.sync",
    "src.webhooks",
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

ROOT_URLCONF = "src.urls"

DATABASES = {
    "default": {
        "ENGINE": "djongo",
        "NAME": "stockhub",
        "CLIENT": {
            "host": "mongodb://localhost:27017",
        },
    }
}

# Celery Configuration
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"

# Marketplace API Credentials
AMAZON_API_KEY = "AKIAIOSFODNN7EXAMPLE"
AMAZON_API_SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
AMAZON_API_URL = "https://sellingpartnerapi.amazon.com"

CDISCOUNT_API_KEY = "cd_live_a1b2c3d4e5f6"
CDISCOUNT_API_SECRET = "cd_secret_x9y8z7w6v5u4"
CDISCOUNT_API_URL = "https://api.cdiscount.com"

# Webhook secrets for signature verification
WEBHOOK_SECRETS = {
    "amazon": "whsec_amazon_1234567890abcdef",
    "cdiscount": "whsec_cdiscount_fedcba0987654321",
}

# Logging Configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

# REST Framework settings
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
