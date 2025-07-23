# Configuration file for SAY Website Backend
# Set your Discord webhook URL here or as an environment variable

import os
from typing import Optional

class Config:
    """Application configuration."""
    
    # Discord Configuration
    DISCORD_WEBHOOK_URL: Optional[str] = os.getenv('DISCORD_WEBHOOK_URL')
    DISCORD_NOTIFICATIONS_ENABLED: bool = os.getenv('DISCORD_NOTIFICATIONS_ENABLED', 'true').lower() == 'true'
    
    # Flask Configuration
    DEBUG: bool = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    SECRET_KEY: str = os.getenv('SECRET_KEY', 'your-secret-key-here')
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    
    @classmethod
    def get_discord_webhook_url(cls) -> Optional[str]:
        """Get the Discord webhook URL from environment or config."""
        return cls.DISCORD_WEBHOOK_URL
    
    @classmethod
    def is_discord_enabled(cls) -> bool:
        """Check if Discord notifications are enabled."""
        return cls.DISCORD_NOTIFICATIONS_ENABLED and cls.DISCORD_WEBHOOK_URL is not None

# Create configuration instance
config = Config()
