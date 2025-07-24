# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Database Configuration
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///dev.db")
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Email Configuration
    GOOGLE_APP_PASSWORD = os.getenv("GOOGLE_APP_PASSWORD")
    EMAIL = os.getenv("EMAIL", "stanthonyyouth.noreply@gmail.com")
    
    # Debug mode
    DEBUG = os.getenv("FLASK_ENV") == "development"
    
    # Rate limiting
    EMAIL_RATE_LIMIT_PER_DAY = int(os.getenv("EMAIL_RATE_LIMIT_PER_DAY", "2"))
