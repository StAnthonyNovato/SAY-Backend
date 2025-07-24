# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

from flask import Flask, jsonify, request
from flask_cors import CORS
from .config import Config
from .database import db, init_db
import atexit
import logging
from datetime import datetime
from .bp.email_subscription import email_subscription_bp
from .discord import discord_notifier

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
init_db(app)

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
