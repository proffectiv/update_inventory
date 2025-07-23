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
            # Inventory-specific patterns
            'file_names': re.compile(r'\b[\w\-_]+\.(?:xlsx?|csv|xls)\b', re.IGNORECASE),
            'folder_paths': re.compile(r'/[A-Z\-_]+(?:/[^\s]*)?'),
            'temp_file_paths': re.compile(r'/var/folders/[^\s]+', re.IGNORECASE),
            'stock_counts': re.compile(r'Found\s+\d+\s+stock\s+files', re.IGNORECASE),
            'download_counts': re.compile(r'Downloaded\s+\d+\s+stock\s+file\(s\)', re.IGNORECASE),
            'recent_files': re.compile(r'most\s+recent:\s+[\w\-_.()]+\.(?:xlsx?|csv|xls)', re.IGNORECASE),
            'unchanged_files': re.compile(r'Most\s+recent\s+stock\s+file\s+unchanged:\s+[\w\-_.()]+\.(?:xlsx?|csv|xls)', re.IGNORECASE),
            'processing_stock_file': re.compile(r'Processing\s+most\s+recent\s+stock\s+file:\s+[\w\-_.()]+\.(?:xlsx?|csv|xls)', re.IGNORECASE),
            'downloading_file': re.compile(r'Downloading\s+file:\s+[\w\-_.()]+\.(?:xlsx?|csv|xls)', re.IGNORECASE),
            'products_from_file_with_name': re.compile(r'products\s+from\s+file:\s+[\w\-_.()]+\.(?:xlsx?|csv|xls)', re.IGNORECASE),
            'dropbox_folders': re.compile(r'Checking\s+Dropbox\s+folder:\s+[^\s]+', re.IGNORECASE),
            'smtp_servers': re.compile(r'smtp\.[^\s:,]+', re.IGNORECASE),
            'smtp_connection': re.compile(r'Conectando\s+al\s+servidor\s+SMTP:\s+[^\s]+', re.IGNORECASE),
            # Product processing patterns
            'product_counts': re.compile(r'(?:Extracted|Found|Processed|Validated)\s+\d+\s+(?:valid\s+)?products?', re.IGNORECASE),
            'column_mappings': re.compile(r'Column\s+mappings\s+-\s+[^:]+:', re.IGNORECASE),
            'variant_ids': re.compile(r'\b[a-f0-9]{24}\b'),
            'product_details': re.compile(r'\([^)]*(?:Talla|Color|Medida|Tipo|Forma)[^)]*\)', re.IGNORECASE),
            'stock_updates': re.compile(r':\s*\d+\s*->\s*\d+', re.IGNORECASE),
            'stock_difference': re.compile(r'\(difference:\s*[+-]\d+\)', re.IGNORECASE),
            'processing_file': re.compile(r'Processing\s+file:\s+[^\s]+', re.IGNORECASE),
            # Holded product data patterns
            'retrieved_products': re.compile(r'Retrieved\s+\d+\s+products\s+from\s+Holded', re.IGNORECASE),
            'sku_lookup_counts': re.compile(r'Created\s+SKU\s+lookup\s+with\s+\d+\s+total\s+SKUs', re.IGNORECASE),
            'main_product_skus': re.compile(r'Main\s+product\s+SKUs:\s+\d+', re.IGNORECASE),
            'variant_skus': re.compile(r'Variant\s+SKUs:\s+\d+', re.IGNORECASE),
            'skipped_products': re.compile(r'Skipped\s+products\s+without\s+valid\s+SKU:\s+\d+', re.IGNORECASE),
            'loaded_products': re.compile(r'Loaded\s+\d+\s+products\s+from\s+Holded', re.IGNORECASE),
            'sample_skus': re.compile(r'Sample\s+Holded\s+SKUs:\s+\[[^\]]+\]', re.IGNORECASE),
            'sku_product_info': re.compile(r'-\s+\d+:\s+MAIN\s+product\s+[\'"][^\'"]+[\'"]', re.IGNORECASE),
            'numeric_skus': re.compile(r'\b\d{9,}\b'),
            # Conway-specific patterns
            'conway_items_found': re.compile(r'Found\s+\d+\s+Conway\s+items\s+not\s+in\s+stocklist\s+to\s+set\s+to\s+0\s+stock', re.IGNORECASE),
            'conway_item_set_zero': re.compile(r'Set\s+Conway\s+item\s+\d+\s+stock\s+to\s+0\s+\(was\s+\d+\)', re.IGNORECASE),
            'conway_variant_count': re.compile(r'Found\s+\d+\s+Conway\s+variant\s+SKUs', re.IGNORECASE),
            'conway_category_products': re.compile(r'Retrieved\s+\d+\s+Conway\s+category\s+products', re.IGNORECASE),
            'variant_stock_update': re.compile(r'Updating\s+VARIANT\s+stock\s+[a-f0-9]{24}:', re.IGNORECASE),
            'variant_successfully_updated': re.compile(r'Successfully\s+updated\s+stock\s+for\s+variant\s+[a-f0-9]{24}', re.IGNORECASE),
            'updated_stock_sku': re.compile(r'Updated\s+stock\s+for\s+SKU\s+\d+:', re.IGNORECASE),
            'reset_stock_sku': re.compile(r'Reset\s+stock\s+to\s+0\s+for\s+Conway\s+SKU:\s+\d+', re.IGNORECASE),
            'scenario_summary_counts': re.compile(r'Conway\s+SKUs\s+reset\s+to\s+0:\s+\d+', re.IGNORECASE),
            'stock_updates_applied': re.compile(r'Stock\s+updates\s+applied:\s+\d+', re.IGNORECASE),
            'non_conway_skipped': re.compile(r'Non-Conway\s+SKUs\s+skipped:\s+\d+', re.IGNORECASE),
            'extracted_skus': re.compile(r'Extracted\s+\d+\s+SKUs\s+from\s+file', re.IGNORECASE),
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
            # Inventory-specific replacements
            'file_names': '[FILENAME_REDACTED]',
            'folder_paths': '[FOLDER_PATH_REDACTED]',
            'temp_file_paths': '[TEMP_FILE_PATH_REDACTED]',
            'stock_counts': 'Found [COUNT_REDACTED] stock files',
            'download_counts': 'Downloaded [COUNT_REDACTED] stock file(s)',
            'recent_files': 'most recent: [FILENAME_REDACTED]',
            'unchanged_files': 'Most recent stock file unchanged: [FILENAME_REDACTED]',
            'processing_stock_file': 'Processing most recent stock file: [FILENAME_REDACTED]',
            'downloading_file': 'Downloading file: [FILENAME_REDACTED]',
            'products_from_file_with_name': 'products from file: [FILENAME_REDACTED]',
            'dropbox_folders': 'Checking Dropbox folder: [FOLDER_PATH_REDACTED]',
            'smtp_servers': '[SMTP_SERVER_REDACTED]',
            'smtp_connection': 'Conectando al servidor SMTP: [SMTP_SERVER_REDACTED]',
            # Product processing replacements
            'product_counts': '[PRODUCT_COUNT_REDACTED] products',
            'column_mappings': 'Column mappings - [COLUMN_MAPPING_REDACTED]:',
            'variant_ids': '[VARIANT_ID_REDACTED]',
            'product_details': '([PRODUCT_DETAILS_REDACTED])',
            'stock_updates': ': [STOCK_FROM_REDACTED] -> [STOCK_TO_REDACTED]',
            'stock_difference': '(difference: [STOCK_DIFF_REDACTED])',
            'processing_file': 'Processing file: [FILE_PATH_REDACTED]',
            # Holded product data replacements
            'retrieved_products': 'Retrieved [COUNT_REDACTED] products from Holded',
            'sku_lookup_counts': 'Created SKU lookup with [COUNT_REDACTED] total SKUs',
            'main_product_skus': 'Main product SKUs: [COUNT_REDACTED]',
            'variant_skus': 'Variant SKUs: [COUNT_REDACTED]',
            'skipped_products': 'Skipped products without valid SKU: [COUNT_REDACTED]',
            'loaded_products': 'Loaded [COUNT_REDACTED] products from Holded',
            'sample_skus': 'Sample Holded SKUs: [SAMPLE_SKUS_REDACTED]',
            'sku_product_info': '- [SKU_REDACTED]: MAIN product \"[PRODUCT_NAME_REDACTED]\"',
            'numeric_skus': '[SKU_REDACTED]',
            # Conway-specific replacements
            'conway_items_found': 'Found [COUNT_REDACTED] Conway items not in stocklist to set to 0 stock',
            'conway_item_set_zero': 'Set Conway item [SKU_REDACTED] stock to 0 (was [STOCK_COUNT_REDACTED])',
            'conway_variant_count': 'Found [COUNT_REDACTED] Conway variant SKUs',
            'conway_category_products': 'Retrieved [COUNT_REDACTED] Conway category products',
            'variant_stock_update': 'Updating VARIANT stock [VARIANT_ID_REDACTED]:',
            'variant_successfully_updated': 'Successfully updated stock for variant [VARIANT_ID_REDACTED]',
            'updated_stock_sku': 'Updated stock for SKU [SKU_REDACTED]:',
            'reset_stock_sku': 'Reset stock to 0 for Conway SKU: [SKU_REDACTED]',
            'scenario_summary_counts': 'Conway SKUs reset to 0: [COUNT_REDACTED]',
            'stock_updates_applied': 'Stock updates applied: [COUNT_REDACTED]',
            'non_conway_skipped': 'Non-Conway SKUs skipped: [COUNT_REDACTED]',
            'extracted_skus': 'Extracted [COUNT_REDACTED] SKUs from file',
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