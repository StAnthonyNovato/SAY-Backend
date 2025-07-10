# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

from flask import Flask
from flask_cors import CORS
from .bp.email_subscription import email_subscription_bp

app = Flask(__name__)
CORS(app, resources = {
    "/*": {
        "origins": "*" # TODO: Change this to the specific origin in production
    }
})

app.register_blueprint(email_subscription_bp, url_prefix='/api')

@app.route('/')
def index():
    return "All systems operational. API is running."
