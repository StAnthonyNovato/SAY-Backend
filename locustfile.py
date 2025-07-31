# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

"""
Locust load testing configuration for SAY Website Backend
Tests email subscription and confirmation endpoints under load
"""

from locust import HttpUser, task, between
import json
import random
import string
import uuid

def generate_fake_email():
    """Generate a fake email address without external dependencies"""
    domains = ["example.com", "test.com", "loadtest.org", "demo.net"]
    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    domain = random.choice(domains)
    return f"{username}@{domain}"

class EmailSubscriptionUser(HttpUser):
    """
    Simulates users interacting with the email subscription system
    Realistic behavior: ~90% of users who subscribe will also confirm
    """
    wait_time = between(1, 5)  # Wait 1-5 seconds between requests
    
    def on_start(self):
        """Called when a simulated user starts"""
        # Generate a unique email for this user session
        self.email = generate_fake_email()
        self.confirmation_code = None
        self.has_subscribed = False
        self.should_confirm = random.random() < 0.9  # 90% will confirm
        
    @task(10)  # Much higher weight for subscription
    def subscribe_json(self):
        """Test subscription with JSON payload (most common)"""
        if self.has_subscribed:
            return  # Don't subscribe again
            
        payload = {"email": self.email}
        headers = {"Content-Type": "application/json"}
        
        response = self.client.post("/api/subscribe", json=payload, headers=headers)
        
        # If LOAD_TESTING is enabled, extract confirmation code
        if response.status_code == 200:
            self.has_subscribed = True
            try:
                data = response.json()
                if 'confirmation_code' in data:
                    self.confirmation_code = data['confirmation_code']
            except:
                pass  # Not JSON or no confirmation code, that's fine
    
    @task(2)
    def subscribe_form(self):
        """Test subscription with form data (smaller portion of users)"""
        if self.has_subscribed:
            return  # Don't subscribe again
            
        form_data = {"email": self.email}  # Use same email as JSON test
        response = self.client.post("/api/subscribe", data=form_data)
        
        if response.status_code == 200:
            self.has_subscribed = True
            try:
                data = response.json()
                if 'confirmation_code' in data:
                    self.confirmation_code = data['confirmation_code']
            except:
                pass
    
    @task(15)  # Very high priority for confirmation
    def confirm_valid_code(self):
        """Test confirmation with valid code (90% of users will do this)"""
        if self.confirmation_code and self.should_confirm:
            response = self.client.get(f"/api/confirm?code={self.confirmation_code}", name="confirm_valid_code")
            if response.status_code == 200:
                # Reset confirmation code after successful confirmation
                self.confirmation_code = None
            
    
    @task(1)  # Much lower frequency for bad requests
    def confirm_invalid_code(self):
        """Test confirmation with invalid codes (realistic typos/errors)"""
        # Only do this occasionally and make it more realistic
        if random.random() < 0.1:  # Only 10% chance to run this
            invalid_codes = [
                str(uuid.uuid4()),  # Valid UUID format but not in DB
                "invalid-code-123",  # Invalid format
            ]
            
            code = random.choice(invalid_codes)
            response = self.client.get(f"/api/confirm?code={code}", name="confirm_invalid_code")
    
    @task(1)
    def healthcheck(self):
        """Test the healthcheck endpoint"""
        self.client.get("/api/healthcheck")

class RealisticUserJourney(HttpUser):
    """
    Simulates complete realistic user journeys from subscription to confirmation
    This user follows a linear path: subscribe → wait → confirm
    """
    wait_time = between(2, 8)  # Realistic user thinking time
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.journey_complete = False
        self.email = None
        self.confirmation_code = None
    
    def on_start(self):
        """Start the user journey"""
        self.email = generate_fake_email()
        self.journey_complete = False
        
    @task
    def complete_user_journey(self):
        """Complete the full subscription → confirmation journey"""
        if self.journey_complete:
            # Start a new journey with a new email
            self.email = generate_fake_email()
            self.confirmation_code = None
            self.journey_complete = False
        
        if not self.confirmation_code:
            # Step 1: Subscribe
            payload = {"email": self.email}
            response = self.client.post("/api/subscribe", json=payload)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'confirmation_code' in data:
                        self.confirmation_code = data['confirmation_code']
                except:
                    pass
        else:
            # Step 2: Confirm (90% of users will do this)
            if random.random() < 0.9:
                response = self.client.get(f"/api/confirm?code={self.confirmation_code}", name="confirm_user_journey")
                if response.status_code == 200:
                    self.journey_complete = True
            else:
                # 10% abandon without confirming
                self.journey_complete = True

class HighVolumeSubscriptionUser(HttpUser):
    """
    Simulates high-volume subscription attempts (testing rate limiting)
    """
    wait_time = between(0.1, 0.5)  # Very fast requests to trigger rate limits
    
    def on_start(self):
        """Use the same email to trigger rate limiting"""
        self.email = "loadtest@example.com"
    
    @task
    def rapid_subscribe(self):
        """Rapidly attempt subscriptions to test rate limiting"""
        payload = {"email": self.email}
        
        response = self.client.post("/api/subscribe", json=payload)
        # Both success and rate limit responses are valid for this test
        # Locust will automatically track response times and status codes

class SpamHealthCheckUser(HttpUser):
    """
    Simulates a user spamming the health check endpoint
    This is to test how the system handles excessive requests
    """
    wait_time = between(1, 5)  # Extremely fast requests
    
    @task(100)  # Very high frequency to simulate spam
    def spam_healthcheck(self):
        """Spam the health check endpoint"""
        self.client.get("/api/healthcheck", name="spam_healthcheck")

class AdminUser(HttpUser):
    """
    Simulates admin/debug operations
    """
    wait_time = between(2, 10)
    
    @task
    def check_rate_limit_internals(self):
        """Test the debug endpoint (only works in debug mode)"""
        response = self.client.get("/api/rateLimitInternals")
        # This endpoint returns 403 in production, 200 in debug mode
        # Both are expected responses

class StressTestUser(HttpUser):
    """
    High-intensity user for stress testing
    More realistic: generates unique emails and completes full journeys
    """
    wait_time = between(0.2, 1)  # Fast but not unrealistic
    
    def on_start(self):
        self.email_counter = 0
        self.pending_confirmations = []  # Store codes to confirm later
    
    @task(8)
    def stress_subscribe(self):
        """Generate unique emails for each request to avoid rate limiting"""
        self.email_counter += 1
        unique_email = f"stress{self.email_counter}_{random.randint(1000, 9999)}@loadtest.com"
        
        payload = {"email": unique_email}
        response = self.client.post("/api/subscribe", json=payload, name="stress_subscribe")
        
        # Store confirmation codes for later confirmation
        if response.status_code == 200:
            try:
                data = response.json()
                if 'confirmation_code' in data:
                    self.pending_confirmations.append(data['confirmation_code'])
            except:
                pass
    
    @task(7)  # High rate of confirmations
    def stress_confirm(self):
        """Confirm pending subscriptions"""
        if self.pending_confirmations and random.random() < 0.85:  # 85% confirmation rate
            code = self.pending_confirmations.pop(0)
            response = self.client.get(f"/api/confirm?code={code}", name="stress_confirm")

# Custom user classes for different test scenarios
# You can run specific user types with: locust -f locustfile.py --users 50 --spawn-rate 5 --host http://localhost:8000 EmailSubscriptionUser

"""
Usage Examples:

1. Realistic load test (90% confirmation rate):
   locust -f locustfile.py --users 20 --spawn-rate 2 --host http://localhost:8000

2. Complete user journey testing:
   locust -f locustfile.py --users 15 --spawn-rate 2 --host http://localhost:8000 RealisticUserJourney

3. Rate limit testing:
   locust -f locustfile.py --users 10 --spawn-rate 5 --host http://localhost:8000 HighVolumeSubscriptionUser

4. Stress testing with confirmations:
   locust -f locustfile.py --users 30 --spawn-rate 8 --host http://localhost:8000 StressTestUser

5. Web UI (recommended):
   locust -f locustfile.py --host http://localhost:8000
   Then open http://localhost:8089

Realistic Testing Features:
- 90% of users complete the full subscribe → confirm flow
- Minimal invalid/bad requests (more realistic)
- Users don't repeatedly subscribe with the same email
- Proper wait times between subscription and confirmation

Environment Variables to Test:
- NO_EMAIL=1 (to disable actual email sending during load tests)
- LOAD_TESTING=1 (enables confirmation codes in API responses for full flow testing)
- RATE_LIMIT_EMAILS_PER_HOUR=10 (higher limit for realistic testing)

Full Load Testing Setup:
export NO_EMAIL=1 LOAD_TESTING=1 RATE_LIMIT_EMAILS_PER_HOUR=20
locust -f locustfile.py --host http://localhost:8000

Production Testing:
- Always test against a staging environment first
- Use --host https://stanthonyyouth.alphagame.dev for production
- Start with low user counts and gradually increase
- Monitor your database connections and Discord webhook limits
- NEVER set LOAD_TESTING=1 in production!
"""
