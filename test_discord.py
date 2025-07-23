#!/usr/bin/env python3
"""
Unit tests for the Discord Notification Manager with rate limiting support.
"""

import unittest
import time
import threading
import json
from unittest.mock import patch, MagicMock, Mock
from app.discord import DiscordNotificationManager, DiscordRateLimiter, RateLimitBucket

class TestRateLimitBucket(unittest.TestCase):
    """Test cases for the RateLimitBucket class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.bucket = RateLimitBucket("test_bucket")
    
    def test_initialization(self):
        """Test bucket initialization."""
        self.assertEqual(self.bucket.bucket_id, "test_bucket")
        self.assertIsNone(self.bucket.limit)
        self.assertIsNone(self.bucket.remaining)
        self.assertIsNone(self.bucket.reset_time)
        self.assertIsNone(self.bucket.reset_after)
    
    def test_update_from_headers(self):
        """Test updating bucket from Discord API headers."""
        headers = {
            'X-RateLimit-Limit': '5',
            'X-RateLimit-Remaining': '3',
            'X-RateLimit-Reset': '1627849200.123',
            'X-RateLimit-Reset-After': '60.5'
        }
        
        self.bucket.update_from_headers(headers)
        
        self.assertEqual(self.bucket.limit, 5)
        self.assertEqual(self.bucket.remaining, 3)
        self.assertEqual(self.bucket.reset_time, 1627849200.123)
        self.assertEqual(self.bucket.reset_after, 60.5)
        self.assertIsNotNone(self.bucket.last_updated)
    
    def test_should_wait_with_remaining(self):
        """Test should_wait when requests remain."""
        self.bucket.remaining = 3
        self.assertEqual(self.bucket.should_wait(), 0.0)
    
    def test_should_wait_exhausted(self):
        """Test should_wait when bucket is exhausted."""
        self.bucket.remaining = 0
        self.bucket.reset_after = 30.0
        self.bucket.last_updated = time.time()
        
        wait_time = self.bucket.should_wait()
        self.assertGreater(wait_time, 0)
        self.assertLessEqual(wait_time, 30.0)
    
    def test_is_exhausted(self):
        """Test is_exhausted method."""
        self.bucket.remaining = 0
        self.assertTrue(self.bucket.is_exhausted())
        
        self.bucket.remaining = 1
        self.assertFalse(self.bucket.is_exhausted())

class TestDiscordRateLimiter(unittest.TestCase):
    """Test cases for the DiscordRateLimiter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.rate_limiter = DiscordRateLimiter()
    
    def test_get_bucket(self):
        """Test bucket creation and retrieval."""
        bucket1 = self.rate_limiter.get_bucket("test_bucket")
        bucket2 = self.rate_limiter.get_bucket("test_bucket")
        
        # Should return the same bucket instance
        self.assertIs(bucket1, bucket2)
        self.assertEqual(bucket1.bucket_id, "test_bucket")
    
    def test_handle_rate_limit_response(self):
        """Test handling 429 rate limit responses."""
        # Test per-route rate limit
        response_data = {
            'message': 'You are being rate limited.',
            'retry_after': 5.0,
            'global': False
        }
        headers = {'X-RateLimit-Bucket': 'test_bucket'}
        
        retry_after = self.rate_limiter.handle_rate_limit_response(response_data, headers)
        self.assertEqual(retry_after, 5.0)
        
        # Test global rate limit
        response_data = {
            'message': 'You are being rate limited.',
            'retry_after': 10.0,
            'global': True
        }
        
        retry_after = self.rate_limiter.handle_rate_limit_response(response_data, headers)
        self.assertEqual(retry_after, 10.0)
        
        # Global reset time should be set
        self.assertGreater(self.rate_limiter.global_reset_time, time.time())
    
    def test_should_wait_global(self):
        """Test global rate limit waiting."""
        # No global rate limit
        self.assertEqual(self.rate_limiter.should_wait_global(), 0.0)
        
        # Set global rate limit
        self.rate_limiter.global_reset_time = time.time() + 5.0
        wait_time = self.rate_limiter.should_wait_global()
        self.assertGreater(wait_time, 0)
        self.assertLessEqual(wait_time, 5.0)

class TestDiscordNotificationManager(unittest.TestCase):
    """Test cases for the Discord Notification Manager with rate limiting."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a test instance with a mock webhook URL
        self.test_webhook_url = "https://discord.com/api/webhooks/test/test"
        self.notifier = DiscordNotificationManager(webhook_url=self.test_webhook_url)
        
        # Wait a moment for the worker thread to start
        time.sleep(0.1)
    
    def tearDown(self):
        """Clean up after tests."""
        if hasattr(self, 'notifier'):
            self.notifier.shutdown()
    
    def test_initialization(self):
        """Test that the notification manager initializes correctly."""
        self.assertTrue(self.notifier.enabled)
        self.assertEqual(self.notifier.webhook_url, self.test_webhook_url)
        self.assertIsNotNone(self.notifier._worker_thread)
        self.assertIsNotNone(self.notifier.rate_limiter)
    
    def test_get_rate_limit_info(self):
        """Test rate limit information retrieval."""
        info = self.notifier.get_rate_limit_info()
        
        self.assertIn('global_rate_limit', info)
        self.assertIn('buckets', info)
        self.assertIn('active', info['global_rate_limit'])
        self.assertIn('wait_time', info['global_rate_limit'])
    
    def test_reset_rate_limits(self):
        """Test rate limit reset functionality."""
        # Create some rate limit data
        bucket = self.notifier.rate_limiter.get_bucket("test")
        bucket.remaining = 0
        
        # Reset should clear everything
        self.notifier.reset_rate_limits()
        
        # Should be a new rate limiter instance
        self.assertEqual(len(self.notifier.rate_limiter.buckets), 0)
    
    @patch('requests.post')
    def test_send_notification_success(self, mock_post):
        """Test successful notification sending."""
        # Mock successful response
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.headers = {
            'X-RateLimit-Limit': '5',
            'X-RateLimit-Remaining': '4',
            'X-RateLimit-Reset': str(time.time() + 60),
            'X-RateLimit-Reset-After': '60',
            'X-RateLimit-Bucket': 'webhook_bucket'
        }
        mock_post.return_value = mock_response
        
        # Send a notification
        self.notifier.send_plaintext("Test message")
        
        # Wait for processing
        time.sleep(0.5)
        
        # Verify request was made
        mock_post.assert_called()
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], self.test_webhook_url)
        self.assertIn('content', call_args[1]['json'])
    
    @patch('requests.post')
    def test_send_notification_rate_limited(self, mock_post):
        """Test handling of 429 rate limit responses."""
        # Mock 429 response
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 429
        mock_response.headers = {
            'Retry-After': '5',
            'X-RateLimit-Bucket': 'webhook_bucket'
        }
        mock_response.json.return_value = {
            'message': 'You are being rate limited.',
            'retry_after': 5.0,
            'global': False
        }
        
        # First call returns 429, second call succeeds
        success_response = Mock()
        success_response.ok = True
        success_response.status_code = 200
        success_response.headers = {'X-RateLimit-Bucket': 'webhook_bucket'}
        
        mock_post.side_effect = [mock_response, success_response]
        
        # Send a notification
        start_time = time.time()
        self.notifier.send_plaintext("Test message")
        
        # Wait for processing (should include rate limit delay)
        time.sleep(6)  # Allow time for rate limit + processing
        
        # Verify multiple calls were made (original + retry)
        self.assertGreater(mock_post.call_count, 1)
    
    @patch('requests.post')
    def test_send_notification_network_error(self, mock_post):
        """Test handling of network errors with retry."""
        import requests
        
        # Mock network error followed by success
        mock_post.side_effect = [
            requests.exceptions.ConnectionError("Network error"),
            Mock(ok=True, status_code=200, headers={})
        ]
        
        # Send a notification
        self.notifier.send_plaintext("Test message")
        
        # Wait for processing (should include exponential backoff)
        time.sleep(3)
        
        # Should have retried after network error
        self.assertGreaterEqual(mock_post.call_count, 2)
    
    def test_health_check_with_rate_limits(self):
        """Test health check includes rate limit information."""
        self.assertTrue(self.notifier.is_healthy())
        
        # Add some rate limit data
        bucket = self.notifier.rate_limiter.get_bucket("test")
        bucket.limit = 5
        bucket.remaining = 2
        
        rate_info = self.notifier.get_rate_limit_info()
        self.assertIn('test', rate_info['buckets'])
        self.assertEqual(rate_info['buckets']['test']['limit'], 5)
        self.assertEqual(rate_info['buckets']['test']['remaining'], 2)

if __name__ == '__main__':
    # Run the tests
    unittest.main()
