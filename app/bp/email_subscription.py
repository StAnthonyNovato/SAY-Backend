# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

from flask import Blueprint, request, current_app, jsonify
from os import getenv, path
from datetime import datetime, date
from sqlalchemy import and_
from ..database import db
from ..models.email import EmailSubscriber, EmailRateLimit
from ..mail.emailmanager import SMTPManager
from ..config import Config

email_subscription_bp = Blueprint('email_subscription', __name__)

ACTUALLY_SEND_EMAIL = not getenv("NO_EMAIL") # If NO_EMAIL is set, emails will not be sent

# SMTP configuration
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_PASSWORD = getenv("GOOGLE_APP_PASSWORD")

with open("email_templates/NEW_SUBSCRIBER_CONFIRMATION.txt", "r") as file:
    NEW_SUBSCRIBER_CONFIRMATION_TEMPLATE = file.read()

with open("email_templates/NEW_SUBSCRIBER_CONFIRMATION.html", "r") as file:
    NEW_SUBSCRIBER_CONFIRMATION_HTML_TEMPLATE = file.read()

def can_send_email(email: str) -> bool:
    """Check if user can send email (max 2 per day)"""
    today_start = datetime.combine(date.today(), datetime.min.time())
    tomorrow_start = datetime.combine(date.today().replace(day=date.today().day + 1) if date.today().day < 28 else date.today().replace(month=date.today().month + 1, day=1) if date.today().month < 12 else date.today().replace(year=date.today().year + 1, month=1, day=1), datetime.min.time())
    
    # Count emails sent today
    emails_today = EmailRateLimit.query.filter(
        EmailRateLimit.email == email  # type: ignore
    ).filter(
        EmailRateLimit.timestamp >= today_start  # type: ignore
    ).filter(
        EmailRateLimit.timestamp < tomorrow_start  # type: ignore
    ).count()
    
    return (emails_today < Config.EMAIL_RATE_LIMIT_PER_DAY) or current_app.debug

def record_email_sent(email: str):
    """Record that an email was sent to this address"""
    rate_limit_record = EmailRateLimit(email=email)
    db.session.add(rate_limit_record)
    db.session.commit()

def send_confirmation_email(email: str, subscriber: EmailSubscriber):
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

        subject = f"St. Anthony Youth Newsletter Confirmation - {subscriber.email}"
        
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
                confirmation_link=f"{DOMAIN}/api/confirm?code={subscriber.confirmation_code}",
                confirmation_code=subscriber.confirmation_code,
                support_email=getenv("EMAIL", "damien@alphagame.dev")
            )
        
        record_email_sent(email)
        
    except Exception as e:
        print(f"Error sending email: {e}")
        raise

@email_subscription_bp.route('/subscribe', methods=['POST'])
def subscribe():
    # Logic for subscribing a user to the email list
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
        return jsonify({
            "success": False,
            "error": "Rate limit exceeded",
            "message": "Daily email limit exceeded. Please try again tomorrow.",
            "email": email
        }), 429

    # Check if email already exists
    existing_subscriber = EmailSubscriber.query.filter_by(email=email).first()
    
    if existing_subscriber:
        if existing_subscriber.confirmed:
            return jsonify({
                "success": False,
                "error": "Already subscribed",
                "message": "Email already subscribed and confirmed. You're all good!",
                "email": email
            }), 409
        else:
            # Email exists but not confirmed, resend confirmation
            try:
                send_confirmation_email(email, existing_subscriber)
                return jsonify({
                    "success": True,
                    "message": "Confirmation email resent. Please check your inbox (or spam folder)",
                    "email": email,
                    "action": "resent"
                }), 200
            except Exception as e:
                return jsonify({
                    "success": False,
                    "error": str(e),
                    "message": "We've had a problem sending the confirmation email. Please try again later.",
                    "email": email
                }), 429

    # Create new subscriber
    subscriber = EmailSubscriber(email=email)
    
    try:
        db.session.add(subscriber)
        db.session.commit()
        
        # Send confirmation email to new subscriber
        send_confirmation_email(email, subscriber)
        
        return jsonify({
            "success": True,
            "message": "Subscription Successful. We've sent you a confirmation email. (You might need to check your spam folder)",
            "email": email,
            "action": "subscribed"
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Email sending failed. Please try again later.",
            "email": email
        }), 429

@email_subscription_bp.route('/confirm', methods=['GET'])
def confirm():
    # Logic for confirming a user's email address
    code = request.args.get('code')
    if not code:
        return jsonify({
            "success": False,
            "error": "Invalid request",
            "message": "Confirmation code is required"
        }), 400

    subscriber = EmailSubscriber.query.filter_by(confirmation_code=code).first()
    
    if not subscriber:
        return jsonify({
            "success": False,
            "error": "Invalid confirmation code",
            "message": "The confirmation code is invalid or expired"
        }), 404
    
    if subscriber.confirmed:
        return jsonify({
            "success": True,
            "message": "Email already confirmed",
            "email": subscriber.email,
            "status": "already_confirmed"
        }), 200
    
    # Confirm the subscriber
    subscriber.confirm()
    db.session.commit()
    
    return jsonify({
        "success": True,
        "message": "Email confirmed successfully",
        "email": subscriber.email,
        "status": "confirmed"
    }), 200

# a good cURL command to send subscribe damien@alphagame.dev would be:
# curl -X POST -H "Content-Type: application/json" -d '{"email": "damien@alphagame.dev"}' http://localhost:8000/api/subscribe
