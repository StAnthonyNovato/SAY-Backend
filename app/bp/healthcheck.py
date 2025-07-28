# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

from flask import Blueprint, current_app, jsonify, g
from datetime import datetime
from ..version import __version__
import os

bp_healthcheck = Blueprint('healthcheck', __name__)

@bp_healthcheck.route("/api/health")
@bp_healthcheck.route("/api/healthcheck")
@bp_healthcheck.route("/health")
@bp_healthcheck.route("/healthcheck")
def health():
    """Comprehensive health check for all system components - simplified without database"""
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": __version__,
        "checks": {},
        "environment": "development" if current_app.debug else "production"
    }
    
    overall_healthy = True
    
    # Database connectivity check - simplified
    health_status["checks"]["database"] = {
        "status": "unset",
        "message": "Message not set",
        "details": {}
    }
    
    # MySQL connection check
    cnx = g.cnx if hasattr(g, 'cnx') else None
    if not cnx:
        health_status["checks"]["database"]["status"] = "unhealthy"
        health_status["checks"]["database"]["message"] = "MySQL connection not initialized"
        overall_healthy = False
    
    else:
        try:
            cnx.ping(reconnect=True, attempts=3, delay=1)
            health_status["checks"]["database"]["status"] = "healthy"
            health_status["checks"]["database"]["message"] = "MySQL connection is healthy"
        except Exception as e:
            health_status["checks"]["database"]["status"] = "unhealthy"
            health_status["checks"]["database"]["message"] = f"MySQL connection failed: {str(e)}"
            overall_healthy = False


    # Email service check
    try:
        smtp_password = os.getenv("GOOGLE_APP_PASSWORD")
        email_configured = bool(smtp_password)
        
        health_status["checks"]["email"] = {
            "status": "healthy" if email_configured else "degraded",
            "message": "Email service configured" if email_configured else "Email service not fully configured",
            "details": {
                "smtp_configured": email_configured,
                "from_email": os.getenv("EMAIL", "not_set"),
                "email_sending_enabled": not bool(os.getenv("NO_EMAIL"))
            }
        }
        
        if not email_configured:
            overall_healthy = False
            
    except Exception as e:
        overall_healthy = False
        health_status["checks"]["email"] = {
            "status": "unhealthy",
            "message": f"Email service check failed: {str(e)}",
            "details": {}
        }
    
    # Discord notifications check
    try:
        discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")
        discord_configured = bool(discord_webhook)
        
        health_status["checks"]["discord"] = {
            "status": "healthy" if discord_configured else "degraded",
            "message": "Discord notifications configured" if discord_configured else "Discord notifications not configured",
            "details": {
                "webhook_configured": discord_configured
            }
        }
        
    except Exception as e:
        health_status["checks"]["discord"] = {
            "status": "degraded",
            "message": f"Discord check failed: {str(e)}",
            "details": {}
        }
    
    # Environment variables check
    try:
        required_vars = ["SMTP_FROM_EMAIL", "GOOGLE_APP_PASSWORD"]
        optional_vars = ["GOOGLE_APP_PASSWORD", "DISCORD_WEBHOOK_URL"]
        
        missing_required = [var for var in required_vars if not os.getenv(var)]
        missing_optional = [var for var in optional_vars if not os.getenv(var)]
        
        env_status = "healthy"
        if missing_required:
            env_status = "unhealthy"
            overall_healthy = False
        elif missing_optional:
            env_status = "degraded"
        
        health_status["checks"]["environment"] = {
            "status": env_status,
            "message": "Environment variables configured properly" if env_status == "healthy" else "Some environment variables missing",
            "details": {
                "missing_required": missing_required,
                "missing_optional": missing_optional,
                "all_required_present": len(missing_required) == 0
            }
        }
        
    except Exception as e:
        overall_healthy = False
        health_status["checks"]["environment"] = {
            "status": "unhealthy",
            "message": f"Environment check failed: {str(e)}",
            "details": {}
        }
    
    # Update overall status
    health_status["status"] = "healthy" if overall_healthy else "unhealthy"
    
    # Return appropriate HTTP status code
    status_code = 200 if overall_healthy else 503
    
    return jsonify(health_status), status_code

@bp_healthcheck.route("/api/status")
def status():
    """Simple status endpoint"""
    return jsonify({
        "status": "operational",
        "message": "SAY Website Backend is running",
        "version": __version__,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }), 200
