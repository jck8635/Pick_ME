import os
from dotenv import load_dotenv

load_dotenv()


def _database_url():
    """Return the configured URL, selecting psycopg 3 for PostgreSQL."""
    url = os.getenv('DATABASE_URL', 'sqlite:///pickme.db').strip()
    if url.startswith('postgres://'):
        return url.replace('postgres://', 'postgresql+psycopg://', 1)
    if url.startswith('postgresql://'):
        return url.replace('postgresql://', 'postgresql+psycopg://', 1)
    return url


DATABASE_URL = _database_url()
AUTO_CREATE_DB = os.getenv(
    'AUTO_CREATE_DB',
    'true' if DATABASE_URL.startswith('sqlite:') else 'false',
).strip().lower() in {'1', 'true', 'yes', 'on'}


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-only-change-me')
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}
    AUTO_CREATE_DB = AUTO_CREATE_DB
