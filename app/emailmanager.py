# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

import smtplib
from os import getenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

class EmailHeaders:
    def __init__(self, headers: dict):
        self.headers = headers
        
class SMTPManager:
    def __init__(self, smtp_server: str,
                 smtp_port: int,
                 smtp_password: str,
                 smtp_from_email: str = getenv("SMTP_FROM_EMAIL", "stanthonyyouth.noreply@gmail.com")):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_from_email = smtp_from_email
        self.smtp_password = smtp_password
        self.smtp_connection = None

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

    def connect(self):
        """Establish connection to SMTP server"""
        try:
            self.smtp_connection = smtplib.SMTP(self.smtp_server, self.smtp_port)
            self.smtp_connection.starttls()
            self.smtp_connection.login(self.smtp_from_email, self.smtp_password)
            return True
        except Exception as e:
            print(f"Error connecting to SMTP server: {e}")
            return False

    def send_email(self, to_email: str, subject: str, message: str, html_content: Optional[str] = None):
        """Send email with optional HTML content"""
        if not self.smtp_connection:
            if not self.connect():
                raise Exception("Failed to establish SMTP connection")

        try:
            if html_content:
                # Create multipart message
                msg = MIMEMultipart('alternative')
                msg['From'] = self.smtp_from_email
                msg['To'] = to_email
                msg['Subject'] = subject
                
                # Add text and HTML parts
                text_part = MIMEText(message, 'plain')
                html_part = MIMEText(html_content, 'html')
                
                msg.attach(text_part)
                msg.attach(html_part)
                
                if self.smtp_connection:
                    self.smtp_connection.send_message(msg)
            else:
                # Simple text email
                msg = MIMEText(message)
                msg['From'] = self.smtp_from_email
                msg['To'] = to_email
                msg['Subject'] = subject
                
                if self.smtp_connection:
                    self.smtp_connection.send_message(msg)
                
        except Exception as e:
            print(f"Error sending email: {e}")
            raise

    def send_template_email(self, to_email: str, subject: str, template_content: str, **template_vars):
        """Send email using a template with variable substitution"""
        formatted_content = template_content.format(**template_vars)
        self.send_email(to_email, subject, formatted_content)

    @staticmethod
    def create_manager_from_env():
        """Create SMTPManager instance using environment variables"""
        return SMTPManager(
            smtp_server=getenv("SMTP_SERVER", "smtp.gmail.com"),
            smtp_port=int(getenv("SMTP_PORT", "587")),
            smtp_password=getenv("GOOGLE_APP_PASSWORD", ""),
            smtp_from_email=getenv("EMAIL", "stanthonyyouth.noreply@gmail.com")
        )

    def is_connected(self):
        """Check if SMTP connection is active"""
        return self.smtp_connection is not None

    def close(self):
        """Close SMTP connection"""
        if self.smtp_connection:
            self.smtp_connection.quit()
            self.smtp_connection = None

    