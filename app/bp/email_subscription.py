# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

from flask import Blueprint, request, current_app, jsonify, g, Response
from os import getenv
from datetime import datetime, timedelta
from uuid import uuid4
from ..mail.emailmanager import SMTPManager
from ..discord import discord_notifier
import threading

email_subscription_bp = Blueprint('email_subscription', __name__)

ACTUALLY_SEND_EMAIL = not getenv("NO_EMAIL")  # If NO_EMAIL is set, emails will not be sent

# Rate limiting configuration
RATE_LIMIT_EMAILS_PER_HOUR = int(getenv("RATE_LIMIT_EMAILS_PER_HOUR", "2"))  # Default: 2 emails per hour
RATE_LIMIT_CLEANUP_INTERVAL = int(getenv("RATE_LIMIT_CLEANUP_INTERVAL", "3600"))  # Cleanup every hour

# In-memory rate limiting storage
# Structure: {email: [timestamp1, timestamp2, ...]}
rate_limit_storage = {}
rate_limit_lock = threading.Lock()  # Thread safety for concurrent requests

# SMTP configuration
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_PASSWORD = getenv("GOOGLE_APP_PASSWORD")

with open("email_templates/NEW_SUBSCRIBER_CONFIRMATION.txt", "r") as file:
    NEW_SUBSCRIBER_CONFIRMATION_TEMPLATE = file.read()

with open("email_templates/NEW_SUBSCRIBER_CONFIRMATION.html", "r") as file:
    NEW_SUBSCRIBER_CONFIRMATION_HTML_TEMPLATE = file.read()

def cleanup_old_rate_limit_entries():
    """Clean up old rate limit entries to prevent memory bloat"""
    with rate_limit_lock:
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(hours=1)
        
        emails_to_remove = []
        for email, timestamps in rate_limit_storage.items():
            # Remove timestamps older than 1 hour
            rate_limit_storage[email] = [ts for ts in timestamps if ts > cutoff_time]
            
            # If no timestamps left, mark email for removal
            if not rate_limit_storage[email]:
                emails_to_remove.append(email)
        
        # Remove emails with no recent activity
        for email in emails_to_remove:
            del rate_limit_storage[email]

def can_send_email(email: str) -> bool:
    """Check if user can send email based on rate limiting"""
    with rate_limit_lock:
        current_time = datetime.now()
        one_hour_ago = current_time - timedelta(hours=1)
        
        # Clean up old entries for this email
        if email in rate_limit_storage:
            rate_limit_storage[email] = [ts for ts in rate_limit_storage[email] if ts > one_hour_ago]
            
            # Check if user has exceeded rate limit
            if len(rate_limit_storage[email]) >= RATE_LIMIT_EMAILS_PER_HOUR:
                return False
        
        return True

def record_email_sent(email: str):
    """Record that an email was sent for rate limiting purposes"""
    with rate_limit_lock:
        current_time = datetime.now()
        
        if email not in rate_limit_storage:
            rate_limit_storage[email] = []
        
        rate_limit_storage[email].append(current_time)
        
        # Also do periodic cleanup (every 100 emails or so)
        if len(rate_limit_storage) % 100 == 0:
            cleanup_old_rate_limit_entries()
    
    current_app.logger.info(f"Email sent to {email} - rate limit tracking updated")

def send_confirmation_email(email: str, confirmation_code: str):
    """Send confirmation email to subscriber"""
    if not ACTUALLY_SEND_EMAIL:
        print(f"Skipping email sending for {email} (ACTUALLY_SEND_EMAIL is False)")
        return
    
    if not can_send_email(email):
        raise Exception("Daily email limit exceeded")
    
    try:
        smtp_password = SMTP_PASSWORD
        if not smtp_password:
            raise Exception("SMTP_PASSWORD must be set in the environment variables")
        
        DOMAIN = (
            "http://localhost:8000" if current_app.debug else "https://stanthonyyouth.alphagame.dev"
        )

        subject = f"St. Anthony Youth Newsletter Confirmation - {email}"
        
        # Use SMTPManager to send email with template
        with SMTPManager(
            smtp_server=SMTP_SERVER,
            smtp_port=SMTP_PORT,
            smtp_password=smtp_password,
            smtp_from_email=getenv("EMAIL", "stanthonyyouth.noreply@gmail.com")
        ) as smtp_manager:
            smtp_manager.send_template_email(
                to_email=email,
                subject=subject,
                template_content=NEW_SUBSCRIBER_CONFIRMATION_TEMPLATE,
                html_template_content=NEW_SUBSCRIBER_CONFIRMATION_HTML_TEMPLATE,
                # template variables
                confirmation_link=f"{DOMAIN}/api/confirm?code={confirmation_code}",
                confirmation_code=confirmation_code,
                support_email=getenv("EMAIL", "damien@alphagame.dev")
            )
        
        record_email_sent(email)
        
        # Send success notification to Discord
        discord_notifier.send_diagnostic(
            level="info",
            service="Email Service",
            message=f"Confirmation email sent successfully",
            details={
                "Recipient": email,
                "Type": "New Subscriber Confirmation",
                "Confirmation Code": confirmation_code[:8] + "..."
            }
        )
        
    except Exception as e:
        print(f"Error sending email: {e}")
        
        # Send error notification to Discord
        discord_notifier.send_error_notification(
            service="Email Service",
            error=e,
            context=f"Failed to send confirmation email to {email}"
        )
        
        raise

@email_subscription_bp.route("/rateLimitInternals")
def rate_limit_internals():
    """Internal endpoint to view rate limit storage for debugging"""
    if not current_app.debug:
        return jsonify({
            "success": False,
            "error": "This endpoint is only available in debug mode"
        }), 403
    
    with rate_limit_lock:
        return jsonify({
            "rate_limit_storage": {
                email: timestamps[:10]  # Show only first 10 timestamps for brevity
                for email, timestamps in rate_limit_storage.items()
            },
            "rate_limit_count": len(rate_limit_storage),
            "rate_limit_cleanup_interval": RATE_LIMIT_CLEANUP_INTERVAL,
            "rate_limit_emails_per_hour": RATE_LIMIT_EMAILS_PER_HOUR
        }), 200
    
@email_subscription_bp.route('/subscribe', methods=['POST']) # pyright: ignore[reportArgumentType]
def subscribe():
    """Subscribe user to email list - simplified without database"""
    # Handle both JSON and form data
    if request.is_json:
        json = request.get_json()
        if not json or 'email' not in json:
            response = jsonify({
                "success": False,
                "error": "Invalid request",
                "message": "Email field is required",
                "content_type": request.content_type
            })
            response.status_code = 400
            return response
        email = json['email']
    else:
        # Handle HTML form submission
        email = request.form.get('email')
        if not email:
            return jsonify({
                "success": False,
                "error": "Invalid request",
                "message": "Email field is required",
                "content_type": request.content_type
            }), 400

    # Check rate limit
    if not can_send_email(email):
        # Send rate limit notification to Discord
        discord_notifier.send_diagnostic(
            level="warning",
            service="Email Service",
            message="Email subscription rate limit exceeded",
            details={
                "Email": email,
                "Action": "Subscribe Request Blocked",
                "Limit": f"{RATE_LIMIT_EMAILS_PER_HOUR} emails per hour"
            }
        )
        response = jsonify({
            "success": False,
            "error": "Rate limit exceeded",
            "message": f"Rate limit exceeded. You can only send {RATE_LIMIT_EMAILS_PER_HOUR} emails per hour. Please try again later.",
            "email": email
        })
        response.status_code = 429
        return response

    # Generate a new confirmation code
    confirmation_code = str(uuid4())
    
    cursor = g.cursor
    if cursor is None:
        current_app.logger.error("No database cursor available")
        return jsonify({
            "success": False,
            "error": "Database connection error",
            "message": "Unable to process request at this time"
        }), 500

    # Check if user already exists in the database
    cursor.execute("""
                   SELECT id, email, confirmation_token, confirmed FROM newsletter WHERE email = %s
                   """, (email,))
    existing_subscription = cursor.fetchone()

    # Track what action we're taking for Discord notifications
    action_type = None
    
    # Did we find an existing subscription?
    if existing_subscription:
        subscription_id, existing_email, existing_token, is_confirmed = existing_subscription
        
        if is_confirmed:
            # User is already confirmed, no need to send another email
            return jsonify({
                "success": True,
                "message": "You are already subscribed and confirmed!",
                "email": email,
                "action": "already_confirmed"
            }), 200
        else:
            # User exists but not confirmed, keep their existing confirmation token
            confirmation_code = existing_token
            action_type = "resend_confirmation"
            current_app.logger.info(f"Resending confirmation email for existing unconfirmed user: {email}")
    else:
        # New user, insert into database
        cursor.execute("""
            INSERT INTO newsletter (email, confirmation_token)
            VALUES (%s, %s)
        """, (email, confirmation_code))
        action_type = "new_subscription"
        current_app.logger.info(f"Added new user to newsletter: {email}")
    
    try:
        # Send confirmation email to subscriber
        send_confirmation_email(email, confirmation_code)
        
        # Send appropriate Discord notification based on action type
        if action_type == "new_subscription":
            discord_notifier.send_embed(
                title="📧 New Email Subscriber",
                description="A new user has subscribed to the email newsletter",
                color=0x00ff00,  # Green
                fields=[
                    {"name": "Email", "value": email, "inline": True},
                    {"name": "Status", "value": "Pending Confirmation", "inline": True},
                    {"name": "Action", "value": "New Subscription", "inline": True}
                ],
                footer={"text": "SAY Website Backend • Email Service"}
            )
            
            return jsonify({
                "success": True,
                "message": "Subscription successful! We've sent you a confirmation email. (You might need to check your spam folder)",
                "email": email,
                "action": "new_subscription"
            }), 200
            
        elif action_type == "resend_confirmation":
            discord_notifier.send_embed(
                title="🔄 Confirmation Email Resent",
                description="Resent confirmation email to existing unconfirmed subscriber",
                color=0xffa500,  # Orange
                fields=[
                    {"name": "Email", "value": email, "inline": True},
                    {"name": "Status", "value": "Still Pending Confirmation", "inline": True},
                    {"name": "Action", "value": "Resent Confirmation Email", "inline": True}
                ],
                footer={"text": "SAY Website Backend • Email Service"}
            )
            
            return jsonify({
                "success": True,
                "message": "We've resent your confirmation email. Please check your inbox (and spam folder).",
                "email": email,
                "action": "resend_confirmation"
            }), 200
        
    except Exception as e:
        # Send error notification to Discord 
        discord_notifier.send_error_notification(
            service="Email Service",
            error=e,
            context=f"Failed to process subscription for {email} (action: {action_type or 'unknown'})"
        )
        
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Email sending failed. Please try again later.",
            "email": email
        }), 500

@email_subscription_bp.route('/confirm', methods=['GET'])
def confirm():
    """Confirm user's email address using the database"""
    code = request.args.get('code')
    if not code:
        return jsonify({
            "success": False,
            "error": "Invalid request",
            "message": "Confirmation code is required"
        }), 400

    cursor = g.cursor
    if cursor is None:
        current_app.logger.error("No database cursor available for confirmation")
        return jsonify({
            "success": False,
            "error": "Database connection error",
            "message": "Unable to process confirmation at this time"
        }), 500
    
    # Look up the confirmation token in the database
    cursor.execute("""
        SELECT id, email, confirmed FROM newsletter 
        WHERE confirmation_token = %s
    """, (code,))
    
    subscription = cursor.fetchone()
    
    if not subscription:
        # Invalid confirmation code
        discord_notifier.send_diagnostic(
            level="warning",
            service="Email Service",
            message="Invalid confirmation code attempted",
            details={
                "Confirmation Code": code[:8] + "...",
                "Action": "Confirmation Failed"
            }
        )
        
        return jsonify({
            "success": False,
            "error": "Invalid confirmation code",
            "message": "The confirmation code is invalid or has expired"
        }), 400
    
    subscription_id, email, is_confirmed = subscription
    
    if is_confirmed:
        # Already confirmed
        return jsonify({
            "success": True,
            "message": "Email was already confirmed",
            "email": email,
            "status": "already_confirmed"
        }), 200
    
    # Confirm the subscription
    cursor.execute("""
        UPDATE newsletter 
        SET confirmed = TRUE, updated_at = CURRENT_TIMESTAMP 
        WHERE id = %s
    """, (subscription_id,))
    
    # Send confirmation success notification to Discord
    discord_notifier.send_embed(
        title="✅ Email Confirmation Successful",
        description="A user has successfully confirmed their email subscription",
        color=0x00ff00,  # Green
        fields=[
            {"name": "Email", "value": email, "inline": True},
            {"name": "Status", "value": "Confirmed ✅", "inline": True},
            {"name": "Confirmation Code", "value": code[:8] + "...", "inline": True}
        ],
        footer={"text": "SAY Website Backend • Email Service"}
    )
    
    current_app.logger.info(f"Successfully confirmed email subscription for: {email}")
    
    return jsonify({
        "success": True,
        "message": "Email confirmed successfully! You're now subscribed to our newsletter.",
        "email": email,
        "status": "confirmed"
    }), 200

# Testing commands:
# Subscribe: curl -X POST -H "Content-Type: application/json" -d '{"email": "damien@alphagame.dev"}' http://localhost:8000/api/subscribe
# Form Submit: curl -X POST -d "email=damien@alphagame.dev" http://localhost:8000/api/subscribe
# Confirm: curl http://localhost:8000/api/confirm?code=CONFIRMATION_CODE_HERE
# Rate limit debug: curl http://localhost:8000/api/rateLimitInternals (debug mode only)

# Features implemented:
# ✅ Full MySQL database integration with newsletter table
# ✅ Rate limiting with in-memory storage
# ✅ Duplicate email handling (existing confirmed vs unconfirmed users)
# ✅ Proper confirmation token validation
# ✅ Discord notifications for all events
# ✅ Thread-safe operations