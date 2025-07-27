# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

from flask import Flask, jsonify, request
from flask_cors import CORS
import atexit
import logging
from os import getenv
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
from .config import Config
from .database import db, init_db

app = Flask(__name__)
app.config.from_object(Config)
app.debug = app.debug or (getenv("FLASK_DEBUG", False) != False or getenv("FLASK_ENV", False) == "development")

# Initialize database
init_db(app)

CORS(app, resources = {
    "/*": {
        "origins": "*" # TODO: Change this to the specific origin in production
    }
})

app.register_blueprint(email_subscription_bp, url_prefix='/api')

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

@app.route("/api/health")
@app.route("/api/healthcheck")
@app.route("/health")
@app.route("/healthcheck")
def health():
    """Comprehensive health check for all system components"""
    from datetime import datetime
    from .models.email import EmailSubscriber, EmailRateLimit
    import os
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {},
        "version": "1.0.0",
        "environment": "development" if app.debug else "production"
    }
    
    overall_healthy = True
    
    # Database connectivity check
    try:
        # Test database connection by doing a simple query
        subscriber_count = EmailSubscriber.query.count()
        rate_limit_count = EmailRateLimit.query.count()
        
        health_status["checks"]["database"] = {
            "status": "healthy",
            "message": "Database connection successful",
            "details": {
                "subscribers_count": subscriber_count,
                "rate_limits_count": rate_limit_count,
                "database_url": app.config.get('SQLALCHEMY_DATABASE_URI', '').split('://')[0] + "://***"
            }
        }
    except Exception as e:
        overall_healthy = False
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}",
            "details": {}
        }
    
    # Email configuration check
    try:
        smtp_password = os.getenv("GOOGLE_APP_PASSWORD")
        email_address = os.getenv("EMAIL", "stanthonyyouth.noreply@gmail.com")
        
        if smtp_password:
            health_status["checks"]["email_config"] = {
                "status": "healthy",
                "message": "Email configuration present",
                "details": {
                    "smtp_configured": True,
                    "email_address": email_address,
                    "actually_send_email": not os.getenv("NO_EMAIL")
                }
            }
        else:
            health_status["checks"]["email_config"] = {
                "status": "warning",
                "message": "SMTP password not configured",
                "details": {
                    "smtp_configured": False,
                    "email_address": email_address,
                    "actually_send_email": False
                }
            }
    except Exception as e:
        health_status["checks"]["email_config"] = {
            "status": "unhealthy",
            "message": f"Email configuration check failed: {str(e)}",
            "details": {}
        }
    
    # Environment variables check
    try:
        required_vars = ["DATABASE_URL", "EMAIL"]
        optional_vars = ["GOOGLE_APP_PASSWORD", "NO_EMAIL", "EMAIL_RATE_LIMIT_PER_DAY"]
        
        env_status = {}
        missing_required = []
        
        for var in required_vars:
            if os.getenv(var):
                env_status[var] = "present"
            else:
                env_status[var] = "missing"
                missing_required.append(var)
        
        for var in optional_vars:
            env_status[var] = "present" if os.getenv(var) else "missing"
        
        if missing_required:
            health_status["checks"]["environment"] = {
                "status": "warning",
                "message": f"Missing required environment variables: {', '.join(missing_required)}",
                "details": env_status
            }
        else:
            health_status["checks"]["environment"] = {
                "status": "healthy",
                "message": "All required environment variables present",
                "details": env_status
            }
    except Exception as e:
        health_status["checks"]["environment"] = {
            "status": "unhealthy",
            "message": f"Environment check failed: {str(e)}",
            "details": {}
        }
    
    # Application configuration check
    try:
        config_status = {
            "debug_mode": app.debug,
            "testing": app.testing,
            "rate_limit_per_day": app.config.get('EMAIL_RATE_LIMIT_PER_DAY', 2),
            "secret_key_configured": bool(app.secret_key),
            "sqlalchemy_track_modifications": app.config.get('SQLALCHEMY_TRACK_MODIFICATIONS', True)
        }
        
        health_status["checks"]["application"] = {
            "status": "healthy",
            "message": "Application configuration loaded",
            "details": config_status
        }
    except Exception as e:
        overall_healthy = False
        health_status["checks"]["application"] = {
            "status": "unhealthy",
            "message": f"Application configuration check failed: {str(e)}",
            "details": {}
        }
    
    # API endpoints check
    try:
        from flask import url_for
        endpoints = []
        for rule in app.url_map.iter_rules():
            if rule.endpoint != 'static':
                methods = rule.methods or set()
                filtered_methods = list(methods - {'HEAD', 'OPTIONS'}) if methods else []
                endpoints.append({
                    "endpoint": rule.endpoint,
                    "methods": filtered_methods,
                    "rule": str(rule)
                })
        
        health_status["checks"]["api_endpoints"] = {
            "status": "healthy",
            "message": f"Found {len(endpoints)} API endpoints",
            "details": {
                "endpoint_count": len(endpoints),
                "endpoints": endpoints[:10]  # Limit to first 10 for brevity
            }
        }
    except Exception as e:
        health_status["checks"]["api_endpoints"] = {
            "status": "unhealthy",
            "message": f"API endpoints check failed: {str(e)}",
            "details": {}
        }
    
    # Set overall status
    unhealthy_checks = [check for check in health_status["checks"].values() if check["status"] == "unhealthy"]
    warning_checks = [check for check in health_status["checks"].values() if check["status"] == "warning"]
    
    if unhealthy_checks:
        health_status["status"] = "unhealthy"
        status_code = 503
    elif warning_checks:
        health_status["status"] = "degraded"
        status_code = 200
    else:
        health_status["status"] = "healthy"
        status_code = 200
    
    health_status["summary"] = {
        "total_checks": len(health_status["checks"]),
        "healthy_checks": len([c for c in health_status["checks"].values() if c["status"] == "healthy"]),
        "warning_checks": len(warning_checks),
        "unhealthy_checks": len(unhealthy_checks)
    }
    
    return jsonify(health_status), status_code

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
