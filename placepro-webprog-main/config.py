import os
 
class Config:
    SECRET_KEY = 'supersecretkey123'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///placement.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'static/uploads'
