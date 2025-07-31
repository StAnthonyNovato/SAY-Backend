# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

from flask import Blueprint, g, request
import os
import requests
from flask import redirect
from enum import Enum
from random import choice
# Add import for discord diagnostics
from app.discord import discord_notifier

program_signup_bp = Blueprint("program_signup", __name__)

class RegistrationState(Enum):
    SUCCESS = "success"
    DB_ERROR = "db_error"
    MISSING_FIELDS = "missing_fields"
    RECAPTCHA_FAIL = "recaptcha_fail"
    NO_DB = "no_db"

def makeHumanIdentifier():
    # two words, one adjective, one noun, separated by a dash
    adjectives = [
        "fluffy", "bouncy", "sneaky", "sparkly", "noisy", "sleepy", "zany", "wiggly",
        "fuzzy", "chirpy", "howly", "zoomy", "snuggly", "yappy", "quirky", "dizzy",
        "pouncy", "silly", "loopy", "peppy", "spooky", "cheery", "goofy", "sassy"
    ]
    nouns = [
        "otter", "fox", "wolf", "dragon", "bun", "panda", "ferret", "cat", "doggo",
        "raccoon", "badger", "lynx", "coyote", "husky", "gecko", "bat", "owl", "mouse",
        "shark", "tiger", "bear", "moose", "squirrel", "hedgehog", "sloth", "poodle"
    ]

    return f"{choice(adjectives)}-{choice(nouns)}"

def _parseFormElement(form, field_name, default=None, type_=str):
    """
    Helper function to parse form elements with a default value.
    """
    value = form.get(field_name, default)
    if value is None:
        return default
    if type_ is int:
        # Accept int or string that looks like an int
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return default
    return type_(value)

def redirect_with_state(state, human_id, noRecaptchaText=""):
    cursor = g.cursor
    if cursor:
        cursor.execute(
            "INSERT INTO registration_completions (humanid, status) VALUES (%s, %s)",
            (human_id, state)
        )
    referrer = request.referrer or "/"
    extraSlash = "" if referrer.endswith("/") else "/"
    redirect_url = f"{referrer}{extraSlash}registration/complete/?state={state}&id={human_id}"
    if noRecaptchaText:
        redirect_url += f"&noRecaptcha={noRecaptchaText}"
    return redirect(redirect_url)

@program_signup_bp.route("/prgmSignup", methods=["POST"]) # pyright: ignore[reportArgumentType]
def programSignup():
    cursor = g.cursor
    human_id = makeHumanIdentifier()
    if not cursor:
        # Discord diagnostic: No DB connection
        discord_notifier.send_diagnostic(
            level="error",
            service="program_signup",
            message="No database connection during registration attempt.",
            details={"human_id": human_id}
        )
        state = RegistrationState.NO_DB.value
        return redirect_with_state(state, human_id)
    
    form = request.form

    # reCAPTCHA verification if enabled
    recaptcha_secret = os.getenv("RECAPTCHA_SECRET_KEY")
    noRecaptchaText = ""
    if recaptcha_secret:
        recaptcha_response = form.get("g-recaptcha-response")
        print(recaptcha_response)
        if not recaptcha_response:
            # Discord diagnostic: Missing reCAPTCHA response
            discord_notifier.send_diagnostic(
                level="warning",
                service="program_signup",
                message="Missing reCAPTCHA response.",
                details={"human_id": human_id}
            )
            state = RegistrationState.RECAPTCHA_FAIL.value
            return redirect_with_state(state, human_id)
        verify_resp = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={
                "secret": recaptcha_secret,
                "response": recaptcha_response,
                "remoteip": request.remote_addr,
            },
            timeout=5,
        )
        verify_result = verify_resp.json()
        print(verify_result)
        if not verify_result.get("success"):
            # Discord diagnostic: reCAPTCHA failed
            discord_notifier.send_diagnostic(
                level="warning",
                service="program_signup",
                message="reCAPTCHA verification failed.",
                details={"human_id": human_id, "verify_result": verify_result}
            )
            state = RegistrationState.RECAPTCHA_FAIL.value
            return redirect_with_state(state, human_id)
    else:
        noRecaptchaText = "(reCAPTCHA verification is disabled; skipping verification.  If this is in a production environment, God help us.)"
        # Discord diagnostic: reCAPTCHA disabled
        discord_notifier.send_diagnostic(
            level="warning",
            service="program_signup",
            message="reCAPTCHA is disabled.",
            details={"human_id": human_id}
        )
    # Extract fields
    parent_fname = _parseFormElement(form, "parent_fname")
    parent_lname = _parseFormElement(form, "parent_lname")
    parent_phone = _parseFormElement(form, "parent_phone")
    parent_email = _parseFormElement(form, "parent_email")
    child_fname = _parseFormElement(form, "child_fname")
    child_lname = _parseFormElement(form, "child_lname")
    child_phone = _parseFormElement(form, "child_phone")
    child_email = _parseFormElement(form, "child_email")
    child_baptism = _parseFormElement(form, "child_baptism", default=0, type_=int) # pyright: ignore[reportArgumentType]
    child_baptism_date = _parseFormElement(form, "child_baptism_date")
    child_baptism_place = _parseFormElement(form, "child_baptism_place")
    child_first_comm = _parseFormElement(form, "child_first_comm", default=0, type_=int) # pyright: ignore[reportArgumentType]
    child_first_comm_date = _parseFormElement(form, "child_first_comm_date")
    child_first_comm_place = _parseFormElement(form, "child_first_comm_place")

    # Ensure *_date and *_place are NULL, and tinyint is 0 if unset or falsy
    if not child_baptism:
        child_baptism = 0
        child_baptism_date = None
        child_baptism_place = None
    if not child_first_comm:
        child_first_comm = 0
        child_first_comm_date = None
        child_first_comm_place = None

    # Validate required fields
    required_fields = [
        parent_fname, parent_lname, parent_phone, parent_email,
        child_fname, child_lname
    ]

    if any(f is None or f == "" for f in required_fields):
        # Discord diagnostic: Missing required fields
        discord_notifier.send_diagnostic(
            level="warning",
            service="program_signup",
            message="Missing required fields in registration.",
            details={"human_id": human_id}
        )
        state = RegistrationState.MISSING_FIELDS.value
        return redirect_with_state(state, human_id)

    # Insert into database
    try:
        cursor.execute(
            """
            INSERT INTO registrations (
                humanid,
                parent_fname, parent_lname, parent_phone, parent_email,
                child_fname, child_lname, child_phone, child_email,
                child_baptism, child_baptism_date, child_baptism_place,
                child_first_comm, child_first_comm_date, child_first_comm_place
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                human_id, parent_fname, parent_lname, parent_phone, parent_email,
                child_fname, child_lname, child_phone, child_email,
                child_baptism, child_baptism_date, child_baptism_place,
                child_first_comm, child_first_comm_date, child_first_comm_place
            )
        )
    except Exception as e:
        # Discord diagnostic: DB error
        discord_notifier.send_error_notification(
            service="program_signup",
            error=e,
            context=f"Failed to insert registration for human_id={human_id}"
        )
        state = RegistrationState.DB_ERROR.value
        return redirect_with_state(state, human_id, noRecaptchaText)

    # Success!
    # Discord diagnostic: Registration success
    discord_notifier.send_diagnostic(
        level="info",
        service="program_signup",
        message="Registration completed successfully.",
        details={"human_id": human_id}
    )
    state = RegistrationState.SUCCESS.value
    return redirect_with_state(state, human_id, noRecaptchaText)
