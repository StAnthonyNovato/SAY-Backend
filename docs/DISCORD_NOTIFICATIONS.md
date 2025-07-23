# Discord Notification System

## Overview

The SAY Website Backend now includes a non-blocking Discord notification system for app diagnostics and monitoring. This system uses a separate worker thread to send notifications to Discord without blocking the main application flow, and implements proper Discord API rate limiting with automatic retry logic.

## Features

- **Non-blocking**: Uses a separate worker thread to send notifications
- **Queue-based**: All notifications are queued and processed asynchronously
- **Rate Limiting**: Full Discord API rate limit compliance with automatic retry
- **Multiple message types**: Supports plain text messages and rich embeds
- **Diagnostic helpers**: Pre-built methods for common diagnostic scenarios
- **Graceful shutdown**: Properly handles application shutdown
- **Error handling**: Robust error handling with exponential backoff
- **Health monitoring**: Built-in health check capabilities with rate limit status

## Rate Limiting Features

### Discord API Compliance
- **Per-route Rate Limits**: Tracks individual endpoint rate limits using bucket IDs
- **Global Rate Limits**: Handles Discord's global 50 requests/second limit
- **Automatic Retry**: Implements proper retry logic with Discord's `retry_after` values
- **Bucket Tracking**: Maintains separate rate limit tracking for different Discord API buckets
- **Proactive Limiting**: Checks rate limits before sending to prevent unnecessary 429 responses

### Rate Limit Headers Parsed
- `X-RateLimit-Limit`: Number of requests allowed
- `X-RateLimit-Remaining`: Remaining requests in current window
- `X-RateLimit-Reset`: Unix timestamp when rate limit resets
- `X-RateLimit-Reset-After`: Seconds until rate limit reset
- `X-RateLimit-Bucket`: Unique bucket identifier for shared limits
- `X-RateLimit-Global`: Indicates global rate limiting (on 429 responses)
- `Retry-After`: Time to wait before retrying (on 429 responses)

## Setup

### 1. Create a Discord Webhook

1. Go to your Discord server
2. Navigate to Server Settings → Integrations → Webhooks
3. Click "New Webhook"
4. Choose a channel and copy the webhook URL
5. Set the webhook URL as an environment variable:

```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"
```

### 2. Optional Configuration

You can also disable Discord notifications entirely:

```bash
export DISCORD_NOTIFICATIONS_ENABLED="false"
```

## Usage

### Basic Usage

```python
from app.discord import discord_notifier

# Send a plain text message
discord_notifier.send_plaintext("Service is starting up...")

# Send a rich embed
discord_notifier.send_embed(
    title="System Status",
    description="All systems operational",
    color=0x00ff00,  # Green
    fields=[
        {"name": "Service", "value": "SAY Backend", "inline": True},
        {"name": "Status", "value": "✅ Online", "inline": True}
    ]
)
```

### Diagnostic Messages

```python
# Info level diagnostic
discord_notifier.send_diagnostic(
    level="info",
    service="Email Service", 
    message="Service running normally",
    details={"Active Users": "150", "Queue Size": "0"}
)

# Warning level diagnostic  
discord_notifier.send_diagnostic(
    level="warning",
    service="Database",
    message="High response time detected",
    details={"Response Time": "250ms", "Threshold": "100ms"}
)

# Error level diagnostic
discord_notifier.send_diagnostic(
    level="error",
    service="File System",
    message="Failed to write to cache",
    details={"Error": "Permission denied", "Path": "/tmp/cache"}
)
```

### Startup and Error Notifications

```python
# Send startup notification
discord_notifier.send_startup_notification("SAY Website Backend", version="1.2.3")

# Send error notification with exception
try:
    # Some code that might fail
    pass
except Exception as e:
    discord_notifier.send_error_notification(
        service="User Registration",
        error=e,
        context="Processing new user signup"
    )
```

## Message Types

### Diagnostic Levels

- **info**: 🔵 Blue - General information
- **warning**: 🟡 Orange - Warnings that need attention
- **error**: 🔴 Red - Errors that occurred
- **critical**: 🚨 Dark Red - Critical issues requiring immediate attention

### Embed Fields

Rich embeds support:

- Title and description
- Color coding
- Multiple fields (inline or full-width)
- Footer with text and icon
- Author information
- Thumbnail and main images
- Timestamps

## Health Monitoring

Check the health of the notification system:

```python
# Check if the system is healthy
healthy = discord_notifier.is_healthy()

# Get current queue size
queue_size = discord_notifier.get_queue_size()

# Check if notifications are enabled
enabled = discord_notifier.enabled

# Get detailed rate limit information
rate_limit_info = discord_notifier.get_rate_limit_info()
print(f"Global rate limit active: {rate_limit_info['global_rate_limit']['active']}")
print(f"Buckets tracked: {len(rate_limit_info['buckets'])}")

# Reset rate limit tracking (for testing)
discord_notifier.reset_rate_limits()
```

### Rate Limit Information Structure

The `get_rate_limit_info()` method returns detailed information about current rate limits:

```json
{
  "global_rate_limit": {
    "active": false,
    "reset_time": 0.0,
    "wait_time": 0.0
  },
  "buckets": {
    "webhook_bucket_id": {
      "limit": 5,
      "remaining": 3,
      "reset_time": 1627849200.0,
      "reset_after": 60.0,
      "exhausted": false,
      "wait_time": 0.0,
      "last_updated": 1627849140.0
    }
  }
}
```

## Integration with Flask

The Discord notification system is automatically integrated with the Flask application:

- Sends startup notification when the app starts
- Automatically sends error notifications for 500 errors
- Provides a `/health` endpoint that includes Discord notification and rate limit status
- Gracefully shuts down when the application stops

### Health Endpoint Response

The `/health` endpoint now includes comprehensive rate limit information:

```json
{
  "status": "healthy",
  "timestamp": "2025-07-21T12:00:00.000Z",
  "services": {
    "discord_notifications": {
      "status": "healthy",
      "enabled": true,
      "queue_size": 0,
      "rate_limits": {
        "global_rate_limit": {
          "active": false,
          "reset_time": 0.0,
          "wait_time": 0.0
        },
        "buckets": {}
      }
    }
  }
}
```

## Testing

Run the example script to test your Discord integration:

```bash
python discord_example.py
```

This will send various types of test notifications to your Discord channel.

## Thread Safety

The Discord notification system is fully thread-safe:

- Uses a dedicated worker thread for sending notifications
- Thread-safe queue for message passing
- Proper synchronization mechanisms
- Safe shutdown procedures

## Error Handling

The notification system includes comprehensive error handling:

### Network Errors
- **Automatic Retry**: Network failures trigger exponential backoff retry (2s, 3s, 5s)
- **Timeout Handling**: 10-second timeout on webhook requests
- **Connection Recovery**: Automatically recovers from temporary network issues

### Rate Limit Handling
- **429 Response Parsing**: Correctly parses Discord's rate limit response format
- **Retry-After Compliance**: Waits exactly as long as Discord specifies
- **Bucket Tracking**: Maintains separate rate limit state for different API buckets
- **Global vs Per-Route**: Handles both global and per-route rate limits appropriately

### Error Recovery
- **Graceful Degradation**: Application continues if Discord is unavailable
- **Non-blocking**: Errors never block the main application thread
- **Comprehensive Logging**: All errors are logged with appropriate detail levels
- **Invalid Webhook Detection**: Stops retrying on permanent errors (404, 401, etc.)

### Error Scenarios Handled
- Invalid webhook URLs (404 errors)
- Network timeouts and connection failures
- Discord API temporary unavailability (5xx errors)
- Rate limiting (429 responses)
- Malformed request data (4xx errors)
- SSL/TLS certificate issues

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DISCORD_WEBHOOK_URL` | Discord webhook URL | None (required) |
| `DISCORD_NOTIFICATIONS_ENABLED` | Enable/disable notifications | `true` |
| `LOG_LEVEL` | Application log level | `INFO` |

## Performance Considerations

- Notifications are queued and processed asynchronously
- No impact on request response times
- Memory usage scales with queue size
- Worker thread uses minimal CPU when idle
- Automatic queue cleanup on shutdown

## Security Notes

- Keep your Discord webhook URL secure
- Don't commit webhook URLs to version control
- Use environment variables for configuration
- Consider rate limiting for high-volume applications
