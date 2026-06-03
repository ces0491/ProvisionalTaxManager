import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Fix DATABASE_URL for SQLAlchemy 1.4+ (postgres:// -> postgresql://)
    basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    database_url = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'tax_data.db')
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = database_url

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    AUTH_PASSWORD = os.environ.get('AUTH_PASSWORD') or 'changeme'

    # Session cookie hardening. SECURE is off by default so local HTTP login
    # works; set SESSION_COOKIE_SECURE=true in production (Render serves HTTPS).
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'

    # Tax configuration
    TAX_REFERENCE = '0327851259'
    BUSINESS_NAME = 'Sheet Solved'
    INCOME_SOURCE = 'PRECISE DIGITAL'
