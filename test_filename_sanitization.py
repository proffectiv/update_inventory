#!/usr/bin/env python3
"""
Test script to verify filename sanitization works with actual exposed filenames.
"""

from log_sanitizer import SensitiveDataSanitizer

def test_filename_sanitization():
    """Test filename sanitization with the actual exposed filenames from the logs."""
    
    sanitizer = SensitiveDataSanitizer()
    
    # Actual exposed messages from the log
    test_messages = [
        "2025-07-23 19:29:47,374 - dropbox_handler - INFO - Found [COUNT_REDACTED] stock files, most recent: stock_test_file_v2_(4).xlsx",
        "2025-07-23 19:29:47,374 - dropbox_handler - INFO - Processing most recent stock file: stock_test_file_v2_(4).xlsx",
        "2025-07-23 19:29:47,376 - dropbox_handler - INFO - Downloading file: stock_test_file_v2_(4).xlsx",
        "2025-07-23 19:29:48,988 - file_processor - INFO - [PRODUCT_COUNT_REDACTED] products from file: dropbox_stock_test_file_v2_(4).xlsx"
    ]
    
    print("Testing filename sanitization with exposed filenames...")
    print("=" * 80)
    
    all_passed = True
    
    for i, message in enumerate(test_messages, 1):
        sanitized = sanitizer.sanitize(message)
        
        print(f"\nTest {i}:")
        print(f"Original : {message}")
        print(f"Sanitized: {sanitized}")
        
        # Check if the specific filename was redacted
        if "stock_test_file_v2_(4).xlsx" in sanitized or "dropbox_stock_test_file_v2_(4).xlsx" in sanitized:
            print("❌ Filename still visible!")
            all_passed = False
        else:
            print("✅ Filename properly redacted")
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ All filename sanitization tests passed!")
    else:
        print("❌ Some filename sanitization tests failed!")
    
    return all_passed

if __name__ == "__main__":
    success = test_filename_sanitization()
    if not success:
        print("\n🔧 Need to adjust sanitization patterns!")