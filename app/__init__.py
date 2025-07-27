# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

from flask import Flask, jsonify, request
from flask_cors import CORS
import atexit
import logging
from os import getenv
from .version import __version__
from datetime import datetime



class MultiLineFormatter(logging.Formatter):
    def format(self, record):
        # Format the first line using the parent formatter
        message = super().format(record)
        
        # If message contains newlines, handle each line separately
        if "\n" in record.getMessage():
            # Get the formatted first line to extract the prefix
            first_line = message.split('\n')[0]
            # Extract the prefix from the first line (everything before the actual message)
            prefix = first_line[:first_line.find(record.getMessage())]
            
            # Format each line with the proper prefix
            lines = []
            for line in record.getMessage().splitlines():
                # Create a new record with this line as the message
                new_record = logging.LogRecord(
                    record.name, record.levelno, record.pathname, 
                    record.lineno, line, record.args, record.exc_info,
                    func=record.funcName
                )
                # Format it with the parent formatter
                formatted_line = super().format(new_record)
                lines.append(formatted_line)
                
            return "\n".join(lines)
        return message

# Configure logging
level = (logging.DEBUG if getenv("FLASK_ENV") == "development" else logging.INFO)

formatter = MultiLineFormatter('%(asctime)-21s %(levelname)-8s %(name)-12s | %(message)s', datefmt="%Y-%m-%d %H:%M:%S")
handler = logging.StreamHandler()
handler.setFormatter(formatter)

logging.basicConfig(level=level, handlers=[handler])
logger = logging.getLogger("app")

# get a list of all initialized loggers
all_loggers = [logging.getLogger(lgr) for lgr in logging.root.manager.loggerDict.keys() if lgr.startswith("app")]
for logger in all_loggers:
    logger.setLevel(level)

from .bp.email_subscription import email_subscription_bp
from .discord import discord_notifier
from .bp.healthcheck import bp_healthcheck

app = Flask(__name__)
app.debug = app.debug or (getenv("FLASK_DEBUG", False) != False or getenv("FLASK_ENV", False) == "development")


CORS(app, resources = {
    "/*": {
        "origins": "*" # TODO: Change this to the specific origin in production
    }
})

app.register_blueprint(email_subscription_bp, url_prefix='/api')
app.register_blueprint(bp_healthcheck, url_prefix='/')
logger.info("SAY Website Backend version %s starting up", __version__)
# Send startup notification
if not app.debug and getenv("FLASK_ENV") != "development":
    discord_notifier.send_startup_notification("SAY Website Backend")

if getenv("NO_EMAIL"):
    logger.warning("Email functionality is disabled due to NO_EMAIL environment variable being set.")
else:
    logger.info("Email function is enabled.")
    if not getenv("GOOGLE_APP_PASSWORD"):
        logger.warning("* GOOGLE_APP_PASSWORD is not set.")

@app.before_request
def before_request():
    """Log incoming requests for diagnostic purposes."""

    # Do we have the X-Forwarded-For header?
    usingForwardedFor = False
    if 'X-Forwarded-For' in request.headers:
        # Use the first IP in the list (the original client IP)
        request.remote_addr = request.headers['X-Forwarded-For'].split(',')[0].strip()
        usingForwardedFor = True
    else:
        # Use the direct remote address
        request.remote_addr = request.remote_addr or "Unknown"

    warningDirectHit = "*(Warning: Direct hit to the server, or `X-Forwarded-For` header missing!)*" if not usingForwardedFor else ""
    if not app.debug:
        discord_notifier.send_plaintext(
            message = f"**[Request]** {request.method} {request.path} from {request.remote_addr} {warningDirectHit}",
            username = "Request Logger Subsystem",
        )

@app.errorhandler(500)
def handle_internal_error(error):
    """Handle internal server errors and send Discord notification."""
    logger.error(f"Internal server error: {error}")
    
    # Send error notification to Discord
    discord_notifier.send_diagnostic(
        level="error",
        service="Flask Application", 
        message="Internal server error occurred",
        details={
            "Error": str(error),
            "Endpoint": request.path if request else "Unknown",
            "Method": request.method if request else "Unknown",
            "User Agent": request.headers.get('User-Agent', 'Unknown') if request else "Unknown"
        }
    )
    
    return "An internal server error occurred. Please try again later.", 500

@app.errorhandler(404)
def handle_not_found(error):
    """Handle 404 errors."""
    logger.warning(f"404 error: {request.path} not found")
    return jsonify({"error": "Endpoint not found"}), 404

@app.route('/')
def index():
    """Health check endpoint."""
    return "All systems operational. API is running."

# Register shutdown handler to gracefully close Discord notification system
@atexit.register
def shutdown_handler():
    """Gracefully shutdown the Discord notification system."""
    logger.info("Application shutting down, closing Discord notification system")
    discord_notifier.shutdown()
