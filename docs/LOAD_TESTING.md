# Load Testing Guide

This guide explains how to perform load testing on the SAY Website Backend using Locust.

## Installation

1. Install load testing dependencies:
```bash
pip install -r requirements-loadtest.txt
```

## Quick Start

### 1. Basic Load Test (Web UI)
```bash
# Start the backend server first
python main.py

# In another terminal, start Locust
locust -f locustfile.py --host http://localhost:8000
```

Then open http://localhost:8089 in your browser to use the web interface.

### 2. Command Line Testing
```bash
# Basic load test with 20 users, spawning 2 per second
locust -f locustfile.py --users 20 --spawn-rate 2 --host http://localhost:8000 --run-time 2m

# Rate limit testing
locust -f locustfile.py --users 10 --spawn-rate 5 --host http://localhost:8000 HighVolumeSubscriptionUser --run-time 1m

# Stress testing
locust -f locustfile.py --users 50 --spawn-rate 10 --host http://localhost:8000 StressTestUser --run-time 30s
```

## Load Testing Mode Features

### LOAD_TESTING=1 Environment Variable

When `LOAD_TESTING=1` is set, the backend will:

1. **Return confirmation codes in API responses** for successful subscriptions
2. **Enable full end-to-end testing** of the subscription → confirmation flow
3. **Allow Locust to test realistic user journeys**

**Example API Response with LOAD_TESTING=1:**
```json
{
  "success": true,
  "message": "Subscription successful! We've sent you a confirmation email.",
  "email": "user@example.com",
  "action": "new_subscription",
  "confirmation_code": "123e4567-e89b-12d3-a456-426614174000"
}
```

**Without LOAD_TESTING (normal operation):**
```json
{
  "success": true,
  "message": "Subscription successful! We've sent you a confirmation email.",
  "email": "user@example.com",
  "action": "new_subscription"
}
```

### Security Notice

⚠️ **NEVER set LOAD_TESTING=1 in production!** This would expose confirmation codes in API responses, which is a security risk.

## User Classes

### EmailSubscriptionUser (Default)
- **90% confirmation rate** - realistic user behavior
- Mixed JSON and form submissions
- **Prevents duplicate subscriptions** - users don't re-subscribe
- **Minimal invalid requests** - only 10% chance of bad confirmation attempts
- Includes healthcheck requests

### RealisticUserJourney
- **Complete linear user flow**: subscribe → wait → confirm
- **90% completion rate** with 10% abandonment
- Realistic thinking time between actions
- Starts new journey after completion

### HighVolumeSubscriptionUser
- Tests rate limiting functionality
- Uses same email to trigger limits quickly
- Fast request intervals (0.1-0.5s)

### AdminUser
- Tests debug/admin endpoints
- Slower request patterns (2-10s intervals)

### StressTestUser
- **High-intensity with realistic confirmations**
- **85% confirmation rate** under stress
- Generates unique emails per request
- **Maintains confirmation queue** for realistic flow

## Environment Setup for Testing

### Disable Email Sending
```bash
export NO_EMAIL=1
```

### Enable Load Testing Mode (Returns Confirmation Codes)
```bash
export LOAD_TESTING=1
```

### Adjust Rate Limits for Testing
```bash
export RATE_LIMIT_EMAILS_PER_HOUR=5
```

### Full Load Testing Setup
```bash
export NO_EMAIL=1 LOAD_TESTING=1 RATE_LIMIT_EMAILS_PER_HOUR=10
python main.py
# In another terminal:
locust -f locustfile.py --host http://localhost:8000
```

### Test Database Setup
Make sure you're using a test database, not production!

## Production Testing

⚠️ **IMPORTANT**: Never run load tests against production without proper planning!

1. **Use staging environment first**
2. **Start with low user counts** (5-10 users)
3. **Gradually increase load**
4. **Monitor all systems**:
   - Database connections
   - Discord webhook rate limits
   - Email service quotas
   - Server resources

### Production Testing Command
```bash
locust -f locustfile.py --host https://stanthonyyouth.alphagame.dev --users 5 --spawn-rate 1 --run-time 30s
```

## Monitoring During Tests

Watch these metrics:
- Response times
- Error rates
- Database connection pool usage
- Discord notifications being sent
- Server CPU/Memory usage

## Interpreting Results

### Good Performance Indicators
- Response times under 500ms for most requests
- Error rate under 1%
- No database connection errors
- Rate limiting working correctly (429 responses)

### Warning Signs
- Response times over 2 seconds
- High error rates (>5%)
- Database connection timeouts
- Discord webhook failures

## Troubleshooting

### Common Issues

1. **"Database connection error"**
   - Check database connection pool size
   - Ensure test database is properly configured

2. **"Discord webhook errors"**
   - Discord has rate limits (5 requests per 5 seconds)
   - Consider reducing notification frequency for load tests

3. **"SMTP errors"**
   - Set `NO_EMAIL=1` to disable email sending during tests
   - Gmail has sending limits that can be hit quickly

4. **High response times**
   - Check server resources (CPU, memory)
   - Monitor database query performance
   - Consider connection pooling optimization

## Example Load Test Session

```bash
# 1. Start with light load
locust -f locustfile.py --users 5 --spawn-rate 1 --host http://localhost:8000 --run-time 1m

# 2. Test rate limiting
locust -f locustfile.py --users 3 --spawn-rate 1 --host http://localhost:8000 HighVolumeSubscriptionUser --run-time 30s

# 3. Stress test (if previous tests pass)
locust -f locustfile.py --users 20 --spawn-rate 5 --host http://localhost:8000 --run-time 2m

# 4. Monitor results in web UI at http://localhost:8089
```

Happy load testing! 🚀
