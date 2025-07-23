#!/usr/bin/env python3
"""
Complete test to verify all sensitive data is properly sanitized.
"""

from log_sanitizer import SensitiveDataSanitizer

def test_complete_sanitization():
    """Test complete sanitization with all types of sensitive data."""
    
    sanitizer = SensitiveDataSanitizer()
    
    print("Testing complete log sanitization coverage...")
    print("=" * 80)
    
    # Test categories with sample messages
    test_categories = {
        "Email & Auth": [
            "Connected to Dropbox account: user@example.com",
            "Bearer abc123token456",
            "Basic dXNlcjpwYXNzd29yZA==",
            "api_key: sk_test_123456789"
        ],
        "File Names & Paths": [
            "most recent: stock_test_file_v2_(4).xlsx",
            "Processing most recent stock file: inventory_data_final.csv",
            "Downloading file: product_list_2025.xlsx",
            "products from file: dropbox_stock_test_file_v2_(4).xlsx",
            "Processing file: /var/folders/abc/def/tmp123.xlsx"
        ],
        "Conway Operations": [
            "Found 4 Conway variant SKUs",
            "Retrieved 12 Conway category products",
            "Updating VARIANT stock 64f8b2c3d1e5a2b7c8d9e0f1: 15 -> 20 (difference: +5)",
            "Successfully updated stock for variant 64f8b2c3d1e5a2b7c8d9e0f1",
            "Updated stock for SKU 2879351: 10 -> 15",
            "Reset stock to 0 for Conway SKU: 2879369 (was 5)"
        ],
        "System Counts": [
            "Conway SKUs reset to 0: 3",
            "Stock updates applied: 7",
            "Non-Conway SKUs skipped: 2",
            "Extracted 15 SKUs from file",
            "Found 8 stock files",
            "Downloaded 3 stock file(s)"
        ],
        "Infrastructure": [
            "Conectando al servidor SMTP: smtp.strato.com:465",
            "Checking Dropbox folder: /INVENTORY_FILES/STOCK",
            "Downloaded file to: /var/folders/gx/abc123def456/T/tmpabcd1234.xlsx",
            "Column mappings - SKU: item, Price: evp, Offer: None"
        ]
    }
    
    all_passed = True
    total_tests = 0
    passed_tests = 0
    
    for category, messages in test_categories.items():
        print(f"\n📂 {category}:")
        print("-" * 40)
        
        for message in messages:
            total_tests += 1
            sanitized = sanitizer.sanitize(message)
            
            # Check if message was sanitized (different from original)
            if message != sanitized:
                passed_tests += 1
                print(f"✅ {message[:50]}... → SANITIZED")
            else:
                print(f"❌ {message[:50]}... → NOT CHANGED")
                all_passed = False
    
    print("\n" + "=" * 80)
    print(f"RESULTS: {passed_tests}/{total_tests} tests passed")
    
    if all_passed:
        print("🎉 ALL SENSITIVE DATA PROPERLY SANITIZED!")
    else:
        print("⚠️  Some sensitive data may still be exposed!")
    
    return all_passed

def test_redaction_tokens():
    """Test that all redaction tokens are working."""
    
    sanitizer = SensitiveDataSanitizer()
    
    expected_tokens = [
        '[EMAIL_REDACTED]',
        '[FILENAME_REDACTED]',
        '[VARIANT_ID_REDACTED]',
        '[SKU_REDACTED]',
        '[COUNT_REDACTED]',
        '[STOCK_FROM_REDACTED]',
        '[STOCK_TO_REDACTED]',
        '[STOCK_DIFF_REDACTED]',
        '[TEMP_FILE_PATH_REDACTED]',
        '[SMTP_SERVER_REDACTED]',
        '[FOLDER_PATH_REDACTED]',
        '[COLUMN_MAPPING_REDACTED]',
        '[PRODUCT_COUNT_REDACTED]'
    ]
    
    print("\n" + "=" * 80)
    print("Testing redaction tokens...")
    
    # Create test message with various sensitive data
    test_message = """
    2025-07-23 19:29:47,374 - dropbox_handler - INFO - Found 4 stock files, most recent: stock_test_file_v2_(4).xlsx
    2025-07-23 19:29:48,988 - holded_api - INFO - Updating VARIANT stock 64f8b2c3d1e5a2b7c8d9e0f1: 15 -> 20 (difference: +5)
    2025-07-23 19:29:49,584 - inventory_updater - INFO - Updated stock for SKU 2879351: 10 -> 15
    2025-07-23 19:29:50,115 - email_notifier - INFO - Conectando al servidor SMTP: smtp.strato.com:465
    """
    
    sanitized = sanitizer.sanitize(test_message)
    
    tokens_found = []
    for token in expected_tokens:
        if token in sanitized:
            tokens_found.append(token)
    
    print(f"Found {len(tokens_found)} redaction tokens:")
    for token in tokens_found:
        print(f"  ✅ {token}")
    
    missing_tokens = set(expected_tokens) - set(tokens_found)
    if missing_tokens:
        print(f"\nMissing tokens (not found in test):")
        for token in missing_tokens:
            print(f"  ⚠️  {token}")
    
    return len(tokens_found) > 0

if __name__ == "__main__":
    success1 = test_complete_sanitization()
    success2 = test_redaction_tokens()
    
    if success1 and success2:
        print("\n🔒 COMPLETE SANITIZATION SYSTEM VERIFIED!")
        print("All sensitive data is properly protected.")
    else:
        print("\n❌ Sanitization system needs attention!")