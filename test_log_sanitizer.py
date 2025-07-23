#!/usr/bin/env python3
"""
Test script to verify log sanitizer works with robust system logs.
"""

from log_sanitizer import SensitiveDataSanitizer

def test_log_sanitization():
    """Test log sanitization with sample robust system log messages."""
    
    sanitizer = SensitiveDataSanitizer()
    
    # Sample log messages from the execution
    test_messages = [
        "2025-07-23 19:24:56,942 - holded_api - INFO - Found 4 Conway variant SKUs",
        "2025-07-23 19:24:56,942 - holded_api - INFO - Retrieved 1 Conway category products",
        "2025-07-23 19:24:57,034 - holded_api - INFO - Updating VARIANT stock 64f8b2c3d1e5a2b7c8d9e0f1: 15 -> 20 (difference: +5)",
        "2025-07-23 19:24:57,333 - holded_api - INFO - Successfully updated stock for variant 64f8b2c3d1e5a2b7c8d9e0f1",
        "2025-07-23 19:24:57,333 - inventory_updater - INFO - Updated stock for SKU 2879351: 15 -> 20",
        "2025-07-23 19:24:57,280 - inventory_updater - INFO - Conway SKUs reset to 0: 0",
        "2025-07-23 19:24:57,280 - inventory_updater - INFO - Stock updates applied: 4",
        "2025-07-23 19:24:57,280 - inventory_updater - INFO - Non-Conway SKUs skipped: 0",
        "2025-07-23 19:24:58,284 - email_notifier - INFO - Conectando al servidor SMTP: smtp.strato.com:465",
        "2025-07-23 19:24:56,195 - __main__ - INFO -   - /var/folders/gx/abc123def456/T/tmpabcd1234.xlsx",
        "2025-07-23 19:24:55,472 - dropbox_handler - INFO - Found 3 stock files, most recent: stock_test_file_v2_(3).xlsx",
        "2025-07-23 19:24:57,033 - file_processor - INFO - Column mappings - SKU: item, Price: evp, Offer: None, Stock: stock qty",
        "2025-07-23 19:24:57,033 - inventory_updater - INFO - Extracted 4 SKUs from file"
    ]
    
    print("Testing log sanitization with robust system patterns...")
    print("=" * 80)
    
    all_passed = True
    
    for i, message in enumerate(test_messages, 1):
        sanitized = sanitizer.sanitize(message)
        
        print(f"\nTest {i}:")
        print(f"Original : {message}")
        print(f"Sanitized: {sanitized}")
        
        # Check if sensitive data was properly redacted
        if message != sanitized:
            print("✅ Message was sanitized")
        else:
            print("⚠️  Message was not changed (may not contain sensitive data)")
        
        # Check for specific redaction patterns
        sensitive_found = False
        if any(pattern in message.lower() for pattern in ['variant', 'sku', 'smtp', 'folder', 'file']):
            if any(redacted in sanitized for redacted in ['[VARIANT_ID_REDACTED]', '[SKU_REDACTED]', '[SMTP_SERVER_REDACTED]', '[TEMP_FILE_PATH_REDACTED]', '[FILENAME_REDACTED]', '[COUNT_REDACTED]', '[COLUMN_MAPPING_REDACTED]']):
                print("✅ Sensitive data properly redacted")
            else:
                print("❌ Sensitive data not properly redacted")
                all_passed = False
                sensitive_found = True
        
        if not sensitive_found and message != sanitized:
            print("✅ Redaction patterns working")
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ All log sanitization tests passed!")
    else:
        print("❌ Some log sanitization tests failed!")
    
    return all_passed

def test_sanitizer_setup():
    """Test that the sanitizer setup works correctly."""
    print("\nTesting sanitizer setup...")
    
    try:
        from log_sanitizer import setup_sanitized_logging
        import logging
        
        # Test setup
        setup_sanitized_logging()
        
        # Test logging with sensitive data
        logger = logging.getLogger('test_logger')
        
        # This should be sanitized in the output
        logger.info("Testing with variant ID: 64f8b2c3d1e5a2b7c8d9e0f1 and SKU: 2879351")
        logger.info("Email sent to: user@example.com via smtp.strato.com")
        
        print("✅ Sanitized logging setup works!")
        return True
        
    except Exception as e:
        print(f"❌ Error setting up sanitized logging: {e}")
        return False

if __name__ == "__main__":
    success1 = test_log_sanitization()
    success2 = test_sanitizer_setup()
    
    if success1 and success2:
        print("\n🎉 All log sanitizer tests passed!")
    else:
        print("\n❌ Some log sanitizer tests failed!")