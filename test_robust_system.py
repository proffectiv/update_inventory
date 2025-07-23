#!/usr/bin/env python3
"""
Test script for the robust Conway category inventory system.

This script allows testing the new robust inventory functionality
without running the full automation.
"""

import sys
import logging

from holded_api import HoldedAPI
from inventory_updater import RobustInventoryUpdater

def test_conway_category_retrieval():
    """Test retrieving Conway category products."""
    print("=" * 60)
    print("TESTING CONWAY CATEGORY RETRIEVAL")
    print("=" * 60)
    
    try:
        api = HoldedAPI()
        
        # Test connection first
        print("Testing Holded API connection...")
        if not api.test_connection():
            print("❌ Holded API connection failed")
            return False
        print("✅ Holded API connection successful")
        
        # Test Conway category products retrieval
        print("Retrieving Conway category products...")
        conway_products = api.get_conway_category_products()
        
        if conway_products is None:
            print("❌ Failed to retrieve Conway category products")
            return False
        
        print(f"✅ Retrieved {len(conway_products)} Conway category products")
        
        # Test Conway variant SKUs extraction
        print("Extracting Conway variant SKUs...")
        conway_skus = api.get_conway_variant_skus()
        
        if not conway_skus:
            print("❌ Failed to extract Conway variant SKUs")
            return False
        
        print(f"✅ Extracted {len(conway_skus)} Conway variant SKUs")
        
        # Show sample SKUs (should all be variants now)
        sample_skus = list(conway_skus.keys())[:5]
        print("Sample Conway variant SKUs:")
        for sku in sample_skus:
            product_data = conway_skus[sku]
            product_type = "VARIANT" if product_data.get('_is_variant') else "MAIN (UNEXPECTED!)"
            product_name = product_data.get('name', 'Unknown')
            print(f"  - {sku}: {product_type} - {product_name}")
            
            # Warn if any main products made it through
            if not product_data.get('_is_variant'):
                print(f"    ⚠️  WARNING: Main product found in variant SKU list!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Conway category retrieval: {e}")
        return False

def test_robust_updater_logic():
    """Test the robust updater logic with dry run."""
    print("\n" + "=" * 60)
    print("TESTING ROBUST UPDATER LOGIC")
    print("=" * 60)
    
    try:
        updater = RobustInventoryUpdater()
        
        # Get Conway SKUs
        print("Getting Conway variant SKUs...")
        conway_skus = updater.holded_api.get_conway_variant_skus()
        
        if not conway_skus:
            print("❌ No Conway SKUs found")
            return False
        
        print(f"✅ Found {len(conway_skus)} Conway SKUs")
        
        # Simulate some file SKUs for testing scenarios
        print("Simulating file SKUs for testing...")
        sample_conway_skus = list(conway_skus.keys())[:3]
        
        # Create test file SKUs - some matching Conway, some not
        file_skus = {}
        
        # Add some Conway SKUs to file (scenario 2)
        if len(sample_conway_skus) >= 2:
            file_skus[sample_conway_skus[0]] = {'sku': sample_conway_skus[0], 'stock': 10}
            file_skus[sample_conway_skus[1]] = {'sku': sample_conway_skus[1], 'stock': 5}
        
        # Add some non-Conway SKUs (scenario 3)
        file_skus['TEST-NON-CONWAY-1'] = {'sku': 'TEST-NON-CONWAY-1', 'stock': 20}
        file_skus['TEST-NON-CONWAY-2'] = {'sku': 'TEST-NON-CONWAY-2', 'stock': 15}
        
        print(f"Created {len(file_skus)} test file SKUs:")
        for sku, data in file_skus.items():
            in_conway = "YES" if sku in conway_skus else "NO"
            print(f"  - {sku}: stock={data['stock']}, in_conway={in_conway}")
        
        # Test scenario logic (dry run - don't actually update)
        print("\nTesting scenario logic (dry run):")
        
        # Scenario 1: Conway SKUs not in file
        conway_not_in_file = [sku for sku in conway_skus.keys() if sku not in file_skus]
        print(f"Scenario 1 - Conway SKUs not in file (would be set to 0): {len(conway_not_in_file)}")
        for sku in conway_not_in_file[:3]:  # Show first 3
            current_stock = updater._get_current_stock(conway_skus[sku])
            print(f"  - {sku}: current_stock={current_stock}")
        
        # Scenario 2: SKUs in both
        both_match = [sku for sku in file_skus.keys() if sku in conway_skus]
        print(f"Scenario 2 - SKUs in both Conway and file: {len(both_match)}")
        for sku in both_match:
            current_stock = updater._get_current_stock(conway_skus[sku])
            new_stock = file_skus[sku]['stock']
            print(f"  - {sku}: current={current_stock}, new={new_stock}")
        
        # Scenario 3: File SKUs not in Conway
        file_not_in_conway = [sku for sku in file_skus.keys() if sku not in conway_skus]
        print(f"Scenario 3 - File SKUs not in Conway (would be skipped): {len(file_not_in_conway)}")
        for sku in file_not_in_conway:
            print(f"  - {sku}: would be skipped")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing robust updater logic: {e}")
        return False

def main():
    """Main test function."""
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    print("ROBUST INVENTORY SYSTEM TEST")
    print("=" * 60)
    
    # Run tests
    tests_passed = 0
    total_tests = 2
    
    if test_conway_category_retrieval():
        tests_passed += 1
    
    if test_robust_updater_logic():
        tests_passed += 1
    
    # Final results
    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)
    print(f"Tests passed: {tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("✅ All tests passed! The robust system appears to be working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the configuration and implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())