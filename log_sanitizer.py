"""
Log sanitizer module for removing sensitive information from logs.

This module provides:
- Custom logging formatter that sanitizes sensitive data
- Functions to clean existing log files
- Patterns for detecting and masking sensitive information
"""

import re
import logging
from typing import Dict, List, Pattern


class SensitiveDataSanitizer:
    """Handles sanitization of sensitive data in log messages."""
    
    def __init__(self):
        """Initialize sanitizer with patterns for sensitive data detection."""
        self.patterns: Dict[str, Pattern] = {
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'api_key': re.compile(r'(?i)(api[_-]?key|token|secret|password)["\'\s]*[:=]["\'\s]*([^\s"\']+)'),
            'bearer_token': re.compile(r'Bearer\s+[A-Za-z0-9\-._~+/]+=*', re.IGNORECASE),
            'basic_auth': re.compile(r'Basic\s+[A-Za-z0-9+/]+=*', re.IGNORECASE),
            'url_credentials': re.compile(r'://[^:]+:[^@]+@'),
            'ip_address': re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'),
            'phone': re.compile(r'\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b'),
            'credit_card': re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
            'social_security': re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
        }
        
        self.replacements: Dict[str, str] = {
            'email': '[EMAIL_REDACTED]',
            'api_key': r'\1: [API_KEY_REDACTED]',
            'bearer_token': 'Bearer [TOKEN_REDACTED]',
            'basic_auth': 'Basic [AUTH_REDACTED]',
            'url_credentials': '://[CREDENTIALS_REDACTED]@',
            'ip_address': '[IP_REDACTED]',
            'phone': '[PHONE_REDACTED]',
            'credit_card': '[CARD_REDACTED]',
            'social_security': '[SSN_REDACTED]',
        }
    
    def sanitize(self, message: str) -> str:
        """
        Sanitize a log message by replacing sensitive data with placeholders.
        
        Args:
            message: The log message to sanitize
            
        Returns:
            The sanitized log message
        """
        sanitized = message
        
        for pattern_name, pattern in self.patterns.items():
            replacement = self.replacements.get(pattern_name, '[REDACTED]')
            sanitized = pattern.sub(replacement, sanitized)
        
        return sanitized


class SanitizingFormatter(logging.Formatter):
    """Custom logging formatter that sanitizes sensitive data."""
    
    def __init__(self, *args, **kwargs):
        """Initialize the formatter with sanitizer."""
        super().__init__(*args, **kwargs)
        self.sanitizer = SensitiveDataSanitizer()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record and sanitize sensitive data."""
        # Format the record normally first
        formatted = super().format(record)
        
        # Sanitize the formatted message
        return self.sanitizer.sanitize(formatted)


def sanitize_log_file(file_path: str, output_path: str = None) -> bool:
    """
    Sanitize an existing log file by removing sensitive information.
    
    Args:
        file_path: Path to the log file to sanitize
        output_path: Optional output path. If None, overwrites original file
        
    Returns:
        True if sanitization was successful, False otherwise
    """
    sanitizer = SensitiveDataSanitizer()
    
    try:
        # Read the original file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Sanitize the content
        sanitized_content = sanitizer.sanitize(content)
        
        # Write to output file (or overwrite original)
        output_file = output_path or file_path
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(sanitized_content)
        
        print(f"Successfully sanitized log file: {output_file}")
        return True
        
    except Exception as e:
        print(f"Error sanitizing log file {file_path}: {e}")
        return False


def setup_sanitized_logging():
    """
    Set up logging with sanitization.
    Replace this function call in main.py instead of the current setup_logging().
    """
    # Remove any existing handlers
    logging.getLogger().handlers.clear()
    
    # Create sanitizing formatter
    formatter = SanitizingFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Set up console handler with sanitizer
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Set up file handler with sanitizer
    file_handler = logging.FileHandler('inventory_update.log')
    file_handler.setFormatter(formatter)
    
    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        handlers=[console_handler, file_handler]
    )


if __name__ == "__main__":
    # Example usage for cleaning existing log files
    sanitize_log_file('inventory_update.log')