# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

from flask import Blueprint, request, current_app
from smtplib import SMTP, SMTPException
from os import getenv, path
from json import load, dump
from uuid import uuid4

email_subscription_bp = Blueprint('email_subscription', __name__)

if not path.isfile("email-subscribers.json"):
    with open("email-subscribers.json", "w") as file:
        file.write("[]")
        # schema: [email:str, confirmed:bool, confirmation_code:str]

with open("email-subscribers.json", "r") as file:
    SUBSCRIBERS_DATA = load(file)

# SMTP configuration
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_PASSWORD = getenv("GOOGLE_APP_PASSWORD")



def send_confirmation_email(email: str, user: dict):
    try:
        with SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.starttls()
            assert SMTP_PASSWORD, "SMTP_PASSWORD must be set in the environment variables"
            DOMAIN = (
                "http://localhost:8000" if current_app.debug else "https://say-services.alphagame.dev"
            )

            smtp.login(getenv("EMAIL", "stanthonyyouth.noreply@gmail.com"), SMTP_PASSWORD)

            EMAIL_TEMPLATE = f"""
Hey!

Thanks for subscribing to the St. Anthony Youth Newsletter! We're so glad to have you onboard!

Yeah, we hate spam too, so we won't send you any spam. We will only send you emails when we have something important to say, like a new event or a new blog post.

Anyway, to confirm your subscription, please click the link below:
{DOMAIN}/api/confirm?code={user['confirmation_code']}

Thank you!
"""
            subject = f"St. Anthony Youth Newsletter - {user['email']}"
            message = f"From: {getenv('EMAIL', 'stanthonyyouth.noreply@gmail.com')}\nTo: {email}\nSubject: {subject}\n\n{EMAIL_TEMPLATE}"
            smtp.sendmail(getenv("EMAIL", "stanthonyyouth.noreply@gmail.com"), email, message)
    except SMTPException as e:
        print(f"Error sending email: {e}")

@email_subscription_bp.route('/subscribe', methods=['POST'])
def subscribe():
    global SUBSCRIBERS_DATA

    # Logic for subscribing a user to the email list
    json = request.get_json()
    if not json or 'email' not in json:
        return "Invalid request", 400
    email = json['email']

    # Check if email already exists
    for existing_user in reversed(SUBSCRIBERS_DATA): # Reversed because we want to check the most recent entries first
        if existing_user['email'] == email:
            if existing_user['confirmed']:
                return "Email already subscribed and confirmed", 409
            else:
                # Email exists but not confirmed, resend confirmation
                send_confirmation_email(email, existing_user)
                return "Confirmation email resent", 200

    user = {
        "email": email,
        "confirmed": False,
        "confirmation_code": str(uuid4())
    }

    SUBSCRIBERS_DATA.append(user)

    with open("email-subscribers.json", "w") as file:
        dump(SUBSCRIBERS_DATA, file)

    # TODO: add logic to send either a confirmation email or a welcome email
    send_confirmation_email(email, user)

    return "Subscription successful", 200

@email_subscription_bp.route('/confirm', methods=['GET'])
def confirm():
    global SUBSCRIBERS_DATA

    # Logic for confirming a user's email address
    code = request.args.get('code')
    if not code:
        return "Invalid request", 400

    for user in SUBSCRIBERS_DATA:
        if user['confirmation_code'] == code:
            if user["confirmed"]:
                return "Email already confirmed", 200
            user['confirmed'] = True
            with open("email-subscribers.json", "w") as file:
                dump(SUBSCRIBERS_DATA, file)
            return "Email confirmed successfully", 200

    return "Invalid confirmation code", 404

# a good cURL command to send subscribe damien@alphagame.dev would be:
# curl -X POST -H "Content-Type: application/json" -d '{"email": "damien@alphagame.dev"}' http://localhost:8000/api/subscribe