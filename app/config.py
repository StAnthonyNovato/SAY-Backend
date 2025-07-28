# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Email Configuration
    GOOGLE_APP_PASSWORD = os.getenv("GOOGLE_APP_PASSWORD")
    EMAIL = os.getenv("EMAIL", "stanthonyyouth.noreply@gmail.com")
    
    # Debug mode
    DEBUG = os.getenv("FLASK_ENV") == "development"
    
    # Rate limiting
    EMAIL_RATE_LIMIT_PER_DAY = int(os.getenv("EMAIL_RATE_LIMIT_PER_DAY", "2"))

MYSQL_CONNECTION_INFO = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "user": os.getenv("MYSQL_USER", None),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "password": os.getenv("MYSQL_PASSWORD", None),
    "database": os.getenv("MYSQL_DATABASE", None)
}