#!/usr/bin/env python3
# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

"""
Migration script to move data from JSON files to SQLAlchemy database
"""

import json
import sys
import os
from datetime import datetime

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from app.database import db
from app.models.email import EmailSubscriber, EmailRateLimit

def migrate_email_subscribers():
    """Migrate email subscribers from JSON to database"""
    print("Migrating email subscribers...")
    
    # Read JSON data
    try:
        with open('email-subscribers.json', 'r') as f:
            subscribers_data = json.load(f)
    except FileNotFoundError:
        print("email-subscribers.json not found, skipping subscriber migration")
        return
    
    migrated_count = 0
    for subscriber_data in subscribers_data:
        email = subscriber_data['email']
        confirmed = subscriber_data['confirmed']
        confirmation_code = subscriber_data['confirmation_code']
        
        # Check if already exists
        existing = EmailSubscriber.query.filter_by(email=email).first()
        if existing:
            print(f"Subscriber {email} already exists, skipping")
            continue
        
        # Create new subscriber
        subscriber = EmailSubscriber(email=email)
        subscriber.confirmed = confirmed
        subscriber.confirmation_code = confirmation_code
        
        if confirmed:
            subscriber.confirmed_at = datetime.utcnow()
        
        db.session.add(subscriber)
        migrated_count += 1
    
    db.session.commit()
    print(f"Migrated {migrated_count} email subscribers")

def migrate_rate_limits():
    """Migrate rate limits from JSON to database"""
    print("Migrating rate limits...")
    
    # Read JSON data
    try:
        with open('email-rate-limit.json', 'r') as f:
            rate_limit_data = json.load(f)
    except FileNotFoundError:
        print("email-rate-limit.json not found, skipping rate limit migration")
        return
    
    migrated_count = 0
    for email, timestamps in rate_limit_data.items():
        for timestamp_str in timestamps:
            # Parse timestamp
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
            except ValueError:
                print(f"Invalid timestamp format: {timestamp_str}, skipping")
                continue
            
            # Create rate limit record
            rate_limit = EmailRateLimit(email=email)
            rate_limit.timestamp = timestamp
            
            db.session.add(rate_limit)
            migrated_count += 1
    
    db.session.commit()
    print(f"Migrated {migrated_count} rate limit records")

def backup_json_files():
    """Create backup copies of JSON files"""
    import shutil
    
    json_files = ['email-subscribers.json', 'email-rate-limit.json']
    
    for json_file in json_files:
        if os.path.exists(json_file):
            backup_file = f"{json_file}.backup"
            shutil.copy2(json_file, backup_file)
            print(f"Backed up {json_file} to {backup_file}")

def main():
    """Run the migration"""
    print("Starting JSON to SQLAlchemy migration...")
    
    with app.app_context():
        # Create backup
        backup_json_files()
        
        # Create tables if they don't exist
        db.create_all()
        
        # Run migrations
        migrate_email_subscribers()
        migrate_rate_limits()
        
        print("Migration completed successfully!")
        
        # Show summary
        subscriber_count = EmailSubscriber.query.count()
        rate_limit_count = EmailRateLimit.query.count()
        confirmed_count = EmailSubscriber.query.filter_by(confirmed=True).count()
        
        print(f"\nDatabase Summary:")
        print(f"- Total subscribers: {subscriber_count}")
        print(f"- Confirmed subscribers: {confirmed_count}")
        print(f"- Rate limit records: {rate_limit_count}")

if __name__ == '__main__':
    main()
