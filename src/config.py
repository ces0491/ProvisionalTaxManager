import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Fix DATABASE_URL for SQLAlchemy 1.4+ (postgres:// -> postgresql://)
    database_url = os.environ.get('DATABASE_URL') or 'sqlite:///tax_data.db'
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = database_url

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    AUTH_PASSWORD = os.environ.get('AUTH_PASSWORD') or 'changeme'

    # Tax configuration
    TAX_REFERENCE = '0327851259'
    BUSINESS_NAME = 'Sheet Solved'
    INCOME_SOURCE = 'PRECISE DIGITAL'
