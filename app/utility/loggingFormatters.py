# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

import logging

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
