import os

# Vercel sets VERCEL=1 automatically; Render sets DATABASE_PATH
_is_vercel    = os.environ.get('VERCEL')
_db_path      = os.environ.get('DATABASE_PATH')
_upload_folder = os.environ.get('UPLOAD_FOLDER', 'static/uploads')

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'supersecretkey123')

    if _is_vercel:
        # Vercel: use /tmp (ephemeral but writable)
        SQLALCHEMY_DATABASE_URI = 'sqlite:////tmp/placement.db'
        UPLOAD_FOLDER = '/tmp/uploads'
    elif _db_path:
        # Render: persistent disk path
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{_db_path}'
        UPLOAD_FOLDER = _upload_folder
    else:
        # Local dev
        SQLALCHEMY_DATABASE_URI = 'sqlite:///placement.db'
        UPLOAD_FOLDER = _upload_folder

    SQLALCHEMY_TRACK_MODIFICATIONS = False
