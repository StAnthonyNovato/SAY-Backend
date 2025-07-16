# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

from flask import Blueprint, request, current_app, jsonify
from os import getenv, path
from json import load, dump
from uuid import uuid4
from datetime import datetime, date
from ..mail.emailmanager import SMTPManager

email_subscription_bp = Blueprint('email_subscription', __name__)

ACTUALLY_SEND_EMAIL = not getenv("NO_EMAIL") # If NO_EMAIL is set, emails will not be sent

if not path.isfile("email-subscribers.json"):
    with open("email-subscribers.json", "w") as file:
        file.write("[]")
        # schema: [email:str, confirmed:bool, confirmation_code:str]

if not path.isfile("email-rate-limit.json"):
    with open("email-rate-limit.json", "w") as file:
        file.write("{}")
        # schema: {email: [timestamp1, timestamp2, ...]}

with open("email-subscribers.json", "r") as file:
    SUBSCRIBERS_DATA = load(file)

with open("email-rate-limit.json", "r") as file:
    EMAIL_RATE_LIMIT = load(file)

# SMTP configuration
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_PASSWORD = getenv("GOOGLE_APP_PASSWORD")


with open("email_templates/NEW_SUBSCRIBER_CONFIRMATION.txt", "r") as file:
    NEW_SUBSCRIBER_CONFIRMATION_TEMPLATE = file.read()

def can_send_email(email: str) -> bool:
    """Check if user can send email (max 2 per day)"""
    today = date.today().isoformat()
    
    if email not in EMAIL_RATE_LIMIT:
        EMAIL_RATE_LIMIT[email] = []
    
    # Clean up old entries (keep only today's entries)
    EMAIL_RATE_LIMIT[email] = [
        timestamp for timestamp in EMAIL_RATE_LIMIT[email] 
        if timestamp.startswith(today)
    ]
    
    return (len(EMAIL_RATE_LIMIT[email]) < 2) or current_app.debug # Allow debug mode to send more emails w/o rate limiting

def record_email_sent(email: str):
    """Record that an email was sent to this address"""
    if email not in EMAIL_RATE_LIMIT:
        EMAIL_RATE_LIMIT[email] = []
    
    EMAIL_RATE_LIMIT[email].append(datetime.now().isoformat())
    
    with open("email-rate-limit.json", "w") as file:
        dump(EMAIL_RATE_LIMIT, file)

def send_confirmation_email(email: str, user: dict):
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

        subject = f"St. Anthony Youth Newsletter - {user['email']}"
        
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
                confirmation_link=f"{DOMAIN}/api/confirm?code={user['confirmation_code']}",
                support_email=getenv("EMAIL", "damien@alphagame.dev")
            )
        
        record_email_sent(email)
        
    except Exception as e:
        print(f"Error sending email: {e}")
        raise

@email_subscription_bp.route('/subscribe', methods=['POST'])
def subscribe():
    global SUBSCRIBERS_DATA

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
    for existing_user in reversed(SUBSCRIBERS_DATA): # Reversed because we want to check the most recent entries first
        if existing_user['email'] == email:
            if existing_user['confirmed']:
                return jsonify({
                    "success": False,
                    "error": "Already subscribed",
                    "message": "Email already subscribed and confirmed",
                    "email": email
                }), 409
            else:
                # Email exists but not confirmed, resend confirmation
                try:
                    send_confirmation_email(email, existing_user)
                    return jsonify({
                        "success": True,
                        "message": "Confirmation email resent",
                        "email": email,
                        "action": "resent"
                    }), 200
                except Exception as e:
                    return jsonify({
                        "success": False,
                        "error": "Email sending failed",
                        "message": str(e),
                        "email": email
                    }), 429

    user = {
        "email": email,
        "confirmed": False,
        "confirmation_code": str(uuid4())
    }

    SUBSCRIBERS_DATA.append(user)

    with open("email-subscribers.json", "w") as file:
        dump(SUBSCRIBERS_DATA, file)

    # Send confirmation email to new subscriber
    try:
        send_confirmation_email(email, user)
        return jsonify({
            "success": True,
            "message": "Subscription successful - confirmation email sent",
            "email": email,
            "action": "subscribed"
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Email sending failed",
            "message": str(e),
            "email": email
        }), 429

@email_subscription_bp.route('/confirm', methods=['GET'])
def confirm():
    global SUBSCRIBERS_DATA

    # Logic for confirming a user's email address
    code = request.args.get('code')
    if not code:
        return jsonify({
            "success": False,
            "error": "Invalid request",
            "message": "Confirmation code is required"
        }), 400

    for user in SUBSCRIBERS_DATA:
        if user['confirmation_code'] == code:
            if user["confirmed"]:
                return jsonify({
                    "success": True,
                    "message": "Email already confirmed",
                    "email": user["email"],
                    "status": "already_confirmed"
                }), 200
            user['confirmed'] = True
            with open("email-subscribers.json", "w") as file:
                dump(SUBSCRIBERS_DATA, file)
            return jsonify({
                "success": True,
                "message": "Email confirmed successfully",
                "email": user["email"],
                "status": "confirmed"
            }), 200

    return jsonify({
        "success": False,
        "error": "Invalid confirmation code",
        "message": "The confirmation code is invalid or expired"
    }), 404

# a good cURL command to send subscribe damien@alphagame.dev would be:
# curl -X POST -H "Content-Type: application/json" -d '{"email": "damien@alphagame.dev"}' http://localhost:8000/api/subscribe