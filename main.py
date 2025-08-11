"""
Main entry point for the inventory update automation.

This module handles:
- Orchestrating the complete workflow
- Checking email and Dropbox triggers
- Processing inventory files
- Coordinating updates and notifications
- Error handling and cleanup
"""

import sys
import logging
from typing import List, Dict, Any
import traceback

from dropbox_handler import check_dropbox_trigger
from inventory_updater import update_inventory_robust
from email_notifier import send_update_notification, send_error_notification
from log_sanitizer import setup_sanitized_logging
from new_products_processor import process_new_products_workflow, cleanup_new_products_files


def setup_logging():
    """Set up logging configuration with sanitization."""
    setup_sanitized_logging()


def main():
    """
    Main function that orchestrates the inventory update process.
    
    This function:
    1. Checks for Dropbox file updates
    2. Processes any found files
    3. Updates inventory in Holded
    4. Sends notification emails
    5. Handles errors and cleanup
    """
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("STARTING INVENTORY UPDATE AUTOMATION")
    logger.info("=" * 60)
    
    try:
        # Step 1: Check for Dropbox file updates
        logger.info("Step 1: Checking for Dropbox file updates...")
        
        try:
            files_to_process = check_dropbox_trigger()
            if files_to_process:
                logger.info(f"Found {len(files_to_process)} files from Dropbox")
            else:
                logger.info("No Dropbox file updates found. Automation completed.")
                return
        except Exception as e:
            logger.error(f"Error checking Dropbox trigger: {e}")
            return
        
        logger.info(f"Total files to process: {len(files_to_process)}")
        for file_path in files_to_process:
            logger.info(f"  - {file_path}")
        
        # Step 2: Process inventory updates with robust Conway category logic
        logger.info("Step 2: Processing inventory updates with robust Conway category logic...")
        
        update_results = update_inventory_robust(files_to_process)
        
        # Log summary
        logger.info("UPDATE SUMMARY:")
        logger.info(f"  Files processed: {update_results.get('processed_files', 0)}")
        logger.info(f"  Products processed: {update_results.get('processed_products', 0)}")
        logger.info(f"  Stock updates: {update_results.get('stock_updates', 0)}")
        logger.info(f"  Stock resets (Conway SKUs not in files): {update_results.get('stock_resets', 0)}")
        logger.info(f"  SKUs skipped (not Conway): {update_results.get('skipped_not_in_holded', 0)}")
        logger.info(f"  New products for manual creation: {len(update_results.get('new_products_for_creation', []))}")
        logger.info(f"  Errors: {len(update_results.get('errors', []))}")
        
        # Step 2.5: Process new products if any exist
        new_products_data = update_results.get('new_products_for_creation', [])
        attachment_files = None
        
        if new_products_data:
            logger.info(f"Step 2.5: Processing {len(new_products_data)} new products for import files and images...")
            
            try:
                new_products_result = process_new_products_workflow(new_products_data)
                
                if new_products_result:
                    # Prepare attachment files for email
                    attachment_files = {}
                    
                    if new_products_result.get('holded_import'):
                        attachment_files['Conway Products Import.csv'] = new_products_result['holded_import']
                        logger.info(f"Prepared Holded import file for email attachment: {new_products_result['holded_import']}")
                    
                    if new_products_result.get('images_zip'):
                        attachment_files['Product Images.zip'] = new_products_result['images_zip']
                        logger.info(f"Prepared images ZIP file for email attachment: {new_products_result['images_zip']}")
                    
                    # Merge enhanced new products data into update_results for email notification
                    if new_products_result.get('completely_new_products'):
                        update_results['completely_new_products'] = new_products_result['completely_new_products']
                    if new_products_result.get('new_variants_of_existing_products'):
                        update_results['new_variants_of_existing_products'] = new_products_result['new_variants_of_existing_products']
                    if new_products_result.get('products_for_deletion'):
                        update_results['products_for_deletion'] = new_products_result['products_for_deletion']
                    if new_products_result.get('data_integrity_issues'):
                        update_results['data_integrity_issues'] = new_products_result['data_integrity_issues']
                    if new_products_result.get('processing_metadata'):
                        update_results['processing_metadata'] = new_products_result['processing_metadata']
                    
                    logger.info(f"New products processing completed successfully with {len(attachment_files)} attachments")
                else:
                    logger.warning("New products processing failed or returned no results")
                    
            except Exception as e:
                logger.error(f"Error processing new products: {e}")
                logger.error(traceback.format_exc())
        else:
            logger.info("No new products to process - skipping new products workflow")
        
        # Step 3: Send notification email
        logger.info("Step 3: Sending notification email...")
        
        try:
            email_sent = send_update_notification(update_results, attachment_files)
            if email_sent:
                logger.info("Notification email sent successfully")
            else:
                logger.warning("Failed to send notification email")
        except Exception as e:
            logger.error(f"Error sending notification email: {e}")
        
        # Step 4: Cleanup temporary files
        logger.info("Step 4: Cleaning up temporary files...")
        cleanup_temp_files(files_to_process)
        
        # Step 4.5: Cleanup new products files if any were created
        if new_products_data and attachment_files:
            logger.info("Step 4.5: Cleaning up new products temporary files...")
            try:
                if 'new_products_result' in locals() and new_products_result:
                    # Extract only file paths for cleanup
                    file_paths = {
                        'holded_import': new_products_result.get('holded_import'),
                        'images_zip': new_products_result.get('images_zip'),
                        'temp_stock_csv': new_products_result.get('temp_stock_csv')
                    }
                    cleanup_new_products_files(file_paths)
                else:
                    cleanup_new_products_files(None)
            except Exception as e:
                logger.warning(f"Error cleaning up new products files: {e}")
        
        logger.info("=" * 60)
        logger.info("INVENTORY UPDATE AUTOMATION COMPLETED")
        logger.info("=" * 60)
        
    except Exception as e:
        error_msg = f"Critical error in main automation: {e}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        
        # Send error notification
        try:
            send_error_notification(
                error_message=error_msg,
                error_details=traceback.format_exc()
            )
        except Exception as notify_error:
            logger.error(f"Failed to send error notification: {notify_error}")
        
        # Exit with error code
        sys.exit(1)


def cleanup_temp_files(file_paths: List[str]):
    """
    Clean up temporary files.
    
    Args:
        file_paths: List of file paths to clean up
    """
    logger = logging.getLogger(__name__)
    
    for file_path in file_paths:
        try:
            import os
            if os.path.exists(file_path) and '/tmp/' in file_path:  # Only delete temp files
                os.remove(file_path)
                logger.info(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"Could not clean up file {file_path}: {e}")


def test_connections():
    """
    Test all external connections (Holded API, Dropbox, Email).
    
    This function is useful for debugging and initial setup.
    """
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("TESTING CONNECTIONS")
    logger.info("=" * 40)
    
    # Test Holded API
    try:
        from holded_api import HoldedAPI
        holded = HoldedAPI()
        if holded.test_connection():
            logger.info("✅ Holded API connection: SUCCESS")
        else:
            logger.error("❌ Holded API connection: FAILED")
    except Exception as e:
        logger.error(f"❌ Holded API connection: ERROR - {e}")
    
    # Test Dropbox
    try:
        from dropbox_handler import DropboxHandler
        dropbox = DropboxHandler()
        if dropbox.test_connection():
            logger.info("✅ Dropbox connection: SUCCESS")
        else:
            logger.error("❌ Dropbox connection: FAILED")
    except Exception as e:
        logger.error(f"❌ Dropbox connection: ERROR - {e}")
    
    # Test Email SMTP (for notifications only)
    try:
        from email_notifier import EmailNotifier
        notifier = EmailNotifier()
        # Send a test notification
        test_results = {
            'processed_files': 0,
            'processed_products': 0,
            'stock_updates': 0,
            'stock_resets': 0,
            'skipped_not_in_holded': 0,
            'new_products_for_creation': [],
            'errors': ['This is a connection test']
        }
        if notifier.send_update_confirmation(test_results):
            logger.info("✅ Email SMTP (notifications): SUCCESS")
        else:
            logger.error("❌ Email SMTP (notifications): FAILED")
    except Exception as e:
        logger.error(f"❌ Email SMTP (notifications): ERROR - {e}")
    
    logger.info("=" * 40)
    logger.info("CONNECTION TESTS COMPLETED")


def run_dropbox_only():
    """Run automation checking only Dropbox triggers (for testing)."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("RUNNING DROPBOX-ONLY MODE")
    
    try:
        dropbox_files = check_dropbox_trigger()
        if dropbox_files:
            logger.info(f"Found {len(dropbox_files)} files from Dropbox")
            update_results = update_inventory_robust(dropbox_files)
            
            # Process new products if any exist
            new_products_data = update_results.get('new_products_for_creation', [])
            attachment_files = None
            
            if new_products_data:
                logger.info(f"Processing {len(new_products_data)} new products...")
                try:
                    new_products_result = process_new_products_workflow(new_products_data)
                    if new_products_result:
                        attachment_files = {}
                        if new_products_result.get('holded_import'):
                            attachment_files['Conway Products Import.csv'] = new_products_result['holded_import']
                        if new_products_result.get('images_zip'):
                            attachment_files['Product Images.zip'] = new_products_result['images_zip']
                except Exception as e:
                    logger.error(f"Error processing new products: {e}")
            
            send_update_notification(update_results, attachment_files)
            cleanup_temp_files(dropbox_files)
            
            # Cleanup new products files if any were created
            if new_products_data and attachment_files:
                try:
                    if 'new_products_result' in locals() and new_products_result:
                        # Extract only file paths for cleanup
                        file_paths = {
                            'holded_import': new_products_result.get('holded_import'),
                            'images_zip': new_products_result.get('images_zip'),
                            'temp_stock_csv': new_products_result.get('temp_stock_csv')
                        }
                        cleanup_new_products_files(file_paths)
                    else:
                        cleanup_new_products_files(None)
                except Exception as e:
                    logger.warning(f"Error cleaning up new products files: {e}")
        else:
            logger.info("No Dropbox files found")
    except Exception as e:
        logger.error(f"Error in Dropbox-only mode: {e}")


def process_local_file(file_path: str):
    """
    Process a local file (for testing).
    
    Args:
        file_path: Path to the local file to process
    """
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info(f"PROCESSING LOCAL FILE: {file_path}")
    
    try:
        update_results = update_inventory_robust([file_path])
        
        # Process new products if any exist
        new_products_data = update_results.get('new_products_for_creation', [])
        attachment_files = None
        
        if new_products_data:
            logger.info(f"Processing {len(new_products_data)} new products...")
            try:
                new_products_result = process_new_products_workflow(new_products_data)
                if new_products_result:
                    attachment_files = {}
                    if new_products_result.get('holded_import'):
                        attachment_files['Conway Products Import.csv'] = new_products_result['holded_import']
                    if new_products_result.get('images_zip'):
                        attachment_files['Product Images.zip'] = new_products_result['images_zip']
            except Exception as e:
                logger.error(f"Error processing new products: {e}")
        
        send_update_notification(update_results, attachment_files)
        
        # Cleanup new products files if any were created
        if new_products_data and attachment_files:
            try:
                if 'new_products_result' in locals() and new_products_result:
                    # Extract only file paths for cleanup
                    file_paths = {
                        'holded_import': new_products_result.get('holded_import'),
                        'images_zip': new_products_result.get('images_zip'),
                        'temp_stock_csv': new_products_result.get('temp_stock_csv')
                    }
                    cleanup_new_products_files(file_paths)
                else:
                    cleanup_new_products_files(None)
            except Exception as e:
                logger.warning(f"Error cleaning up new products files: {e}")
        
        logger.info("Local file processing completed")
    except Exception as e:
        logger.error(f"Error processing local file: {e}")


if __name__ == "__main__":
    """
    Entry point with command line argument support.
    
    Usage:
        python main.py                    # Run automation (check Dropbox)
        python main.py test              # Test connections
        python main.py dropbox           # Dropbox-only mode (same as default)
        python main.py file <path>       # Process local file
    """
    
    if len(sys.argv) == 1:
        # Default: run automation
        main()
    elif len(sys.argv) == 2:
        command = sys.argv[1].lower()
        if command == "test":
            test_connections()
        elif command == "dropbox":
            run_dropbox_only()
        else:
            print("Usage: python main.py [test|dropbox|file <path>]")
            sys.exit(1)
    elif len(sys.argv) == 3 and sys.argv[1].lower() == "file":
        file_path = sys.argv[2]
        process_local_file(file_path)
    else:
        print("Usage: python main.py [test|dropbox|file <path>]")
        sys.exit(1) 