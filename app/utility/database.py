# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

from flask import current_app
from mysql.connector.connection import MySQLConnection
import logging

def getConnection():
    """Get the MySQL connection from the Flask app context."""
    logger = logging.getLogger(__name__)

    if not hasattr(current_app, 'cnx'):
        logger.error("MySQL connection is not initialized.")
        raise RuntimeError("MySQL connection is not initialized.")
    
    # ping
    connection: MySQLConnection = current_app.cnx # pyright: ignore[reportAttributeAccessIssue]
    try:
        is_connected = connection.is_connected()
        connection.ping(reconnect=True, attempts=3, delay=1)
        connectionHadToReconnect = not (is_connected and connection.is_connected())
        logger.info(f"MySQL connection is healthy. {"(Reconnected)" if connectionHadToReconnect else ""}")
    except Exception as e:
        current_app.logger.error("Failed to ping MySQL connection: %s", e)
        raise
    return connection