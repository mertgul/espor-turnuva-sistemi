import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_secret_key'
    
    # Veritabanı bağlantı bilgileri
    DB_HOST = 'localhost'
    DB_NAME = 'esports_db'
    DB_USER = 'postgres'
    DB_PASSWORD = '1245'
    DB_PORT = '5432'
    
    # SQLAlchemy veritabanı URI
    SQLALCHEMY_DATABASE_URI = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
