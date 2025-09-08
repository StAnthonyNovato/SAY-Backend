# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

import logging
from os import getenv, getpid
from flask import request

class MultiLineFormatter(logging.Formatter):
    """Custom logging formatter that handles multi-line messages.
    
    Made as a response to how Flask logs multi-line messages, AND IT IS SO FREAKING ANNOYING.
    This formatter ensures that each line of a multi-line log message is formatted correctly,
    preserving the original message structure while applying the desired format.
    """
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

class GunicornWorkerFilter(logging.Filter):
    """Filter to add the Gunicorn worker ID to log records."""
    
    def filter(self, record):
        # Add the worker ID to the log record
        worker_id = getenv("GUNICORN_WORKER_ID", "unknown")

        if worker_id != "unknown":
            record.worker_id = "worker" + worker_id
        else:
            record.worker_id = f"PID {getpid()}"
        return True
    
class NoDockerHealthcheckFilter(logging.Filter):
    """Filter to exclude health check requests from logs."""
    
    def filter(self, record):
        # Exclude health check requests from logs
        if request.args.get("reason", None) == "DockerAutomatedHealthcheck" and "health" in request.path:
            return False
        return True