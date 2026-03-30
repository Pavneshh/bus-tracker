import os

class Config:
    """Application configuration"""
    
    # Database
    SQLALCHEMY_DATABASE_URI = 'sqlite:///database/bus_tracker.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # API Keys
    GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', 'your_api_key_here')
    
    # Flask
    DEBUG = True
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
