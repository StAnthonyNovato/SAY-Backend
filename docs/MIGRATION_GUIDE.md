# SQLAlchemy Migration Guide

This document explains the migration from JSON file storage to SQLAlchemy database storage.

## Overview

The backend has been migrated from storing data in JSON files to using SQLAlchemy with support for both SQLite (development) and MySQL (production).

## Database Configuration

The database is configured via environment variables in `.env`:

```bash
# Database URL - defaults to SQLite for development
DATABASE_URL=sqlite:///dev.db

# For production with MySQL:
# DATABASE_URL=mysql+pymysql://username:password@localhost/database_name

# Email rate limiting (emails per day)
EMAIL_RATE_LIMIT_PER_DAY=2
```

## Database Models

### EmailSubscriber
- `id` (Primary Key)
- `email` (Unique, Indexed)
- `confirmed` (Boolean)
- `confirmation_code` (Unique UUID, Indexed)
- `created_at` (Timestamp)
- `confirmed_at` (Timestamp, nullable)

### EmailRateLimit
- `id` (Primary Key)
- `email` (Indexed)
- `timestamp` (Timestamp)

## Migration Process

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Run Data Migration
The migration script will backup existing JSON files and migrate data:
```bash
python app/migrate_data.py
```

This will:
- Create backups: `email-subscribers.json.backup`, `email-rate-limit.json.backup`
- Migrate all subscriber data to the database
- Migrate rate limiting data to the database

### Step 3: Database Migrations with Alembic

Generate initial migration:
```bash
alembic revision --autogenerate -m "Initial migration"
```

Apply migrations:
```bash
alembic upgrade head
```

## Development vs Production

### SQLite (Development)
- Default configuration uses SQLite
- Database file: `dev.db`
- No additional setup required

### MySQL (Production)
- Set `DATABASE_URL` environment variable
- Example: `mysql+pymysql://user:password@localhost/say_backend`
- Ensure MySQL server is running and database exists

## API Changes

The API endpoints remain the same, but now use database storage:
- `POST /api/subscribe` - Subscribe to newsletter
- `GET /api/confirm?code=<uuid>` - Confirm subscription

## Backup Strategy

### JSON Backups
Original JSON files are backed up during migration with `.backup` extension.

### Database Backups
For production, implement regular database backups according to your MySQL backup strategy.

## Rollback Plan

If needed to rollback to JSON storage:
1. Restore from `.backup` files
2. Switch to the previous git commit
3. Restart the application

## Testing

Test the migration in a development environment first:
1. Copy production JSON files to dev environment
2. Run migration script
3. Test all API endpoints
4. Verify data integrity

## Monitoring

After migration, monitor:
- Database performance
- Email subscription functionality
- Rate limiting behavior
- Error logs for any migration issues
