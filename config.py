import os

# On Render, DATABASE_PATH and UPLOAD_FOLDER are set via env vars pointing to /data (persistent disk)
# Locally they fall back to the original sqlite:///placement.db and static/uploads

_db_path = os.environ.get('DATABASE_PATH')
_upload_folder = os.environ.get('UPLOAD_FOLDER', 'static/uploads')

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'supersecretkey123')
    if _db_path:
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{_db_path}'
    else:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///placement.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = _upload_folder
