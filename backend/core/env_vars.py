"""Environment variables - Direct access to secrets."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the backend directory (parent of core)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Django Settings
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-default-key-change-in-production")
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes", "on")
ALLOWED_HOSTS = [
    h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()
]

# Database Configuration
DB_NAME = os.getenv("DB_NAME", "jin_ai_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

# API Keys
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
DEEPGRAM_TTS_MODEL = os.getenv("DEEPGRAM_TTS_MODEL", "aura-2-odysseus-en")
DEEPGRAM_STT_MODEL = os.getenv("DEEPGRAM_STT_MODEL", "nova-3")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4")

# Celery Configuration
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

__all__ = [
    "SECRET_KEY",
    "DEBUG",
    "ALLOWED_HOSTS",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "DB_HOST",
    "DB_PORT",
    "DEEPGRAM_API_KEY",
    "DEEPGRAM_TTS_MODEL",
    "DEEPGRAM_STT_MODEL",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
]
