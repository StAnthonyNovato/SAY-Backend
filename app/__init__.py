# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

from flask import Flask, jsonify, request
from flask_cors import CORS
import atexit
import logging
from datetime import datetime
from .bp.email_subscription import email_subscription_bp
from .discord import discord_notifier

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources = {
    "/*": {
        "origins": "*" # TODO: Change this to the specific origin in production
    }
})

app.register_blueprint(email_subscription_bp, url_prefix='/api')

# Send startup notification
discord_notifier.send_startup_notification("SAY Website Backend")

@app.before_request
def before_request():
    """Log incoming requests for diagnostic purposes."""
    logger.info(f"Incoming {request.method} request to {request.path} from {request.remote_addr}")

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

@app.route('/health')
def health_check():
    """Detailed health check endpoint."""
    discord_healthy = discord_notifier.is_healthy()
    queue_size = discord_notifier.get_queue_size()
    rate_limit_info = discord_notifier.get_rate_limit_info()
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "discord_notifications": {
                "status": "healthy" if discord_healthy else "unhealthy",
                "enabled": discord_notifier.enabled,
                "queue_size": queue_size,
                "rate_limits": rate_limit_info
            }
        }
    }
    
    return jsonify(health_status)

# Register shutdown handler to gracefully close Discord notification system
@atexit.register
def shutdown_handler():
    """Gracefully shutdown the Discord notification system."""
    logger.info("Application shutting down, closing Discord notification system")
    discord_notifier.shutdown()
