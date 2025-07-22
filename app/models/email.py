# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

from datetime import datetime
from uuid import uuid4
from ..database import db

class EmailSubscriber(db.Model):
    """Model for email subscribers"""
    __tablename__ = 'email_subscribers'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    confirmed = db.Column(db.Boolean, default=False, nullable=False)
    confirmation_code = db.Column(db.String(36), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    
    def __init__(self, email):
        self.email = email
        self.confirmation_code = str(uuid4())
        self.confirmed = False
    
    def confirm(self):
        """Confirm the email subscription"""
        self.confirmed = True
        self.confirmed_at = datetime.utcnow()
    
    def __repr__(self):
        return f"<EmailSubscriber(email='{self.email}', confirmed={self.confirmed})>"

class EmailRateLimit(db.Model):
    """Model for tracking email rate limits"""
    __tablename__ = 'email_rate_limits'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def __init__(self, email):
        self.email = email
        self.timestamp = datetime.utcnow()
    
    def __repr__(self):
        return f"<EmailRateLimit(email='{self.email}', timestamp='{self.timestamp}')>"
