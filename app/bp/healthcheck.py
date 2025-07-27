# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

from flask import Blueprint, current_app, jsonify
from datetime import datetime
from ..models.email import EmailSubscriber, EmailRateLimit
from ..version import __version__
import os

bp_healthcheck = Blueprint('healthcheck', __name__)
@bp_healthcheck.route("/api/health")
@bp_healthcheck.route("/api/healthcheck")
@bp_healthcheck.route("/health")
@bp_healthcheck.route("/healthcheck")
def health():
    """Comprehensive health check for all system components"""
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "checks": {},
        "version": __version__,
        "environment": "development" if current_app.debug else "production"
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
                "database_url": current_app.config.get('SQLALCHEMY_DATABASE_URI', '').split('://')[0] + "://***"
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
            "debug_mode": current_app.debug,
            "testing": current_app.testing,
            "rate_limit_per_day": current_app.config.get('EMAIL_RATE_LIMIT_PER_DAY', 2),
            "secret_key_configured": bool(current_app.secret_key),
            "sqlalchemy_track_modifications": current_app.config.get('SQLALCHEMY_TRACK_MODIFICATIONS', True)
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
        for rule in current_app.url_map.iter_rules():
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
