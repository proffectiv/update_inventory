"""
Configuration module for inventory update automation.

This module loads all necessary environment variables and provides
configuration for Dropbox, Holded API, email notifications (SMTP), and other settings.

Required environment variables (create a .env file):
- SMTP_HOST=smtp.strato.de
- SMTP_PORT=465
- SMTP_USERNAME=your-email@yourdomain.com
- SMTP_PASSWORD=your-email-password
- DROPBOX_ACCESS_TOKEN=your-dropbox-access-token
- DROPBOX_FOLDER_PATH=/inventory-updates
- HOLDED_API_KEY=your-holded-api-key
- HOLDED_BASE_URL=https://api.holded.com
- NOTIFICATION_EMAIL=admin@yourdomain.com
- ALLOWED_EXTENSIONS=csv,xlsx,xls
- MAX_FILE_SIZE_MB=10
"""

import os
from typing import List


class Config:
    """Configuration class that loads environment variables."""
    
    def __init__(self):
        """Initialize configuration with environment variables."""
        self._load_env_file()
        self._validate_required_vars()
    
    def _load_env_file(self):
        """Load environment variables from .env file if it exists."""
        try:
            with open('.env', 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
        except FileNotFoundError:
            print("Warning: .env file not found. Using system environment variables.")
    
    def _validate_required_vars(self):
        """Validate that all required environment variables are set."""
        required_vars = [
            'SMTP_HOST', 'SMTP_PORT', 'SMTP_USERNAME', 'SMTP_PASSWORD',
            'DROPBOX_ACCESS_TOKEN', 'HOLDED_API_KEY', 'NOTIFICATION_EMAIL'
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {missing_vars}")
    
    # Email Configuration (Strato SMTP - for notifications only)
    @property
    def smtp_host(self) -> str:
        return os.getenv('SMTP_HOST', 'smtp.strato.de')
    
    @property
    def smtp_port(self) -> int:
        return int(os.getenv('SMTP_PORT', '465'))
    
    @property
    def smtp_username(self) -> str:
        return os.getenv('SMTP_USERNAME', '')
    
    @property
    def smtp_password(self) -> str:
        return os.getenv('SMTP_PASSWORD', '')
    
    # Dropbox Configuration
    @property
    def dropbox_access_token(self) -> str:
        return os.getenv('DROPBOX_ACCESS_TOKEN', '')
    
    @property
    def dropbox_folder_path(self) -> str:
        return os.getenv('DROPBOX_FOLDER_PATH', '/inventory-updates')
    
    # Holded API Configuration
    @property
    def holded_api_key(self) -> str:
        return os.getenv('HOLDED_API_KEY', '')
    
    @property
    def holded_base_url(self) -> str:
        return os.getenv('HOLDED_BASE_URL', 'https://api.holded.com')
    
    # Notification Configuration
    @property
    def notification_email(self) -> str:
        return os.getenv('NOTIFICATION_EMAIL', '')
    
    # File Processing Configuration
    @property
    def allowed_extensions(self) -> List[str]:
        extensions = os.getenv('ALLOWED_EXTENSIONS', 'csv,xlsx,xls')
        return [ext.strip().lower() for ext in extensions.split(',')]
    
    @property
    def max_file_size_mb(self) -> int:
        return int(os.getenv('MAX_FILE_SIZE_MB', '10'))


# Global configuration instance
config = Config() 