# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

from flask import Blueprint, request, current_app, jsonify, g
from os import getenv
from datetime import datetime
from uuid import uuid4
from ..mail.emailmanager import SMTPManager
from ..discord import discord_notifier

email_subscription_bp = Blueprint('email_subscription', __name__)

ACTUALLY_SEND_EMAIL = not getenv("NO_EMAIL")  # If NO_EMAIL is set, emails will not be sent

# SMTP configuration
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_PASSWORD = getenv("GOOGLE_APP_PASSWORD")

with open("email_templates/NEW_SUBSCRIBER_CONFIRMATION.txt", "r") as file:
    NEW_SUBSCRIBER_CONFIRMATION_TEMPLATE = file.read()

with open("email_templates/NEW_SUBSCRIBER_CONFIRMATION.html", "r") as file:
    NEW_SUBSCRIBER_CONFIRMATION_HTML_TEMPLATE = file.read()

def can_send_email(email: str) -> bool:
    """Check if user can send email - simplified without database"""
    # For now, always allow emails (you can add rate limiting later)
    return True

def record_email_sent(email: str):
    """Record that an email was sent - simplified without database"""
    current_app.logger.info(f"Email sent to {email}")

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
            "http://localhost:8000" if current_app.debug else "https://say-services.alphagame.dev"
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

@email_subscription_bp.route('/subscribe', methods=['POST'])
def subscribe():
    """Subscribe user to email list - simplified without database"""
    # Handle both JSON and form data
    if request.is_json:
        json = request.get_json()
        if not json or 'email' not in json:
            return jsonify({
                "success": False,
                "error": "Invalid request",
                "message": "Email field is required",
                "content_type": request.content_type
            }), 400
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
                "Limit": "2 emails per day"
            }
        )
        
        return jsonify({
            "success": False,
            "error": "Rate limit exceeded",
            "message": "Daily email limit exceeded. Please try again tomorrow.",
            "email": email
        }), 429

    # Generate a new confirmation code
    confirmation_code = str(uuid4())
    
    try:
        # Send confirmation email to subscriber
        send_confirmation_email(email, confirmation_code)
        
        # Send new subscriber notification to Discord
        discord_notifier.send_embed(
            title="📧 New Email Subscriber",
            description="A new user has subscribed to the email newsletter",
            color=0x00ff00,  # Green
            fields=[
                {"name": "Email", "value": email, "inline": True},
                {"name": "Status", "value": "Pending Confirmation", "inline": True},
                {"name": "Action", "value": "Confirmation Email Sent", "inline": True}
            ],
            footer={"text": "SAY Website Backend • Email Service"}
        )
        
        return jsonify({
            "success": True,
            "message": "Subscription Successful. We've sent you a confirmation email. (You might need to check your spam folder)",
            "email": email,
            "action": "subscribed"
        }), 200
        
    except Exception as e:
        # Send error notification to Discord 
        discord_notifier.send_error_notification(
            service="Email Service",
            error=e,
            context=f"Failed to process new subscription for {email}"
        )
        
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Email sending failed. Please try again later.",
            "email": email
        }), 429

@email_subscription_bp.route('/confirm', methods=['GET'])
def confirm():
    """Confirm user's email address - simplified without database"""
    code = request.args.get('code')
    if not code:
        return jsonify({
            "success": False,
            "error": "Invalid request",
            "message": "Confirmation code is required"
        }), 400

    # For now, without database, we just accept any confirmation code
    # You can implement proper validation later when you add your database back
    
    # Send confirmation success notification to Discord
    discord_notifier.send_embed(
        title="✅ Email Confirmation Successful",
        description="A user has successfully confirmed their email subscription",
        color=0x00ff00,  # Green
        fields=[
            {"name": "Status", "value": "Confirmed ✅", "inline": True},
            {"name": "Confirmation Code", "value": code[:8] + "...", "inline": True}
        ],
        footer={"text": "SAY Website Backend • Email Service"}
    )
    
    return jsonify({
        "success": True,
        "message": "Email confirmed successfully",
        "status": "confirmed"
    }), 200

# Testing commands:
# Subscribe: curl -X POST -H "Content-Type: application/json" -d '{"email": "damien@alphagame.dev"}' http://localhost:8000/api/subscribe
# Form Submit: curl -X POST -d "email=damien@alphagame.dev" http://localhost:8000/api/subscribe
# Confirm: curl http://localhost:8000/api/confirm?code=CONFIRMATION_CODE_HERE

# Note: This module now has NO database dependencies! 
# All email subscription logic works without any database
# You can add your database layer back when you're ready