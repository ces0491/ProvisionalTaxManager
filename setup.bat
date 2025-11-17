@echo off
echo ================================
echo SA Tax App Setup
echo ================================
echo.

echo Creating virtual environment...
python -m venv venv
call venv\Scripts\activate

echo.
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Creating .env file...
if not exist .env (
    copy .env.example .env
    echo Please edit .env file and set your AUTH_PASSWORD
) else (
    echo .env file already exists
)

echo.
echo Creating uploads directory...
if not exist uploads mkdir uploads

echo.
echo Initializing database...
python -c "from app import app, db; from categorizer import init_categories_in_db; from models import Category; app.app_context().push(); db.create_all(); init_categories_in_db(db, Category); print('Database initialized!')"

echo.
echo ================================
echo Setup complete!
echo ================================
echo.
echo To start the app:
echo   1. Activate virtual environment: venv\Scripts\activate
echo   2. Edit .env and set AUTH_PASSWORD
echo   3. Run: python app.py
echo   4. Open browser to: http://localhost:5000
echo.
pause
