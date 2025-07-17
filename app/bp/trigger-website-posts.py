# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

from flask import Blueprint, request
from os import getenv
from requests import get
from json import loads
from app.models.post import Post

bp_trigger_website_posts = Blueprint('bp_trigger_website_posts', __name__)

posts_json_url = "http://127.0.0.1:4000/assets/data/posts.json"

@bp_trigger_website_posts.route("/trigger", methods=["POST"])
def trigger():
    """Protected API endpoint to read website posts from the main website, and proceed to send them as an email newsletter to all subscribers."""

    # Protected API endpoint - private API key
    # We want to check the Authorization header for a specific API key
    expected_api_key = getenv("API_KEY", None)
    assert expected_api_key is not None, "API key must be set in environment variables."
    api_key = request.headers.get("Authorization")

    if not api_key:
        return {"error": "API key is missing"}, 401
    if api_key != expected_api_key:
        return {"error": "Invalid API key"}, 403

    data = get(posts_json_url).json()
    if not data:
        return {"error": "No posts found"}, 404

    

    return {"status": "success"}