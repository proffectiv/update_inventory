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
        
    def process_new_products(self, new_products_data: List[Dict[str, Any]]) -> Optional[Dict[str, str]]:
        """
        Process new products through the complete workflow.
        
        Args:
            new_products_data: List of new product dictionaries from inventory updater
            
        Returns:
            Dictionary with file paths {'holded_import': path, 'images_zip': path} or None if failed
        """
        if not new_products_data:
            self.logger.info("No new products to process")
            return None
            
        try:
            self.logger.info(f"Processing {len(new_products_data)} new products")
            
            # Step 1: Create temporary stock CSV file
            temp_stock_csv = self._create_temporary_stock_csv(new_products_data)
            if not temp_stock_csv:
                self.logger.error("Failed to create temporary stock CSV")
                return None
                
            # Step 2: Run transform_products.py to generate Holded import file
            holded_import_file = self._run_transform_products(temp_stock_csv)
            if not holded_import_file:
                self.logger.error("Failed to generate Holded import file")
                return None
                
            # Step 3: Run download_product_images.py to get product images
            images_zip_file = self._run_download_images(holded_import_file)
            # Note: images_zip_file can be None if no images found, this is acceptable
            
            result = {
                'holded_import': holded_import_file,
                'images_zip': images_zip_file,
                'temp_stock_csv': temp_stock_csv
            }
            
            self.logger.info(f"New products processing completed successfully")
            self.logger.info(f"  - Holded import file: {holded_import_file}")
            self.logger.info(f"  - Images ZIP file: {images_zip_file if images_zip_file else 'None (no images found)'}")
            
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
        Run the download_product_images.py script to download product images.
        
        Args:
            holded_import_csv: Path to the Holded import CSV file
            
        Returns:
            Path to generated images ZIP file or None if failed/no images
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
                return zip_path
            else:
                self.logger.warning("No images ZIP file was created (possibly no images found)")
                return None
                
        except Exception as e:
            self.logger.error(f"Error running download_product_images: {e}")
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
        for key, path in file_paths.items():
            if path and os.path.exists(path):
                files_to_cleanup.append(path)
    
    # Also cleanup common temp files
    common_temp_files = [
        'stock_Stocklist_CONWAY.csv',
        'conway_products_holded_import.csv',
        'Importar Productos.csv'
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