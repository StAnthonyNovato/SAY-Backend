# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

from flask_sqlalchemy import SQLAlchemy
from contextlib import contextmanager
from functools import wraps

# Initialize SQLAlchemy
db = SQLAlchemy()

@contextmanager
def auto_commit():
    """Context manager for auto-committing database operations"""
    try:
        yield db.session
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise e

def auto_commit_decorator(func):
    """Decorator to auto-commit database operations"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            db.session.commit()
            return result
        except Exception as e:
            db.session.rollback()
            raise e
    return wrapper

def init_db(app):
    """Initialize database with Flask app"""
    db.init_app(app)
    
    with app.app_context():
        # Import models here to ensure they're registered
        from .models.email import EmailSubscriber, EmailRateLimit
        
        # Create all tables
        db.create_all()
