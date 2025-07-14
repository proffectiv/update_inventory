"""
File processor module for parsing CSV and Excel files.

This module handles:
- Reading CSV and Excel files
- Extracting SKU, price, and stock information
- Validating data format
- Converting data to standardized format
"""

import pandas as pd
import os
from typing import List, Dict, Optional, Any
import logging

from config import config


class FileProcessor:
    """Handles processing of CSV and Excel files."""
    
    def __init__(self):
        """Initialize file processor."""
        self.allowed_extensions = config.allowed_extensions
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Common column name variations for auto-detection
        # Updated to include Conway-specific columns
        self.sku_columns = ['sku', 'codigo', 'code', 'product_code', 'item_code', 'ref', 'item']
        self.price_columns = ['price', 'precio', 'cost', 'coste', 'amount', 'importe', 'evp']
        self.offer_columns = ['oferta', 'offer', 'special_price', 'promo_price']
        self.stock_columns = ['stock', 'quantity', 'cantidad', 'units', 'unidades', 'inventory', 'stock qty']
    
    def process_file(self, file_path: str) -> Optional[List[Dict[str, Any]]]:
        """
        Process a file and extract product data.
        
        Args:
            file_path: Path to the file to process
            
        Returns:
            List of product dictionaries with SKU, price, and stock
        """
        if not os.path.exists(file_path):
            self.logger.error(f"File not found: {file_path}")
            return None
        
        # Get file extension
        file_extension = file_path.lower().split('.')[-1]
        
        if file_extension not in self.allowed_extensions:
            self.logger.error(f"Unsupported file extension: {file_extension}")
            return None
        
        try:
            # Read file based on extension
            if file_extension == 'csv':
                df = self._read_csv_file(file_path)
            elif file_extension in ['xlsx', 'xls']:
                df = self._read_excel_file(file_path)
            else:
                self.logger.error(f"Unsupported file extension: {file_extension}")
                return None
            
            if df is None or df.empty:
                self.logger.error("No data found in file")
                return None
            
            # Process and standardize data
            products = self._extract_product_data(df)
            
            self.logger.info(f"Processed {len(products)} products from file: {os.path.basename(file_path)}")
            return products
            
        except Exception as e:
            self.logger.error(f"Error processing file {file_path}: {e}")
            return None
    
    def _read_csv_file(self, file_path: str) -> Optional[pd.DataFrame]:
        """
        Read CSV file with various encoding attempts.
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            DataFrame or None if failed
        """
        encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
        
        for encoding in encodings:
            try:
                df = pd.read_csv(file_path, encoding=encoding)
                self.logger.info(f"Successfully read CSV with encoding: {encoding}")
                return df
            except UnicodeDecodeError:
                continue
            except Exception as e:
                self.logger.error(f"Error reading CSV file: {e}")
                return None
        
        self.logger.error("Could not read CSV file with any supported encoding")
        return None
    
    def _read_excel_file(self, file_path: str) -> Optional[pd.DataFrame]:
        """
        Read Excel file.
        
        Args:
            file_path: Path to Excel file
            
        Returns:
            DataFrame or None if failed
        """
        try:
            # Try to read the first sheet
            df = pd.read_excel(file_path, sheet_name=0)
            self.logger.info("Successfully read Excel file")
            return df
        except Exception as e:
            self.logger.error(f"Error reading Excel file: {e}")
            return None
    
    def _extract_product_data(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Extract product data from DataFrame.
        
        Args:
            df: DataFrame containing product data
            
        Returns:
            List of product dictionaries
        """
        # Clean column names (remove spaces, convert to lowercase)
        df.columns = df.columns.str.strip().str.lower()
        
        # Auto-detect column mappings
        sku_col = self._find_column(df, self.sku_columns)
        price_col = self._find_column(df, self.price_columns)
        offer_col = self._find_column(df, self.offer_columns)
        stock_col = self._find_column(df, self.stock_columns)
        
        if not sku_col:
            self.logger.error("Could not find SKU column in file")
            return []
        
        self.logger.info(f"Column mappings - SKU: {sku_col}, Price: {price_col}, Offer: {offer_col}, Stock: {stock_col}")
        
        products = []
        
        for index, row in df.iterrows():
            try:
                # Extract SKU (required)
                sku = str(row[sku_col]).strip()
                if not sku or sku.lower() in ['nan', 'none', '']:
                    continue
                
                # Clean up SKU format - remove .0 from numeric SKUs
                if sku.endswith('.0') and sku[:-2].isdigit():
                    sku = sku[:-2]
                
                product = {'sku': sku}
                
                # Extract price - prioritize offer price if available
                final_price = None
                is_offer = False
                
                # Check for offer price first
                if offer_col and pd.notna(row[offer_col]):
                    try:
                        # Clean offer price value
                        offer_str = str(row[offer_col]).replace('€', '').replace('$', '').replace(',', '.').strip()
                        # Skip dash/hyphen values that indicate no price
                        if offer_str and offer_str.lower() not in ['nan', 'none', ''] and not offer_str.replace('-', '').replace(' ', '') == '':
                            final_price = float(offer_str)
                            is_offer = True
                    except (ValueError, TypeError):
                        self.logger.warning(f"Invalid offer price format for SKU {sku}: {row[offer_col]}")
                
                # If no offer price, use regular price
                if final_price is None and price_col and pd.notna(row[price_col]):
                    try:
                        # Clean price value (remove currency symbols, etc.)
                        price_str = str(row[price_col]).replace('€', '').replace('$', '').replace(',', '.').strip()
                        # Handle formats like "  4.499,95 € "
                        price_str = price_str.replace(' ', '').replace('.', '', price_str.count('.') - 1 if price_str.count('.') > 1 else 0)
                        # Skip dash/hyphen values that indicate no price
                        if price_str and price_str.lower() not in ['nan', 'none', ''] and not price_str.replace('-', '').replace(' ', '') == '':
                            final_price = float(price_str)
                    except (ValueError, TypeError):
                        self.logger.warning(f"Invalid price format for SKU {sku}: {row[price_col]}")
                
                if final_price is not None:
                    product['price'] = final_price
                    product['is_offer'] = is_offer
                
                # Extract stock (optional)
                if stock_col and pd.notna(row[stock_col]):
                    try:
                        stock_str = str(row[stock_col]).strip()
                        
                        # Handle ">10" format - convert to 10
                        if stock_str.startswith('>'):
                            stock = 10
                        elif stock_str.lower() in ['nan', 'none', '']:
                            continue
                        else:
                            stock = int(float(stock_str))
                        
                        product['stock'] = stock
                    except (ValueError, TypeError):
                        self.logger.warning(f"Invalid stock format for SKU {sku}: {row[stock_col]}")
                
                # Only add product if it has SKU and at least price or stock
                if len(product) > 1:  # More than just SKU
                    products.append(product)
                
            except Exception as e:
                self.logger.warning(f"Error processing row {index}: {e}")
                continue
        
        self.logger.info(f"Extracted {len(products)} valid products from file")
        return products
    
    def _find_column(self, df: pd.DataFrame, possible_names: List[str]) -> Optional[str]:
        """
        Find a column by checking various possible names.
        
        Args:
            df: DataFrame to search
            possible_names: List of possible column names
            
        Returns:
            Actual column name if found, None otherwise
        """
        columns = [col.lower() for col in df.columns]
        
        for possible_name in possible_names:
            if possible_name in columns:
                # Return the original column name (with original case)
                original_index = columns.index(possible_name)
                return df.columns[original_index]
        
        return None
    
    def validate_products(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate and clean product data.
        
        Args:
            products: List of product dictionaries
            
        Returns:
            List of validated product dictionaries
        """
        validated_products = []
        
        for product in products:
            # Check required fields
            if 'sku' not in product or not product['sku']:
                continue
            
            # Validate price if present
            if 'price' in product:
                if not isinstance(product['price'], (int, float)) or product['price'] < 0:
                    self.logger.warning(f"Invalid price for SKU {product['sku']}: {product['price']}")
                    del product['price']
            
            # Validate stock if present
            if 'stock' in product:
                if not isinstance(product['stock'], int) or product['stock'] < 0:
                    self.logger.warning(f"Invalid stock for SKU {product['sku']}: {product['stock']}")
                    del product['stock']
            
            # Only keep products with at least price or stock
            if 'price' in product or 'stock' in product:
                validated_products.append(product)
        
        self.logger.info(f"Validated {len(validated_products)} products out of {len(products)}")
        return validated_products


def process_inventory_file(file_path: str) -> Optional[List[Dict[str, Any]]]:
    """
    Main function to process an inventory file.
    
    Args:
        file_path: Path to the file to process
        
    Returns:
        List of product dictionaries or None if failed
    """
    processor = FileProcessor()
    
    try:
        # Process the file
        products = processor.process_file(file_path)
        
        if not products:
            logging.error(f"No products found in file: {file_path}")
            return None
        
        # Validate the products
        validated_products = processor.validate_products(products)
        
        return validated_products
        
    except Exception as e:
        logging.error(f"Error processing inventory file: {e}")
        return None 