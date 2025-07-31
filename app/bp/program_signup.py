# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

from flask import Blueprint, g, request

program_signup_bp = Blueprint("program_signup", __name__)

@program_signup_bp.route("/prgmSignup", methods=["POST"]) # pyright: ignore[reportArgumentType]
def programSignup():
    cursor = g.cursor
    if not cursor:
        # 503 Service Unavailable
        return "Error: Cannot access database.  Please try again later, or contact the administrator at damien@alphagame.dev.", 503
    
    form = request.form

    name = form.get("name")

    