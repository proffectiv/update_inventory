#!/usr/bin/env python3
"""
Test script to verify email notification structure with robust system.
"""

from email_notifier import EmailNotifier

def test_email_structure():
    """Test email notification with robust system results structure."""
    
    # Simulate results from the robust system
    test_results = {
        'processed_files': 2,
        'processed_products': 25,
        'stock_updates': 8,  # Regular updates
        'stock_resets': 5,   # Conway SKUs set to 0
        'skipped_not_in_holded': 3,  # Non-Conway SKUs
        'errors': [],
        'summary': {
            'stock_updates': [  # Combined updates and resets
                {
                    'sku': 'CONWAY-VAR-001',
                    'product_name': 'Conway Mountain Bike - Size M',
                    'old_stock': 10,
                    'new_stock': 15,
                    'is_variant': True,
                    'action': 'update'
                },
                {
                    'sku': 'CONWAY-VAR-002', 
                    'product_name': 'Conway Mountain Bike - Size L',
                    'old_stock': 5,
                    'new_stock': 0,
                    'is_variant': True,
                    'action': 'reset'
                },
                {
                    'sku': 'CONWAY-VAR-003',
                    'product_name': 'Conway E-Bike - Color Red',
                    'old_stock': 0,
                    'new_stock': 8,
                    'is_variant': True,
                    'action': 'update'
                }
            ],
            'total_stock_updates': 3,
            'errors': []
        }
    }
    
    print("Testing email notification structure...")
    
    # Create email notifier (won't actually send)
    notifier = EmailNotifier()
    
    try:
        # Test subject creation
        subject = notifier._create_email_subject(test_results)
        print(f"✅ Email Subject: {subject}")
        
        # Test HTML body creation
        html_body = notifier._create_email_body_html(test_results)
        print("✅ HTML body created successfully")
        
        # Check if stock updates table is included
        if 'Cambios de Stock (Variantes)' in html_body:
            print("✅ Stock changes table included in HTML")
        else:
            print("❌ Stock changes table missing from HTML")
        
        # Check if variant details are included
        if 'CONWAY-VAR-001' in html_body:
            print("✅ Variant SKUs included in HTML")
        else:
            print("❌ Variant SKUs missing from HTML")
        
        # Check if action types are shown
        if 'Reset a 0' in html_body and 'Actualización' in html_body:
            print("✅ Action types (update/reset) included in HTML")
        else:
            print("❌ Action types missing from HTML")
        
        # Test text body creation
        text_body = notifier._create_email_body_text(test_results)
        print("✅ Text body created successfully")
        
        # Check text body content
        if 'CAMBIOS DE STOCK - VARIANTES' in text_body:
            print("✅ Stock changes section included in text")
        else:
            print("❌ Stock changes section missing from text")
        
        # Show sample HTML (first 500 chars)
        print("\n" + "="*60)
        print("SAMPLE HTML OUTPUT:")
        print("="*60)
        html_snippet = html_body.replace('\n', '').replace('  ', ' ')[:800]
        print(html_snippet + "...")
        
        print("\n" + "="*60)
        print("SAMPLE TEXT OUTPUT (first 500 chars):")
        print("="*60)
        print(text_body[:500] + "...")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing email structure: {e}")
        return False

if __name__ == "__main__":
    success = test_email_structure()
    if success:
        print("\n✅ Email notification structure test passed!")
    else:
        print("\n❌ Email notification structure test failed!")