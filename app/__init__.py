# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import atexit
import logging
import os

logger = logging.getLogger("app")

prometheus_multiproc_dir = os.getenv("PROMETHEUS_MULTIPROC_DIR", "/tmp/prometheus_multiproc_dir")
if not os.path.exists(prometheus_multiproc_dir):
    # Create the directory if it doesn't exist
    logger.info("Creating Prometheus multiprocess directory at %s", prometheus_multiproc_dir)
    os.mkdir(prometheus_multiproc_dir)

# delete contents of prometheus_multiproc_dir on startup
for filename in os.listdir(prometheus_multiproc_dir):
    file_path = os.path.join(prometheus_multiproc_dir, filename)
    try:
        if os.path.isfile(file_path) or os.path.islink(file_path):
            os.unlink(file_path)
            logger.debug(f"Deleted file: {file_path}")
        elif os.path.isdir(file_path):
            os.rmdir(file_path)
            logger.debug(f"Deleted directory: {file_path}")
    except Exception as e:
        logger.error(f"Failed to delete {file_path}. Reason: {e}")

from prometheus_client import multiprocess, CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
from mysql.connector.cursor import MySQLCursor
from mysql.connector import (
    connect,
    Error as MySQLError,
    InterfaceError,
    pooling,
    __version__ as mysql_version)
from prometheus_flask_exporter.multiprocess import GunicornPrometheusMetrics
from .config import MYSQL_CONNECTION_INFO
from .utility import MultiLineFormatter, GunicornWorkerFilter, apply_migrations
from .version import __version__
from datetime import datetime, timedelta
from flask import g
import faulthandler
import threading
import time

faulthandler.enable()
# Configure logging
level = (logging.DEBUG if os.getenv("FLASK_ENV") == "development" or os.getenv("DEBUG_LOGGING") != None else logging.INFO)

formatter = MultiLineFormatter(f'%(asctime)-21s %(levelname)-8s %(name)-12s | %(message)s', datefmt="%Y-%m-%d %H:%M:%S")
handler = logging.StreamHandler()
handler.setFormatter(formatter)
handler.addFilter(GunicornWorkerFilter())  # Add the Gunicorn worker ID filter
logging.basicConfig(level=level, handlers=[handler])
logger = logging.getLogger("app")
# Ensure all app loggers use the GunicornWorkerFilter and correct formatter
for lgr in logging.root.manager.loggerDict.keys():
    if lgr.startswith("app"):
        l = logging.getLogger(lgr)
        l.setLevel(level)
        l.propagate = False  # Prevent log propagation to ancestor loggers
        # Add filter if not already present
        if not any(isinstance(f, GunicornWorkerFilter) for f in getattr(l, 'filters', [])):
            l.addFilter(GunicornWorkerFilter())
        # Add handler if not already present
        if not any(isinstance(h, logging.StreamHandler) for h in getattr(l, 'handlers', [])):
            l.addHandler(handler)

from .bp.email_subscription import email_subscription_bp
from .discord import discord_notifier
from .bp.healthcheck import bp_healthcheck
from .bp.program_signup import program_signup_bp

app = Flask(__name__)
app.debug = app.debug or (os.getenv("FLASK_DEBUG", False) != False or os.getenv("FLASK_ENV", False) == "development")

prom_metrics = GunicornPrometheusMetrics(app, group_by='endpoint', path="/metrics", defaults_prefix="say_website_backend_")
prom_metrics.info('app', 'SAY Website Backend', version=__version__)

logger.info("Using MySQL Connector/Python version: %s", mysql_version)
logger.info("Connecting to MySQL database with config:")
logger.info(f"* Host: {MYSQL_CONNECTION_INFO['host']}")
logger.info(f"* Port: {MYSQL_CONNECTION_INFO['port']}")
logger.info(f"* Database: {MYSQL_CONNECTION_INFO['database']}")

# Create a connection pool instead of a single connection
pool_config = MYSQL_CONNECTION_INFO.copy()
pool_config.update({
    'pool_name': 'say_backend_pool',
    'pool_size': 20,  # Increased pool size for more concurrent connections
    'pool_reset_session': True,  # Reset session variables when connection is returned to pool
    'autocommit': False,  # We'll handle commits manually
    'connect_timeout': 10,  # Reduced timeout for faster failure
    'use_unicode': True,
    'charset': 'utf8mb4'
})

try:
    cnx_pool = pooling.MySQLConnectionPool(**pool_config)
    logger.info("Successfully created MySQL connection pool with %d connections", pool_config['pool_size'])
except Exception as e:
    logger.error(f"Failed to create MySQL connection pool: {e}")
    exit(1)

# Test the pool with a single connection to verify database schema
try:
    test_cnx = cnx_pool.get_connection()
    test_cur = test_cnx.cursor()
    test_cur.execute("SELECT VERSION()")
    result = test_cur.fetchone()
    db_version = result[0] if result and isinstance(result, tuple) else "Unknown"
    logger.info(f"MySQL database version: {db_version}")
    
    apply_migrations(test_cnx, migrations_dir="migrations")

    test_cur.close()
    test_cnx.close()
    
except Exception as e:
    logger.error(f"Failed to setup database connection: {e}")
    exit(1)

# Connection health check tracking
last_health_check = None
health_check_interval = timedelta(minutes=5)  # Only check health every 5 minutes
health_check_lock = threading.Lock()

@app.route("/metrics")
def metrics_route():
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    return Response(generate_latest(registry), mimetype=CONTENT_TYPE_LATEST)

@app.before_request
def add_contextual_cursor():
    """Get a connection from the pool and create a cursor for this request, unless static/healthcheck."""
    g.request_start_time = time.time()
    global last_health_check

    # Skip DB setup for static/healthcheck routes
    if request.endpoint in ('index', 'static') or request.path in ('/', '/health'):
        return

    # Timing start
    t0 = time.time()
    try:
        g.cnx = cnx_pool.get_connection()
        t1 = time.time()
        
        # Only do health checks periodically, not on every request
        current_time = datetime.now()
        should_check_health = False
        
        with health_check_lock:
            if last_health_check is None or (current_time - last_health_check) > health_check_interval:
                should_check_health = True
                last_health_check = current_time
        
        # Perform health check only if needed
        if should_check_health:
            try:
                g.cnx.ping(reconnect=True)
                logger.debug("Database health check passed")
            except Exception as ping_error:
                logger.warning(f"Database ping failed, but continuing with fresh connection: {ping_error}")
        
        # Use unbuffered cursor for faster creation unless buffering is needed
        g.cursor = g.cnx.cursor(buffered=False)
        t2 = time.time()
        logger.debug(f"DB connection acquired in {(t1-t0):.4f}s, cursor in {(t2-t1):.4f}s")
    except Exception as e:
        logger.error(f"Failed to get database connection from pool: {e}")
        g.cnx = None
        g.cursor = None

@app.route("/heartbeat", methods=["GET"])
def heartbeat():
    """Health check endpoint."""
    return jsonify({"status": "ok"}), 200

@app.teardown_request
def teardown_request(exception):
    """Close the database cursor and return connection to pool after each request."""
    cursor: MySQLCursor = g.pop('cursor', None)
    cnx = g.pop('cnx', None)
    
    if cursor is not None:
        try:
            cursor.close()
        except Exception as e:
            logger.warning(f"Error closing cursor: {e}")
    
    if cnx is not None:
        try:
            if exception is None:
                cnx.commit()  # Commit successful requests
            else:
                cnx.rollback()  # Rollback failed requests
                logger.warning(f"Rolling back transaction due to exception: {exception}")
        except Exception as e:
            logger.warning(f"Error handling transaction: {e}")
        finally:
            try:
                cnx.close()  # Return connection to pool
            except Exception as e:
                logger.warning(f"Error returning connection to pool: {e}")

@app.after_request
def log_request(response):
    """Log the request and response details."""
    status_code = response.status_code
    # Flask default request log format: method path status_code remote_addr user_agent
    # Include query parameters in the log if present
    query_string = f"?{request.query_string.decode()}" if request.query_string else ""
    logging.getLogger('app.request').info(
        '%s %s%s %s %s %s "%s"',
        request.method,
        request.path,
        query_string,
        status_code,
        request.remote_addr,
        # how long the request took
        f"{(time.time() - g.request_start_time):.2f}s",
        request.headers.get('User-Agent', 'Unknown')
    )
    
    return response

CORS(app, resources = {
    "/*": {
        "origins": "*" # TODO: Change this to the specific origin in production
    }
})

app.register_blueprint(email_subscription_bp, url_prefix='/api')
app.register_blueprint(bp_healthcheck, url_prefix='/')
app.register_blueprint(program_signup_bp, url_prefix="/api/registration")
logger.info("SAY Website Backend version %s starting up", __version__)
# Send startup notification
if not app.debug and os.getenv("FLASK_ENV") != "development":
    discord_notifier.send_startup_notification("SAY Website Backend")

if os.getenv("NO_EMAIL"):
    logger.warning("Email functionality is disabled due to NO_EMAIL environment variable being set.")
else:
    logger.info("Email function is enabled.")
    if not os.getenv("GOOGLE_APP_PASSWORD"):
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

    warningDirectHit = "\n-# (Warning: Direct hit to the server, or the `X-Forwarded-For` header is missing!)" if not usingForwardedFor else ""

    # fcnl = From Client Not Logged
    fcnl = not (request.args.get("fcnl") is None)
    if not app.debug and not fcnl and request.method != "OPTIONS":
        if request.path in ("/health", "/healthcheck", "/api/health", "/api/healthcheck", "/heartbeat", "/metrics"): return
        discord_notifier.send_plaintext(
            message = f"**[Request]** {request.method} {request.path} from {request.remote_addr} {warningDirectHit}",
            username = "Request Logger Subsystem",
        )



@app.errorhandler(500)
def handle_internal_error(error):
    """Handle internal server errors and send Discord notification."""
    import traceback
    
    # Get full traceback for debugging
    tb_str = traceback.format_exc()
    logger.error(f"Internal server error: {error}\nTraceback:\n{tb_str}")
    
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
    
    # In debug mode, return detailed error information including traceback
    if app.debug:
        return jsonify({
            "error": "Internal server error",
            "message": str(error),
            "traceback": tb_str,
            "endpoint": request.path if request else "Unknown",
            "method": request.method if request else "Unknown"
        }), 500
    else:
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

# Register shutdown handler to gracefully close Discord notification system and database pool
@atexit.register
def shutdown_handler():
    """Gracefully shutdown the Discord notification system and database connection pool."""
    logger.info("Application shutting down, closing Discord notification system")
    discord_notifier.shutdown()
    
    # Close the connection pool
    try:
        # Note: mysql.connector.pooling doesn't have a direct close_all method,
        # but connections will be closed when the pool object is garbage collected
        logger.info("Database connection pool will be closed on application exit")
    except Exception as e:
        logger.warning(f"Error during connection pool shutdown: {e}")
