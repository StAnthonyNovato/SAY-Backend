# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

import threading
import queue
import logging
import os
import time
import json
import requests
from datetime import datetime
from typing import Optional, Dict, Any, List
from dhooks import Webhook, Embed
from datetime import timezone

# Configure logging
logger = logging.getLogger(__name__)

class RateLimitBucket:
    """Tracks rate limit information for a specific Discord API bucket."""
    
    def __init__(self, bucket_id: str):
        self.bucket_id = bucket_id
        self.limit = None
        self.remaining = None
        self.reset_time = None
        self.reset_after = None
        self.last_updated = None
        self._lock = threading.Lock()
    
    def update_from_headers(self, headers: Dict[str, str]):
        """Update bucket info from Discord API response headers."""
        with self._lock:
            try:
                self.limit = int(headers.get('X-RateLimit-Limit', 0))
                self.remaining = int(headers.get('X-RateLimit-Remaining', 0))
                
                reset_timestamp = headers.get('X-RateLimit-Reset')
                if reset_timestamp:
                    self.reset_time = float(reset_timestamp)
                
                reset_after = headers.get('X-RateLimit-Reset-After')
                if reset_after:
                    self.reset_after = float(reset_after)
                
                self.last_updated = time.time()
                
                logger.debug(f"Rate limit bucket {self.bucket_id}: {self.remaining}/{self.limit} remaining, resets in {self.reset_after}s")
                
            except (ValueError, TypeError) as e:
                logger.warning(f"Error parsing rate limit headers: {e}")
    
    def should_wait(self) -> float:
        """Check if we should wait and return wait time in seconds."""
        with self._lock:
            if self.remaining is None or self.remaining > 0:
                return 0.0
            
            if self.reset_after is not None:
                # Account for time already passed since last update
                elapsed = time.time() - (self.last_updated or 0)
                wait_time = max(0, self.reset_after - elapsed)
                return wait_time
            
            return 0.0
    
    def is_exhausted(self) -> bool:
        """Check if this bucket is currently exhausted."""
        with self._lock:
            return self.remaining is not None and self.remaining <= 0

class DiscordRateLimiter:
    """Manages Discord API rate limiting across all buckets."""
    
    def __init__(self):
        self.buckets: Dict[str, RateLimitBucket] = {}
        self.global_reset_time = 0.0
        self._lock = threading.Lock()
    
    def get_bucket(self, bucket_id: str) -> RateLimitBucket:
        """Get or create a rate limit bucket."""
        with self._lock:
            if bucket_id not in self.buckets:
                self.buckets[bucket_id] = RateLimitBucket(bucket_id)
            return self.buckets[bucket_id]
    
    def handle_rate_limit_response(self, response_data: Dict[str, Any], headers: Dict[str, str]) -> float:
        """Handle a 429 rate limit response and return wait time."""
        retry_after = response_data.get('retry_after', 0.0)
        is_global = response_data.get('global', False)
        
        if is_global:
            logger.warning(f"Global rate limit encountered, waiting {retry_after}s")
            with self._lock:
                self.global_reset_time = time.time() + retry_after
        else:
            logger.warning(f"Per-route rate limit encountered, waiting {retry_after}s")
        
        return retry_after
    
    def should_wait_global(self) -> float:
        """Check if we should wait for global rate limit."""
        with self._lock:
            if time.time() < self.global_reset_time:
                return self.global_reset_time - time.time()
            return 0.0

class DiscordNotificationManager:
    """
    Non-blocking Discord notification manager for app diagnostics.
    Uses a separate worker thread to send notifications without blocking the main application.
    Implements proper Discord API rate limiting and retry logic.
    """
    
    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize the Discord notification manager.
        
        Args:
            webhook_url: Discord webhook URL. If not provided, will try to get from environment.
        """
        logger.info("Initializing Discord notification manager")
        self.webhook_url = webhook_url or os.getenv('DISCORD_WEBHOOK_URL')
        if not self.webhook_url:
            logger.warning("No Discord webhook URL provided. Notifications will be disabled.")
            self.enabled = False
        else:
            self.enabled = True
            
        # Rate limiting
        self.rate_limiter = DiscordRateLimiter()
        
        # Create a queue for notifications
        self.notification_queue = queue.Queue()
        
        # Worker thread flag
        self._worker_thread = None
        self._stop_worker = threading.Event()
        self._worker_lock = threading.Lock()
        
        # Start the worker thread
        self._start_worker()
        
    def _start_worker(self):
        """Start the worker thread if not already running."""
        logger.debug("Attempting to start Discord notification worker thread")
        with self._worker_lock:
            if self._worker_thread is None or not self._worker_thread.is_alive():
                self._stop_worker.clear()
                self._worker_thread = threading.Thread(
                    target=self._worker_loop, 
                    daemon=True,
                    name="DiscordNotificationWorker"
                )
                self._worker_thread.start()
                logger.debug("Just started Discord notification worker thread - it should be running now")    
    
    def _worker_loop(self):
        """Main worker loop that processes notification queue."""
        logger.info("Discord notification worker started")
        
        while not self._stop_worker.is_set():
            try:
                # Wait for a notification with timeout
                try:
                    notification_data: Dict[str, Any] = self.notification_queue.get(timeout=1.0)
                    logger.debug(f"Picked up notification from queue - {notification_data}")
                except queue.Empty:
                    continue
                
                # Process the notification with rate limiting
                success = self._send_notification_with_retry(**notification_data)

                if not success:
                    logger.error("Failed to send notification after all retries")
                    # dump data
                    logger.error(f"Notification data: {notification_data}")
                self.notification_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error in Discord notification worker: {e}", exc_info=True)
                
        logger.info("Discord notification worker stopped")
    
    def _send_notification_with_retry(self, content: Optional[str] = None, embed_data: Optional[Dict[str, Any]] = None, 
                                    username: Optional[str] = None, avatar_url: Optional[str] = None,
                                    max_retries: int = 3) -> bool:
        """
        Send notification with rate limiting and retry logic.
        Returns True if successful, False if all retries failed.
        """
        if not self.enabled or not self.webhook_url:
            logger.debug("Discord notifications disabled, skipping")
            return False
        
        for attempt in range(max_retries + 1):
            try:
                # Check global rate limit
                global_wait = self.rate_limiter.should_wait_global()
                if global_wait > 0:
                    logger.info(f"Waiting {global_wait:.2f}s for global rate limit")
                    time.sleep(global_wait)
                
                # Check if we should wait for any bucket rate limits
                # For webhooks, we use a default bucket since we don't know the exact bucket beforehand
                default_bucket = self.rate_limiter.get_bucket('webhook_default')
                bucket_wait = default_bucket.should_wait()
                if bucket_wait > 0:
                    logger.info(f"Waiting {bucket_wait:.2f}s for webhook rate limit")
                    time.sleep(bucket_wait)
                
                # Send the notification
                success = self._send_notification_raw(content, embed_data, username, avatar_url)
                if success:
                    return True
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Network error sending Discord notification (attempt {attempt + 1}): {e}")
                
                # Exponential backoff for network errors
                if attempt < max_retries:
                    backoff_time = (2 ** attempt) + 1  # 2, 3, 5 seconds
                    logger.info(f"Retrying in {backoff_time}s...")
                    time.sleep(backoff_time)
            
            except Exception as e:
                logger.error(f"Unexpected error sending Discord notification: {e}")
                break  # Don't retry on unexpected errors
        
        return False
    
    def _send_notification_raw(self, content: Optional[str] = None, embed_data: Optional[Dict[str, Any]] = None, 
                             username: Optional[str] = None, avatar_url: Optional[str] = None) -> bool:
        """
        Actually send the notification to Discord using raw HTTP requests for better rate limit control.
        Returns True if successful, False if rate limited and should retry.
        """
        logger.debug("Not sending Discord notification - checking if enabled and webhook URL is set")
        if not self.webhook_url:
            logger.error("No webhook URL available")
            return True  # Don't retry
            
        try:
            # Build the webhook payload
            payload = {}
            if content:
                payload['content'] = content
            if username:
                payload['username'] = username
            if avatar_url:
                payload['avatar_url'] = avatar_url
            
            # Create embed if embed_data is provided
            if embed_data:
                embed_dict = {
                    'title': embed_data.get('title'),
                    'description': embed_data.get('description'),
                    'color': embed_data.get('color', 0x00ff00),
                }
                
                # Add timestamp if requested
                if embed_data.get('timestamp', False):
                    embed_dict['timestamp'] = datetime.now().isoformat()
                
                # Add fields
                if 'fields' in embed_data and embed_data['fields']:
                    embed_dict['fields'] = embed_data['fields']
                
                # Add footer
                if 'footer' in embed_data:
                    embed_dict['footer'] = embed_data['footer']
                
                # Add author
                if 'author' in embed_data:
                    embed_dict['author'] = embed_data['author']
                
                # Add thumbnail
                if 'thumbnail' in embed_data:
                    embed_dict['thumbnail'] = {'url': embed_data['thumbnail']}
                
                # Add image
                if 'image' in embed_data:
                    embed_dict['image'] = {'url': embed_data['image']}
                
                # Clean up None values
                embed_dict = {k: v for k, v in embed_dict.items() if v is not None}
                payload['embeds'] = [embed_dict]
            
            # Make the HTTP request
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                try:
                    rate_limit_data = response.json()
                    retry_after = self.rate_limiter.handle_rate_limit_response(
                        rate_limit_data, 
                        dict(response.headers)
                    )
                    
                    logger.warning(f"Rate limited, waiting {retry_after:.2f}s before retry")
                    time.sleep(retry_after)
                    return False  # Indicate retry needed
                    
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Error parsing rate limit response: {e}")
                    time.sleep(1)  # Default wait
                    return False
            
            # Handle other HTTP errors
            elif not response.ok:
                logger.error(f"Discord webhook error {response.status_code}: {response.text}")
                
                # Don't retry on client errors (4xx except 429)
                if 400 <= response.status_code < 500:
                    return True  # Consider it "sent" to avoid infinite retries
                
                return False  # Retry on server errors (5xx)
            
            # Success case
            else:
                # Update rate limit info from headers
                bucket_id = response.headers.get('X-RateLimit-Bucket', 'default')
                bucket = self.rate_limiter.get_bucket(bucket_id)
                bucket.update_from_headers(dict(response.headers))
                
                logger.debug("Discord notification sent successfully")
                return True
                
        except requests.exceptions.Timeout:
            logger.error("Discord webhook request timed out")
            return False
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error sending Discord webhook: {e}")
            raise  # Re-raise to trigger retry logic in parent method
            
        except Exception as e:
            logger.error(f"Unexpected error sending Discord notification: {e}")
            return True  # Don't retry on unexpected errors
    
    def send_plaintext(self, message: str, username: Optional[str] = None, avatar_url: Optional[str] = None):
        """
        Send a plain text message to Discord (non-blocking).
        
        Args:
            message: The text message to send
            username: Optional custom username for the webhook
            avatar_url: Optional custom avatar URL for the webhook
        """
        if not self.enabled:
            logger.debug("Discord notifications disabled")
            return
            
        notification_data = {
            'content': message,
            'username': username,
            'avatar_url': avatar_url
        }
        
        self.notification_queue.put(notification_data)
        logger.debug(f"Queued plaintext notification: {message[:50]}...")
    
    def send_embed(self, title: Optional[str] = None, description: Optional[str] = None, color: int = 0x00ff00, 
                   fields: Optional[List[Dict[str, Any]]] = None, footer: Optional[Dict[str, Any]] = None, 
                   author: Optional[Dict[str, Any]] = None, thumbnail: Optional[str] = None, 
                   image: Optional[str] = None, content: Optional[str] = None,
                   username: Optional[str] = None, avatar_url: Optional[str] = None, timestamp: bool = True):
        """
        Send an embed message to Discord (non-blocking).
        
        Args:
            title: Embed title
            description: Embed description
            color: Embed color (hex value)
            fields: List of field dictionaries with 'name', 'value', and optional 'inline'
            footer: Footer dictionary with 'text' and optional 'icon_url'
            author: Author dictionary with 'name' and optional 'url' and 'icon_url'
            thumbnail: Thumbnail image URL
            image: Main image URL
            content: Additional text content outside the embed
            username: Optional custom username for the webhook
            avatar_url: Optional custom avatar URL for the webhook
            timestamp: Whether to include a timestamp
        """
        if not self.enabled:
            logger.debug("Discord notifications disabled")
            return
            
        embed_data = {
            'title': title,
            'description': description,
            'color': color,
            'timestamp': timestamp
        }
        
        if fields:
            embed_data['fields'] = fields
        if footer:
            embed_data['footer'] = footer
        if author:
            embed_data['author'] = author
        if thumbnail:
            embed_data['thumbnail'] = thumbnail
        if image:
            embed_data['image'] = image
            
        notification_data = {
            'content': content,
            'embed_data': embed_data,
            'username': username,
            'avatar_url': avatar_url
        }
        
        self.notification_queue.put(notification_data)
        logger.debug(f"Queued embed notification: {title or 'Untitled'}")
    
    def send_diagnostic(self, level: str, service: str, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Send a diagnostic notification with predefined formatting.
        
        Args:
            level: Diagnostic level ('info', 'warning', 'error', 'critical')
            service: Name of the service/component
            message: The diagnostic message
            details: Optional dictionary of additional details
        """
        if not self.enabled:
            logger.debug("Discord notifications disabled")
            return
            
        # Define colors for different levels
        colors = {
            'info': 0x0099ff,      # Blue
            'warning': 0xffaa00,   # Orange
            'error': 0xff0000,     # Red
            'critical': 0x990000   # Dark red
        }
        
        # Define emojis for different levels
        emojis = {
            'info': '🔵',
            'warning': '🟡',
            'error': '🔴',
            'critical': '🚨'
        }
        
        color = colors.get(level.lower(), 0x808080)  # Default gray
        emoji = emojis.get(level.lower(), '🔘')
        
        fields = [
            {'name': 'Service', 'value': service, 'inline': True},
            {'name': 'Level', 'value': level.upper(), 'inline': True},
            {'name': 'Timestamp', 'value': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'), 'inline': True}
        ]
        
        # Add details as fields if provided
        if details:
            for key, value in details.items():
                fields.append({'name': key, 'value': str(value), 'inline': False})
        
        self.send_embed(
            title=f"{emoji} App Diagnostic - {level.upper()}",
            description=message,
            color=color,
            fields=fields,
            footer={'text': 'SAY Website Backend Diagnostics'}
        )
    
    def send_startup_notification(self, service_name: str = "SAY Website Backend", version: Optional[str] = None):
        """Send a startup notification to indicate the service is running."""
        details = {}
        if version:
            details['Version'] = version
        details['Started At'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        
        self.send_diagnostic('info', service_name, 'Service started successfully', details)
    
    def send_error_notification(self, service: str, error: Exception, context: Optional[str] = None):
        """Send an error notification with exception details."""
        details = {
            'Error Type': type(error).__name__,
            'Error Message': str(error)
        }
        if context:
            details['Context'] = context
            
        self.send_diagnostic('error', service, 'An error occurred', details)
    
    def shutdown(self):
        """Gracefully shutdown the notification manager."""
        logger.info("Shutting down Discord notification manager")
        self._stop_worker.set()
        
        # Wait for queue to be processed
        self.notification_queue.join()
        
        # Wait for worker thread to finish
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)
            
        logger.info("Discord notification manager shut down")
    
    def get_queue_size(self) -> int:
        """Get the current size of the notification queue."""
        return self.notification_queue.qsize()
    
    def is_healthy(self) -> bool:
        """Check if the notification system is healthy."""
        return (self.enabled and 
                self._worker_thread is not None and 
                self._worker_thread.is_alive() and
                not self._stop_worker.is_set())
    
    def get_rate_limit_info(self) -> Dict[str, Any]:
        """Get current rate limit information."""
        info = {
            'global_rate_limit': {
                'active': self.rate_limiter.should_wait_global() > 0,
                'reset_time': self.rate_limiter.global_reset_time,
                'wait_time': self.rate_limiter.should_wait_global()
            },
            'buckets': {}
        }
        
        for bucket_id, bucket in self.rate_limiter.buckets.items():
            info['buckets'][bucket_id] = {
                'limit': bucket.limit,
                'remaining': bucket.remaining,
                'reset_time': bucket.reset_time,
                'reset_after': bucket.reset_after,
                'exhausted': bucket.is_exhausted(),
                'wait_time': bucket.should_wait(),
                'last_updated': bucket.last_updated
            }
        
        return info
    
    def reset_rate_limits(self):
        """Reset all rate limit tracking (for testing purposes)."""
        logger.info("Resetting all rate limit tracking")
        self.rate_limiter = DiscordRateLimiter()


# Create a global instance
discord_notifier = DiscordNotificationManager()