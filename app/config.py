import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'ai-public-opinion-secret-key'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DATABASE_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'data.db')
