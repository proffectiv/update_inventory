"""
New Products Processor Module

This module handles the complete workflow for newly detected products:
1. Creates temporary CSV files with new products data
2. Transforms products using transform_products.py 
3. Downloads product images using download_product_images.py
4. Returns file paths for email attachment
5. Provides cleanup functionality
"""

import os
import pandas as pd
import tempfile
import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path

# Import the existing transform and download scripts
import transform_products
import download_product_images
from holded_api import HoldedAPI
from dropbox_handler import DropboxHandler


class NewProductsProcessor:
    """Handles processing of newly detected products for manual creation."""
    
    def __init__(self):
        """Initialize the processor."""
        self.logger = logging.getLogger(__name__)
        
        # Track temporary files for cleanup
        self.temp_files = []
        
        # Check if required source files exist
        self.info_csv_path = 'Información_EAN_Conway_2025.csv'
        self.template_csv_path = 'Importar Productos.csv'
        
        # Initialize Holded API for variant management
        self.holded_api = HoldedAPI()
        
        # Initialize Dropbox handler for image uploads
        self.dropbox_handler = DropboxHandler()
        
        # Data integrity tracking
        self.data_integrity_issues = []
        self.products_for_deletion = []
        
    def process_new_products(self, new_products_data: List[Dict[str, Any]]) -> Optional[Dict[str, str]]:
        """
        Process new products through the enhanced dual workflow.
        
        Args:
            new_products_data: List of new product dictionaries from inventory updater
            
        Returns:
            Dictionary with file paths and processing results or None if failed
        """
        if not new_products_data:
            self.logger.info("No new products to process")
            return None
            
        try:
            # Separate products by type (new products vs new variants)
            completely_new_products = [p for p in new_products_data if not p.get('is_new_variant', False)]
            new_variants = [p for p in new_products_data if p.get('is_new_variant', False)]
            
            self.logger.info(f"Processing {len(new_products_data)} total products:")
            self.logger.info(f"  - Completely new products: {len(completely_new_products)}")
            self.logger.info(f"  - New variants of existing products: {len(new_variants)}")
            
            # Step 1: Handle new variants (consolidate with existing variants)
            consolidated_products_data = []
            
            if new_variants:
                self.logger.info("Processing new variants - consolidating with existing variants...")
                consolidated_data = self._consolidate_variants_with_existing(new_variants)
                consolidated_products_data.extend(consolidated_data)
                
            # Step 2: Add completely new products
            consolidated_products_data.extend(completely_new_products)
            
            # Step 3: Create temporary stock CSV file with all products
            temp_stock_csv = self._create_temporary_stock_csv(consolidated_products_data)
            if not temp_stock_csv:
                self.logger.error("Failed to create temporary stock CSV")
                return None
                
            # Step 4: Run transform_products.py to generate Holded import file
            holded_import_file, processing_metadata = self._run_transform_products_with_integrity_check(temp_stock_csv, len(consolidated_products_data))
            if not holded_import_file:
                self.logger.error("Failed to generate Holded import file")
                return None
                
            # Step 5: AUTOMATIC DELETION - Delete existing products that need consolidation
            deletion_results = {}
            if self.products_for_deletion:
                self.logger.info(f"Step 5: Executing automatic deletion of {len(self.products_for_deletion)} products...")
                deletion_results = self.execute_automatic_product_deletions()
                
                if deletion_results['failed_deletions'] > 0:
                    self.logger.warning(f"Some deletions failed ({deletion_results['failed_deletions']}/{deletion_results['total_scheduled']})")
                    self.logger.warning("Proceeding with import - manual deletion may be required for failed items")
            else:
                self.logger.info("Step 5: No products scheduled for deletion")
            
            # Step 6: Run download_product_images.py and upload to Dropbox
            images_download_link = self._run_download_images(holded_import_file)
            # Note: images_download_link can be None if no images found, this is acceptable
            
            result = {
                'holded_import': holded_import_file,
                'images_download_link': images_download_link,
                'temp_stock_csv': temp_stock_csv,
                # Enhanced results for email notification
                'completely_new_products': completely_new_products,
                'new_variants_of_existing_products': new_variants,
                'products_for_deletion': self.products_for_deletion,
                'deletion_results': deletion_results,
                'data_integrity_issues': self.data_integrity_issues,
                'processing_metadata': processing_metadata
            }
            
            self.logger.info(f"Enhanced new products processing completed successfully")
            self.logger.info(f"  - Holded import file: {holded_import_file}")
            self.logger.info(f"  - Images download link: {images_download_link if images_download_link else 'None (no images found)'}")
            self.logger.info(f"  - Products scheduled for deletion: {len(self.products_for_deletion)}")
            self.logger.info(f"  - Data integrity issues: {len(self.data_integrity_issues)}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing new products: {e}")
            return None
    
    def _create_temporary_stock_csv(self, new_products_data: List[Dict[str, Any]]) -> Optional[str]:
        """
        Create a temporary CSV file with the Conway stock list structure.
        
        Args:
            new_products_data: List of new product dictionaries
            
        Returns:
            Path to temporary stock CSV file or None if failed
        """
        try:
            # Create temporary file
            temp_fd, temp_path = tempfile.mkstemp(suffix='.csv', prefix='temp_stock_conway_')
            os.close(temp_fd)  # Close the file descriptor, we'll write using pandas
            
            self.temp_files.append(temp_path)
            
            # Define the expected structure for the stock CSV based on transform_products.py requirements
            stock_data = []
            
            for product in new_products_data:
                # Extract basic product info
                sku = str(product.get('sku', ''))
                name = product.get('name', f'Producto {sku}')  # Use name or fallback to SKU-based name
                stock_qty = product.get('stock', 0)
                
                # Extract Conway-specific data from the original stock file processing
                size = product.get('size', 'M')  # Use actual size from file, default to M if not found
                color = product.get('color', 'Standard')  # Use actual color from file, default if not found
                if product.get('ws') == '29.0':
                    ws = '29'
                elif product.get('ws') == '28.0':
                    ws = '28'
                elif product.get('ws') == '27.0':
                    ws = '27.5'
                else:
                    ws = '29'  # Use actual wheel size from file, default to 29 if not found
                
                # Log for debugging to verify we're getting real data
                self.logger.debug(f"Processing product {sku}: size='{size}', color='{color}', ws='{ws}'")
                
                # Create a Conway-style stock record
                # The transform script expects columns like: Item, Name, Stock qty, size, color, ws
                stock_record = {
                    'Item': sku,
                    'Name': name,
                    'Stock qty': stock_qty,
                    'size': size,    # Now using real data from stock file
                    'color': color,  # Now using real data from stock file
                    'ws': ws         # Now using real data from stock file
                }
                
                stock_data.append(stock_record)
            
            # Create DataFrame and save as CSV
            stock_df = pd.DataFrame(stock_data)
            stock_df.to_csv(temp_path, index=False, encoding='utf-8')
            
            self.logger.info(f"Created temporary stock CSV with {len(stock_data)} products using real Conway data: {temp_path}")
            
            # Log sample of data for verification
            if stock_data:
                sample = stock_data[0]
                self.logger.info(f"Sample product data - SKU: {sample['Item']}, Size: {sample['size']}, Color: {sample['color']}, WS: {sample['ws']}")
            
            # Copy to expected filename for transform_products.py
            expected_path = 'stock_Stocklist_CONWAY.csv'
            stock_df.to_csv(expected_path, index=False, encoding='utf-8')
            self.temp_files.append(expected_path)
            
            self.logger.info(f"Saved stock file as: {expected_path}")
            return expected_path
            
        except Exception as e:
            self.logger.error(f"Error creating temporary stock CSV: {e}")
            return None
    
    def _run_transform_products(self, stock_csv_path: str) -> Optional[str]:
        """
        Run the transform_products.py script to generate Holded import file.
        
        Args:
            stock_csv_path: Path to the temporary stock CSV file
            
        Returns:
            Path to generated Holded import CSV file or None if failed
        """
        try:
            # Check if required files exist
            if not os.path.exists(self.info_csv_path):
                self.logger.error(f"Required file not found: {self.info_csv_path}")
                return None
                
            # Create a minimal template file if it doesn't exist
            if not os.path.exists(self.template_csv_path):
                self._create_minimal_template()
                
            # Call the main function from transform_products module
            self.logger.info("Running transform_products to generate Holded import file...")
            
            # The transform_products.main() function will create 'conway_products_holded_import.csv'
            output_df = transform_products.main()
            
            expected_output = 'conway_products_holded_import.csv'
            if os.path.exists(expected_output):
                self.temp_files.append(expected_output)
                self.logger.info(f"Transform products completed successfully: {expected_output}")
                return expected_output
            else:
                self.logger.error("Transform products did not create expected output file")
                return None
                
        except Exception as e:
            self.logger.error(f"Error running transform_products: {e}")
            return None
    
    def _run_download_images(self, holded_import_csv: str) -> Optional[str]:
        """
        Run the download_product_images.py script and upload images to Dropbox.
        
        Args:
            holded_import_csv: Path to the Holded import CSV file
            
        Returns:
            Dropbox download link for images ZIP file or None if failed/no images
        """
        try:
            self.logger.info("Running download_product_images to download product images...")
            
            # Create the downloader instance
            downloader = download_product_images.ConwayImageDownloader(
                csv_file=holded_import_csv,
                info_csv=self.info_csv_path
            )
            
            # Process all products and get ZIP path
            zip_path = downloader.process_all_products()
            
            if zip_path and os.path.exists(zip_path):
                self.temp_files.append(zip_path)
                
                # Also track the images directory for cleanup
                images_dir = downloader.images_dir
                if images_dir.exists():
                    self.temp_files.append(str(images_dir))
                
                self.logger.info(f"Image download completed successfully: {zip_path}")
                
                # Upload to Dropbox and get download link
                dropbox_path = "/stock-update/stock_conway_product_images.zip"
                
                self.logger.info(f"Uploading images ZIP to Dropbox: {dropbox_path}")
                upload_success = self.dropbox_handler.upload_file(zip_path, dropbox_path, overwrite=True)
                
                if upload_success:
                    # Generate shareable download link
                    download_link = self.dropbox_handler.generate_shareable_link(dropbox_path)
                    
                    if download_link:
                        self.logger.info(f"Images uploaded successfully to Dropbox. Download link generated: {download_link}")
                        return download_link
                    else:
                        self.logger.error("Failed to generate download link for uploaded images")
                        # Return a fallback message indicating upload success but no link
                        return "UPLOADED_NO_LINK"
                else:
                    self.logger.error("Failed to upload images ZIP to Dropbox")
                    return None
                    
            else:
                self.logger.warning("No images ZIP file was created (possibly no images found)")
                return None
                
        except Exception as e:
            self.logger.error(f"Error processing images for Dropbox upload: {e}")
            return None
    
    def _create_minimal_template(self):
        """Create a minimal template CSV file if it doesn't exist."""
        try:
            # Define the expected columns for Holded import based on transform_products.py
            template_columns = [
                'SKU', 'Nombre', 'Descripción', 'Código de barras', 'Código de fábrica',
                'Talla', 'Color', 'Medida de la Rueda', 'Tipo de Bici', 'Forma del Cuadro',
                'Sku Variante', 'Código barras Variante', 'cat - Cycplus', 'cat - DARE',
                'cat - Conway', 'cat - Kogel', 'Coste (Subtotal)', 'Precio compra (Subtotal)',
                'Precio venta (Subtotal)', 'Impuesto de venta', 'Impuesto de compras',
                'Stock', 'Peso', 'Fecha de inicio dd/mm/yyyy', 'Tags separados por -',
                'Proveedor (Código)', 'Cuenta ventas', 'Cuenta compras', 'Almacén'
            ]
            
            # Create empty template DataFrame
            template_df = pd.DataFrame(columns=template_columns)
            template_df.to_csv(self.template_csv_path, index=False)
            self.temp_files.append(self.template_csv_path)
            
            self.logger.info(f"Created minimal template file: {self.template_csv_path}")
            
        except Exception as e:
            self.logger.error(f"Error creating minimal template: {e}")
    
    def _consolidate_variants_with_existing(self, new_variants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Consolidate new variants with existing variants from Holded.
        
        Args:
            new_variants: List of new variant dictionaries
            
        Returns:
            List of all variants (existing + new) for the products
        """
        consolidated_data = []
        processed_products = set()  # Track processed product names
        
        for new_variant in new_variants:
            product_name = new_variant.get('name', '')
            
            if product_name in processed_products:
                # Already processed this product, just add this variant
                consolidated_data.append(new_variant)
                continue
                
            # First variant of this product - get all existing variants
            try:
                existing_variants = self.holded_api.get_all_variants_by_product_name(product_name)
                
                if existing_variants:
                    self.logger.info(f"Found {len(existing_variants)} existing variants for '{product_name}'")
                    
                    # Schedule existing product for deletion (will be re-imported with all variants)
                    main_product_id = existing_variants[0].get('_main_product_id')
                    if main_product_id:
                        self.products_for_deletion.append({
                            'product_id': str(main_product_id),
                            'product_name': product_name,
                            'existing_variants_count': len(existing_variants),
                            'action': 'delete_for_reimport'
                        })
                    
                    # Convert existing variants to our format
                    for existing_variant in existing_variants:
                        variant_data = existing_variant.get('_variant_data', {})
                        
                        # Extract variant details
                        size = ''
                        color = ''
                        ws = ''
                        
                        if 'categoryFields' in variant_data:
                            for field in variant_data['categoryFields']:
                                field_name = field.get('name', '').lower()
                                field_value = field.get('field', '')
                                
                                if 'talla' in field_name or 'size' in field_name:
                                    size = field_value
                                elif 'color' in field_name:
                                    color = field_value
                                elif 'rueda' in field_name or 'wheel' in field_name:
                                    ws = field_value
                        
                        existing_as_new_format = {
                            'sku': existing_variant.get('_variant_sku', ''),
                            'stock': existing_variant.get('stock', 0),
                            'price': existing_variant.get('price', 0),
                            'name': product_name,
                            'is_offer': False,  # Assume false for existing
                            'source_file': 'holded_existing',
                            'size': size,
                            'color': color,
                            'ws': ws,
                            'is_new_variant': False,  # Mark as existing
                            '_from_holded': True  # Special flag
                        }
                        
                        consolidated_data.append(existing_as_new_format)
                    
                    self.logger.info(f"Added {len(existing_variants)} existing variants for '{product_name}' to consolidation")
                
                # Add all new variants for this product
                product_new_variants = [v for v in new_variants if v.get('name') == product_name]
                consolidated_data.extend(product_new_variants)
                
                self.logger.info(f"Consolidated '{product_name}': {len(existing_variants)} existing + {len(product_new_variants)} new = {len(existing_variants) + len(product_new_variants)} total variants")
                
                processed_products.add(product_name)
                
            except Exception as e:
                self.logger.error(f"Error consolidating variants for '{product_name}': {e}")
                # Fallback: just add the new variant
                consolidated_data.append(new_variant)
        
        return consolidated_data
    
    def _run_transform_products_with_integrity_check(self, stock_csv_path: str, expected_input_count: int) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Run transform_products.py with data integrity monitoring.
        
        Args:
            stock_csv_path: Path to the stock CSV file
            expected_input_count: Expected number of input products
            
        Returns:
            Tuple of (output_file_path, metadata_dict)
        """
        processing_metadata = {
            'input_products': expected_input_count,
            'output_products': 0,
            'failed_lookups': [],
            'success_rate': 0.0
        }
        
        try:
            # Run the enhanced transform function to get metadata
            output_file = self._run_transform_products(stock_csv_path)
            
            # Get processing metadata from transform_products
            transform_metadata = transform_products.get_last_processing_metadata()
            if transform_metadata:
                # Merge transform metadata with our metadata
                processing_metadata.update(transform_metadata)
            
            if output_file and os.path.exists(output_file):
                # Count products in output CSV
                output_df = pd.read_csv(output_file)
                output_count = len(output_df)
                processing_metadata['output_products'] = output_count
                
                # Calculate success rate
                if expected_input_count > 0:
                    processing_metadata['success_rate'] = (output_count / expected_input_count) * 100
                
                # Identify missing products (data integrity issues)
                if output_count < expected_input_count:
                    missing_count = expected_input_count - output_count
                    self.logger.warning(f"Data integrity issue: {missing_count} products missing from output CSV")
                    
                    # Try to identify which products failed
                    # This would require comparing input vs output SKUs
                    input_df = pd.read_csv(stock_csv_path)
                    input_skus = set(input_df['Item'].astype(str))
                    output_skus = set(output_df['Sku Variante'].astype(str))
                    
                    missing_skus = input_skus - output_skus
                    
                    for sku in missing_skus:
                        input_row = input_df[input_df['Item'].astype(str) == sku]
                        if len(input_row) > 0:
                            failed_product = {
                                'sku': sku,
                                'name': input_row.iloc[0]['Name'] if 'Name' in input_row.columns else 'Unknown',
                                'reason': 'Missing from transform_products.py output - likely EAN lookup failure'
                            }
                            self.data_integrity_issues.append(failed_product)
                            processing_metadata['failed_lookups'].append(failed_product)
                
                self.logger.info(f"Transform products integrity check: {output_count}/{expected_input_count} products ({processing_metadata['success_rate']:.1f}% success rate)")
                
                return output_file, processing_metadata
            else:
                self.logger.error("Transform products failed - no output file created")
                return None, processing_metadata
                
        except Exception as e:
            self.logger.error(f"Error in transform products with integrity check: {e}")
            return None, processing_metadata

    def execute_automatic_product_deletions(self) -> Dict[str, Any]:
        """
        Automatically delete products scheduled for deletion from Holded.
        
        Returns:
            Dictionary with deletion results and statistics
        """
        deletion_results = {
            'total_scheduled': len(self.products_for_deletion),
            'successful_deletions': 0,
            'failed_deletions': 0,
            'deletion_details': [],
            'errors': []
        }
        
        if not self.products_for_deletion:
            self.logger.info("No products scheduled for deletion")
            return deletion_results
        
        self.logger.info(f"Starting automatic deletion of {len(self.products_for_deletion)} products...")
        
        for product_info in self.products_for_deletion:
            product_id = product_info.get('product_id')
            product_name = product_info.get('product_name', 'Unknown')
            variants_count = product_info.get('existing_variants_count', 0)
            
            try:
                self.logger.info(f"Deleting product: {product_name} (ID: {product_id}) with {variants_count} variants...")
                
                # Execute deletion using Holded API
                success = self.holded_api.delete_product_with_variants(product_id)
                
                if success:
                    deletion_results['successful_deletions'] += 1
                    deletion_results['deletion_details'].append({
                        'product_id': product_id,
                        'product_name': product_name,
                        'variants_count': variants_count,
                        'status': 'success'
                    })
                    self.logger.info(f"✅ Successfully deleted {product_name} ({product_id})")
                else:
                    deletion_results['failed_deletions'] += 1
                    error_msg = f"Failed to delete {product_name} ({product_id})"
                    deletion_results['errors'].append(error_msg)
                    deletion_results['deletion_details'].append({
                        'product_id': product_id,
                        'product_name': product_name,
                        'variants_count': variants_count,
                        'status': 'failed'
                    })
                    self.logger.error(f"❌ {error_msg}")
                    
            except Exception as e:
                deletion_results['failed_deletions'] += 1
                error_msg = f"Exception deleting {product_name} ({product_id}): {e}"
                deletion_results['errors'].append(error_msg)
                deletion_results['deletion_details'].append({
                    'product_id': product_id,
                    'product_name': product_name,
                    'variants_count': variants_count,
                    'status': 'error',
                    'error': str(e)
                })
                self.logger.error(f"💥 {error_msg}")
        
        # Log summary
        success_rate = (deletion_results['successful_deletions'] / deletion_results['total_scheduled'] * 100) if deletion_results['total_scheduled'] > 0 else 0
        self.logger.info(f"Automatic deletion completed:")
        self.logger.info(f"  - Total scheduled: {deletion_results['total_scheduled']}")
        self.logger.info(f"  - Successful: {deletion_results['successful_deletions']}")
        self.logger.info(f"  - Failed: {deletion_results['failed_deletions']}")
        self.logger.info(f"  - Success rate: {success_rate:.1f}%")
        
        return deletion_results

    def cleanup_temp_files(self):
        """Clean up all temporary files created during processing."""
        cleanup_count = 0
        
        for file_path in self.temp_files:
            try:
                if os.path.exists(file_path):
                    if os.path.isdir(file_path):
                        # Remove directory and contents
                        import shutil
                        shutil.rmtree(file_path)
                        self.logger.info(f"Cleaned up directory: {file_path}")
                    else:
                        # Remove file
                        os.remove(file_path)
                        self.logger.info(f"Cleaned up file: {file_path}")
                    cleanup_count += 1
                        
            except Exception as e:
                self.logger.warning(f"Could not clean up {file_path}: {e}")
        
        self.logger.info(f"Cleaned up {cleanup_count} temporary files/directories")
        self.temp_files.clear()


def process_new_products_workflow(new_products_data: List[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """
    Main function to process new products workflow.
    
    Args:
        new_products_data: List of new product dictionaries from inventory updater
        
    Returns:
        Dictionary with file paths for email attachment or None if failed
    """
    processor = NewProductsProcessor()
    
    try:
        # Process the new products
        result = processor.process_new_products(new_products_data)
        
        # Note: Don't cleanup here - let the main workflow handle cleanup after email is sent
        return result
        
    except Exception as e:
        logging.error(f"Error in new products workflow: {e}")
        # Clean up on error
        processor.cleanup_temp_files()
        return None


def cleanup_new_products_files(file_paths: Dict[str, str]):
    """
    Clean up new products files after email is sent.
    
    Args:
        file_paths: Dictionary with file paths from process_new_products_workflow
    """
    logger = logging.getLogger(__name__)
    
    files_to_cleanup = []
    if file_paths:
        # Add all file paths to cleanup list
        for path in file_paths.values():
            if path and os.path.exists(path):
                files_to_cleanup.append(path)
    
    # Also cleanup common temp files
    common_temp_files = [
        'stock_Stocklist_CONWAY.csv',
        'conway_products_holded_import.csv',
        'Importar Productos.csv'
        'product_images'
    ]
    
    for file_path in common_temp_files:
        if os.path.exists(file_path):
            files_to_cleanup.append(file_path)
    
    # Cleanup files
    cleanup_count = 0
    for file_path in files_to_cleanup:
        try:
            if os.path.exists(file_path):
                if os.path.isdir(file_path):
                    import shutil
                    shutil.rmtree(file_path)
                else:
                    os.remove(file_path)
                cleanup_count += 1
                logger.info(f"Cleaned up: {file_path}")
        except Exception as e:
            logger.warning(f"Could not clean up {file_path}: {e}")
    
    logger.info(f"New products cleanup completed: {cleanup_count} files/directories removed")