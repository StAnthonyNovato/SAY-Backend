#!/usr/bin/env python3
"""
Example usage of the Discord Notification Manager for app diagnostics.
This file demonstrates how to use the non-blocking Discord notifications with rate limiting.
"""

import time
import os
from app.discord import discord_notifier

def main():
    """
    Example usage of the Discord notification system.
    
    To use this example:
    1. Set your Discord webhook URL as an environment variable:
       export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/your/webhook/url"
    2. Run this script: python discord_example.py
    """
    
    # Check if the notification system is enabled
    if not discord_notifier.enabled:
        print("Discord notifications are disabled. Please set DISCORD_WEBHOOK_URL environment variable.")
        return
    
    print("Testing Discord notification system with rate limiting...")
    print(f"Queue size: {discord_notifier.get_queue_size()}")
    print(f"System healthy: {discord_notifier.is_healthy()}")
    
    # Display initial rate limit info
    rate_limit_info = discord_notifier.get_rate_limit_info()
    print(f"Initial rate limit info: {rate_limit_info}")
    
    # Example 1: Send a plain text message
    print("\n1. Sending plain text notification...")
    discord_notifier.send_plaintext(
        "🔧 SAY Website Backend - Rate limiting test notification from diagnostic system",
        username="SAY Diagnostics Bot"
    )
    
    # Example 2: Send multiple notifications to test rate limiting
    print("2. Sending multiple notifications to test rate limiting...")
    for i in range(5):
        discord_notifier.send_embed(
            title=f"Rate Limit Test #{i+1}",
            description=f"Testing rate limiting with notification {i+1} of 5",
            color=0x0099ff,  # Blue
            fields=[
                {"name": "Test Number", "value": str(i+1), "inline": True},
                {"name": "Status", "value": "Testing Rate Limits", "inline": True},
                {"name": "Timestamp", "value": time.strftime("%H:%M:%S"), "inline": True}
            ],
            footer={"text": "SAY Diagnostics • Rate Limit Testing"},
            username="SAY Rate Limit Tester"
        )
        # Small delay between notifications
        time.sleep(0.1)
    
    # Example 3: Send diagnostic notifications
    print("3. Sending diagnostic notifications...")
    
    # Info level
    discord_notifier.send_diagnostic(
        level="info",
        service="Rate Limit Test",
        message="Rate limiting system is working correctly",
        details={
            "Notifications Sent": "5",
            "Rate Limiter": "Active",
            "Queue Management": "Working"
        }
    )
    
    # Warning level with rate limit info
    rate_limit_info = discord_notifier.get_rate_limit_info()
    discord_notifier.send_diagnostic(
        level="warning",
        service="Rate Limit Monitor",
        message="Rate limit status check",
        details={
            "Global Active": str(rate_limit_info['global_rate_limit']['active']),
            "Buckets Tracked": str(len(rate_limit_info['buckets'])),
            "Queue Size": str(discord_notifier.get_queue_size())
        }
    )
    
    print(f"\nCurrent queue size: {discord_notifier.get_queue_size()}")
    print("Waiting for notifications to be sent...")
    
    # Wait and monitor the rate limiting
    for i in range(10):
        time.sleep(1)
        queue_size = discord_notifier.get_queue_size()
        rate_info = discord_notifier.get_rate_limit_info()
        
        print(f"After {i+1}s: Queue={queue_size}, Global wait={rate_info['global_rate_limit']['wait_time']:.2f}s")
        
        if queue_size == 0:
            break
    
    # Example 4: Test burst sending (this might trigger rate limits)
    print("\n4. Testing burst sending (may trigger rate limits)...")
    
    start_time = time.time()
    for i in range(10):
        discord_notifier.send_plaintext(
            f"Burst test message #{i+1} - This is testing Discord's rate limiting",
            username="Burst Tester"
        )
    
    # Monitor the queue and rate limits during burst
    print("Monitoring burst sending...")
    while discord_notifier.get_queue_size() > 0 and time.time() - start_time < 30:
        time.sleep(1)
        queue_size = discord_notifier.get_queue_size()
        rate_info = discord_notifier.get_rate_limit_info()
        
        elapsed = time.time() - start_time
        print(f"Burst test {elapsed:.1f}s: Queue={queue_size}")
        
        # Show bucket info if available
        for bucket_id, bucket_info in rate_info['buckets'].items():
            if bucket_info['remaining'] is not None:
                print(f"  Bucket {bucket_id}: {bucket_info['remaining']}/{bucket_info['limit']} remaining, wait={bucket_info['wait_time']:.2f}s")
    
    # Final status
    print(f"\nFinal queue size: {discord_notifier.get_queue_size()}")
    print("Rate limiting test completed!")
    
    # Display final rate limit statistics
    final_rate_info = discord_notifier.get_rate_limit_info()
    print("\nFinal Rate Limit Status:")
    print(f"Global rate limit active: {final_rate_info['global_rate_limit']['active']}")
    print(f"Tracked buckets: {len(final_rate_info['buckets'])}")
    
    for bucket_id, bucket_info in final_rate_info['buckets'].items():
        print(f"  {bucket_id}: {bucket_info['remaining']}/{bucket_info['limit']} remaining")

if __name__ == "__main__":
    main()
