# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

import smtplib
from os import getenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from logging import getLogger
from flask import g

class EmailHeaders:
    def __init__(self, headers: dict):
        self.headers = headers
        
class SMTPManager:
    def __init__(self, smtp_server: str,
                 smtp_port: int,
                 smtp_password: str,
                 smtp_from_email: str = getenv("SMTP_FROM_EMAIL", "stanthonyyouth.noreply@gmail.com"),
                 rate_limit_per_minute: int = 10,
                 rate_limit_per_hour: int = 100,
                 rate_limit_per_day: int = 500):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_from_email = smtp_from_email
        self.smtp_password = smtp_password
        self.smtp_connection = None
        
        # Rate limiting settings
        self.rate_limit_per_minute = rate_limit_per_minute
        self.rate_limit_per_hour = rate_limit_per_hour
        self.rate_limit_per_day = rate_limit_per_day
        
        # Track email send times
        self.email_history: List[datetime] = []
        self.per_email_history: Dict[str, List[datetime]] = {}

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

    def _cleanup_old_entries(self):
        """Remove old entries from email history to keep memory usage low"""
        now = datetime.now()
        cutoff_time = now - timedelta(days=1)
        
        # Clean global history
        self.email_history = [timestamp for timestamp in self.email_history if timestamp > cutoff_time]
        
        # Clean per-email history
        for email in list(self.per_email_history.keys()):
            self.per_email_history[email] = [
                timestamp for timestamp in self.per_email_history[email] 
                if timestamp > cutoff_time
            ]
            # Remove empty entries
            if not self.per_email_history[email]:
                del self.per_email_history[email]

    def _check_global_rate_limits(self) -> tuple[bool, str]:
        """Check if global rate limits are exceeded"""
        now = datetime.now()
        
        # Check minute limit
        minute_ago = now - timedelta(minutes=1)
        recent_minute = [t for t in self.email_history if t > minute_ago]
        if len(recent_minute) >= self.rate_limit_per_minute:
            return False, f"Rate limit exceeded: {len(recent_minute)} emails sent in the last minute (limit: {self.rate_limit_per_minute})"
        
        # Check hour limit
        hour_ago = now - timedelta(hours=1)
        recent_hour = [t for t in self.email_history if t > hour_ago]
        if len(recent_hour) >= self.rate_limit_per_hour:
            return False, f"Rate limit exceeded: {len(recent_hour)} emails sent in the last hour (limit: {self.rate_limit_per_hour})"
        
        # Check day limit
        day_ago = now - timedelta(days=1)
        recent_day = [t for t in self.email_history if t > day_ago]
        if len(recent_day) >= self.rate_limit_per_day:
            return False, f"Rate limit exceeded: {len(recent_day)} emails sent in the last day (limit: {self.rate_limit_per_day})"
        
        return True, ""

    def _check_per_email_rate_limits(self, email: str, max_per_day: int = 2) -> tuple[bool, str]:
        """Check if per-email rate limits are exceeded"""
        if email not in self.per_email_history:
            return True, ""
        
        now = datetime.now()
        day_ago = now - timedelta(days=1)
        recent_emails = [t for t in self.per_email_history[email] if t > day_ago]
        
        if len(recent_emails) >= max_per_day:
            return False, f"Rate limit exceeded for {email}: {len(recent_emails)} emails sent in the last day (limit: {max_per_day})"
        
        return True, ""

    def can_send_email(self, to_email: str, max_per_email_per_day: int = 2) -> tuple[bool, str]:
        """Check if an email can be sent without violating rate limits"""
        self._cleanup_old_entries()
        
        # Check global rate limits
        global_ok, global_msg = self._check_global_rate_limits()
        if not global_ok:
            return False, global_msg
        
        # Check per-email rate limits
        per_email_ok, per_email_msg = self._check_per_email_rate_limits(to_email, max_per_email_per_day)
        if not per_email_ok:
            return False, per_email_msg
        
        return True, ""

    def _record_email_sent(self, to_email: str):
        """Record that an email was sent for rate limiting purposes"""
        now = datetime.now()
        
        cursor = g.cursor
        # Record in global history
        self.email_history.append(now)
        
        # Record in per-email history
        if to_email not in self.per_email_history:
            self.per_email_history[to_email] = []
        self.per_email_history[to_email].append(now)

        cursor = g.cursor
        if not cursor: return

        cursor.execute((
            "INSERT INTO email_log (to_email, subject, body_text, body_html)"
            "VALUES (%s, %s, %s, %s)",
            
            
        ))

    def send_email(self, to_email: str, subject: str, message: str, html_content: Optional[str] = None, 
                   max_per_email_per_day: int = 2, bypass_rate_limit: bool = False):
        """Send email with optional HTML content and rate limiting"""
        
        # Check rate limits unless bypassed
        if not bypass_rate_limit:
            can_send, rate_limit_msg = self.can_send_email(to_email, max_per_email_per_day)
            if not can_send:
                raise Exception(f"Rate limit violation: {rate_limit_msg}")
        
        if not self.smtp_connection:
            if not self.connect():
                raise Exception("Failed to establish SMTP connection")
        try:
            h_From = f"St. Anthony Youth Mail Delivery Subsystem <{self.smtp_from_email}>"
            if html_content:
                getLogger(__name__).info("Sending HTML email")
                # Create multipart message
                msg = MIMEMultipart('alternative')
                msg['From'] = h_From
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
                getLogger(__name__).warning("Sending plain text email")
                # Simple text email
                msg = MIMEText(message)
                msg['From'] = h_From
                msg['To'] = to_email
                msg['Subject'] = subject
                
                if self.smtp_connection:
                    self.smtp_connection.send_message(msg)
            
            # Record the email send for rate limiting
            if not bypass_rate_limit:
                self._record_email_sent(to_email)
                
        except Exception as e:
            print(f"Error sending email: {e}")
            raise

    def send_template_email(self, to_email: str, subject: str, template_content: str, html_template_content: Optional[str] = None,
                           max_per_email_per_day: int = 2, bypass_rate_limit: bool = False, **template_vars):
        """Send email using a template with variable substitution and rate limiting"""
        formatted_content = template_content.format(**template_vars)
        formatted_html_content = html_template_content.format(**template_vars) if html_template_content else None
        if not html_template_content and not formatted_html_content: getLogger(__name__).warning("No HTML content provided, sending plain text email only")
        self.send_email(to_email, subject, formatted_content, 
                       html_content=formatted_html_content,
                       max_per_email_per_day=max_per_email_per_day, 
                       bypass_rate_limit=bypass_rate_limit)

    @staticmethod
    def create_manager_from_env():
        """Create SMTPManager instance using environment variables"""
        return SMTPManager(
            smtp_server=getenv("SMTP_SERVER", "smtp.gmail.com"),
            smtp_port=int(getenv("SMTP_PORT", "587")),
            smtp_password=getenv("GOOGLE_APP_PASSWORD", ""),
            smtp_from_email=getenv("EMAIL", "stanthonyyouth.noreply@gmail.com"),
            rate_limit_per_minute=int(getenv("SMTP_RATE_LIMIT_PER_MINUTE", "10")),
            rate_limit_per_hour=int(getenv("SMTP_RATE_LIMIT_PER_HOUR", "100")),
            rate_limit_per_day=int(getenv("SMTP_RATE_LIMIT_PER_DAY", "500"))
        )

    def is_connected(self):
        """Check if SMTP connection is active"""
        return self.smtp_connection is not None

    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limiting status and statistics"""
        self._cleanup_old_entries()
        now = datetime.now()
        
        # Count emails in different time periods
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        
        minute_count = len([t for t in self.email_history if t > minute_ago])
        hour_count = len([t for t in self.email_history if t > hour_ago])
        day_count = len([t for t in self.email_history if t > day_ago])
        
        return {
            "limits": {
                "per_minute": self.rate_limit_per_minute,
                "per_hour": self.rate_limit_per_hour,
                "per_day": self.rate_limit_per_day
            },
            "current_usage": {
                "last_minute": minute_count,
                "last_hour": hour_count,
                "last_day": day_count
            },
            "remaining": {
                "this_minute": max(0, self.rate_limit_per_minute - minute_count),
                "this_hour": max(0, self.rate_limit_per_hour - hour_count),
                "this_day": max(0, self.rate_limit_per_day - day_count)
            },
            "total_emails_tracked": len(self.email_history),
            "unique_recipients": len(self.per_email_history)
        }

    def reset_rate_limits(self):
        """Reset all rate limiting counters (use with caution)"""
        self.email_history.clear()
        self.per_email_history.clear()

    def update_rate_limits(self, per_minute: Optional[int] = None, 
                          per_hour: Optional[int] = None, 
                          per_day: Optional[int] = None):
        """Update rate limit settings"""
        if per_minute is not None:
            self.rate_limit_per_minute = per_minute
        if per_hour is not None:
            self.rate_limit_per_hour = per_hour
        if per_day is not None:
            self.rate_limit_per_day = per_day

    def close(self):
        """Close SMTP connection"""
        if self.smtp_connection:
            self.smtp_connection.quit()
            self.smtp_connection = None

    