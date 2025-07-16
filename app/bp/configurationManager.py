# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

from enum import Enum
from os import getenv

class SMTPProvider(Enum):
    """Enum for supported SMTP providers"""
    GMAIL = "gmail"
    NONE = "none"

class SMTPAuthenticationManager:
    """Manager for SMTP authentication and sending emails"""
    smtp_server:     str | None  = None
    smtp_port:       int | None  = None
    smtp_password:   str | None  = None

    def __init__(self, smtp_provider: SMTPProvider):
        if smtp_provider == SMTPProvider.GMAIL:
            self.smtp_server = 'smtp.gmail.com'
            self.smtp_port = 587
            self.smtp_password = getenv("GOOGLE_APP_PASSWORD")
        else:
            raise ValueError(f"Unsupported SMTP provider: {smtp_provider}")
