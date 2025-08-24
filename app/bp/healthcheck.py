# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

from flask import Blueprint, current_app, jsonify, g, request, make_response
from datetime import datetime, timedelta
from ..version import __version__
from typing import Dict, Any
import os

bp_healthcheck = Blueprint('healthcheck', __name__)

# In-memory cache for healthcheck
# If we were to scale this, we would use a more robust caching solution like Redis or Memcached
# ... but we're not. ;)
_healthcheck_cache: Dict[str, Any] = {
    "response": None,
    "timestamp": None,
    "status_code": None
}

class Healthcheck:
    def __init__(self, app, g, os_env):
        self.app = app
        self.g = g
        self.os_env = os_env
        self.status = "healthy"
        self.overall_healthy = True
        self.result = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "version": __version__,
            "checks": {},
            "environment": "development" if app.debug else "production"
        }

    def run(self):
        self.check_database()
        self.check_email()
        self.check_discord()
        self.check_environment()
        self.result["status"] = "healthy" if self.overall_healthy else "unhealthy"
        return self.result, self.overall_healthy

    def check_database(self):
        self.result["checks"]["database"] = {
            "status": "unset",
            "message": "Message not set",
            "details": {}
        }
        
        # Get connection pool from app context instead of relying on g.cnx
        # which is intentionally skipped for health check routes
        try:
            # Access the connection pool from the app module globals
            from .. import cnx_pool
            
            # Get a connection from the pool to test it
            test_cnx = cnx_pool.get_connection()
            try:
                test_cnx.ping(reconnect=True, attempts=3, delay=1)
                self.result["checks"]["database"]["status"] = "healthy"
                self.result["checks"]["database"]["message"] = "MySQL connection is healthy"
            except Exception as e:
                self.result["checks"]["database"]["status"] = "unhealthy"
                self.result["checks"]["database"]["message"] = f"MySQL connection failed: {str(e)}"
                self.overall_healthy = False
            finally:
                # Always return connection to pool
                test_cnx.close()
                
        except ImportError:
            self.result["checks"]["database"]["status"] = "unhealthy"
            self.result["checks"]["database"]["message"] = "MySQL connection pool not available (import failed)"
            self.overall_healthy = False
        except Exception as e:
            self.result["checks"]["database"]["status"] = "unhealthy"
            self.result["checks"]["database"]["message"] = f"Failed to get database connection: {str(e)}"
            self.overall_healthy = False

    def check_email(self):
        try:
            smtp_password = self.os_env.get("GOOGLE_APP_PASSWORD")
            email_configured = bool(smtp_password)
            self.result["checks"]["email"] = {
                "status": "healthy" if email_configured else "degraded",
                "message": "Email service configured" if email_configured else "Email service not fully configured",
                "details": {
                    "smtp_configured": email_configured,
                    "from_email": self.os_env.get("EMAIL", "not_set"),
                    "email_sending_enabled": not bool(self.os_env.get("NO_EMAIL"))
                }
            }
            if not email_configured:
                self.overall_healthy = False
        except Exception as e:
            self.overall_healthy = False
            self.result["checks"]["email"] = {
                "status": "unhealthy",
                "message": f"Email service check failed: {str(e)}",
                "details": {}
            }

    def check_discord(self):
        try:
            discord_webhook = self.os_env.get("DISCORD_WEBHOOK_URL")
            discord_configured = bool(discord_webhook)
            self.result["checks"]["discord"] = {
                "status": "healthy" if discord_configured else "degraded",
                "message": "Discord notifications configured" if discord_configured else "Discord notifications not configured",
                "details": {
                    "webhook_configured": discord_configured
                }
            }
        except Exception as e:
            self.result["checks"]["discord"] = {
                "status": "degraded",
                "message": f"Discord check failed: {str(e)}",
                "details": {}
            }

    def check_environment(self):
        try:
            required_vars = ["SMTP_FROM_EMAIL", "GOOGLE_APP_PASSWORD"]
            optional_vars = ["GOOGLE_APP_PASSWORD", "DISCORD_WEBHOOK_URL"]
            missing_required = [var for var in required_vars if not self.os_env.get(var)]
            missing_optional = [var for var in optional_vars if not self.os_env.get(var)]
            env_status = "healthy"
            if missing_required:
                env_status = "unhealthy"
                self.overall_healthy = False
            elif missing_optional:
                env_status = "degraded"
            self.result["checks"]["environment"] = {
                "status": env_status,
                "message": "Environment variables configured properly" if env_status == "healthy" else "Some environment variables missing",
                "details": {
                    "missing_required": missing_required,
                    "missing_optional": missing_optional,
                    "all_required_present": len(missing_required) == 0
                }
            }
        except Exception as e:
            self.overall_healthy = False
            self.result["checks"]["environment"] = {
                "status": "unhealthy",
                "message": f"Environment check failed: {str(e)}",
                "details": {}
            }

@bp_healthcheck.route("/api/health")
@bp_healthcheck.route("/api/healthcheck")
@bp_healthcheck.route("/health")
@bp_healthcheck.route("/healthcheck")
def health():
    """Comprehensive health check for all system components - simplified without database"""

    # Check for cache usage
    use_cache = request.args.get("c") == "1"
    now = datetime.utcnow()
    cache_valid = (
        _healthcheck_cache["response"] is not None and
        _healthcheck_cache["timestamp"] is not None and
        (now - _healthcheck_cache["timestamp"]) < timedelta(minutes=1)
    )

    if use_cache and cache_valid:
        resp = make_response(jsonify(_healthcheck_cache["response"]), _healthcheck_cache["status_code"])
        resp.headers["X-Cache"] = "HIT"
        return resp

    # Run healthcheck logic
    hc = Healthcheck(current_app, g, os.environ)
    health_status, overall_healthy = hc.run()

    status_code = 200 if overall_healthy else 503

    # Update cache
    _healthcheck_cache["response"] = health_status
    _healthcheck_cache["timestamp"] = now
    _healthcheck_cache["status_code"] = status_code

    resp = make_response(jsonify(health_status), status_code)
    resp.headers["X-Cache"] = " `"
    return resp