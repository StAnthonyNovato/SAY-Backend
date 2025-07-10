# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

# NOTE: Don't change this file. It's for the sole purpose of running the Flask app, defined in the
# app/* directory. (Specifically, app/__init__.py)

from app import app

app.run("0.0.0.0", 8000, debug=True)