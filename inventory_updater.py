"""
Inventory updater module - core business logic.

This module handles:
- Comparing file products with Holded products
- Detecting price and stock differences
- Generating update requests
- Executing price and stock updates
- Managing the update workflow
"""

from typing import List, Dict, Any, Tuple, Optional
import logging

from file_processor import process_inventory_file
from holded_api import HoldedAPI, get_holded_products


class InventoryUpdater:
    """Handles inventory comparison and update operations."""
    
    def __init__(self):
        """Initialize inventory updater."""
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Initialize Holded API
        self.holded_api = HoldedAPI()
        
        # Track updates for reporting
        self.price_updates = []
        self.stock_updates = []
        self.errors = []
    
    def process_inventory_update(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        Process inventory updates from file(s).
        
        Args:
            file_paths: List of file paths to process
            
        Returns:
            Dictionary containing update results and statistics
        """
        results = {
            'processed_files': 0,
            'processed_products': 0,
            'price_updates': 0,
            'stock_updates': 0,
            'errors': [],
            'details': []
        }
        
        try:
            # Get current Holded products
            self.logger.info("Retrieving products from Holded...")
            holded_products = get_holded_products()
            
            if not holded_products:
                error_msg = "Failed to retrieve products from Holded"
                self.logger.error(error_msg)
                results['errors'].append(error_msg)
                return results
            
            # Create SKU lookup dictionary
            holded_lookup = self._create_sku_lookup(holded_products)
            self.logger.info(f"Loaded {len(holded_lookup)} products from Holded")
            
            # Process each file
            for file_path in file_paths:
                try:
                    file_result = self._process_single_file(file_path, holded_lookup)
                    
                    # Update overall results
                    results['processed_files'] += 1
                    results['processed_products'] += file_result['processed_products']
                    results['price_updates'] += file_result['price_updates']
                    results['stock_updates'] += file_result['stock_updates']
                    results['errors'].extend(file_result['errors'])
                    results['details'].append(file_result)
                    
                except Exception as e:
                    error_msg = f"Error processing file {file_path}: {e}"
                    self.logger.error(error_msg)
                    results['errors'].append(error_msg)
            
            return results
            
        except Exception as e:
            error_msg = f"Error in inventory update process: {e}"
            self.logger.error(error_msg)
            results['errors'].append(error_msg)
            return results
    
    def _process_single_file(self, file_path: str, holded_lookup: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process a single inventory file.
        
        Args:
            file_path: Path to the file to process
            holded_lookup: Dictionary mapping SKUs to Holded products
            
        Returns:
            Dictionary containing processing results for this file
        """
        file_result = {
            'file_path': file_path,
            'processed_products': 0,
            'price_updates': 0,
            'stock_updates': 0,
            'errors': [],
            'skipped_products': []
        }
        
        # Process the file
        self.logger.info(f"Processing file: {file_path}")
        file_products = process_inventory_file(file_path)
        
        if not file_products:
            error_msg = f"No valid products found in file: {file_path}"
            self.logger.error(error_msg)
            file_result['errors'].append(error_msg)
            return file_result
        
        self.logger.info(f"Found {len(file_products)} products in file")
        
        # Process each product
        for product in file_products:
            try:
                sku = product['sku']
                
                # Check if product exists in Holded
                if sku not in holded_lookup:
                    skip_msg = f"SKU not found in Holded: {sku}"
                    self.logger.warning(skip_msg)
                    file_result['skipped_products'].append(skip_msg)
                    continue
                
                holded_product = holded_lookup[sku]
                file_result['processed_products'] += 1
                
                # Check for price differences
                if 'price' in product:
                    price_updated = self._update_price_if_different(
                        holded_product, product['price']
                    )
                    if price_updated:
                        file_result['price_updates'] += 1
                
                # Check for stock differences
                if 'stock' in product:
                    stock_updated = self._update_stock_if_different(
                        holded_product, product['stock']
                    )
                    if stock_updated:
                        file_result['stock_updates'] += 1
                
            except Exception as e:
                error_msg = f"Error processing product {product.get('sku', 'unknown')}: {e}"
                self.logger.error(error_msg)
                file_result['errors'].append(error_msg)
        
        return file_result
    
    def _create_sku_lookup(self, holded_products: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Create a lookup dictionary mapping SKUs to products.
        
        Args:
            holded_products: List of Holded products
            
        Returns:
            Dictionary mapping SKUs to product data
        """
        lookup = {}
        
        for product in holded_products:
            # Try different possible SKU fields
            sku = None
            for sku_field in ['sku', 'code', 'reference', 'item_code']:
                if sku_field in product and product[sku_field]:
                    sku = str(product[sku_field]).strip()
                    break
            
            if sku:
                lookup[sku] = product
        
        return lookup
    
    def _update_price_if_different(self, holded_product: Dict[str, Any], new_price: float) -> bool:
        """
        Update price if it's different from current price.
        
        Args:
            holded_product: Holded product data
            new_price: New price from file
            
        Returns:
            True if price was updated, False otherwise
        """
        try:
            # Get current price from Holded product
            current_price = None
            for price_field in ['price', 'cost', 'amount', 'sell_price']:
                if price_field in holded_product and holded_product[price_field] is not None:
                    current_price = float(holded_product[price_field])
                    break
            
            if current_price is None:
                self.logger.warning(f"No current price found for product {holded_product.get('id')}")
                return False
            
            # Check if prices are different (with small tolerance for floating point)
            price_difference = abs(current_price - new_price)
            if price_difference < 0.01:  # Less than 1 cent difference
                return False
            
            # Determine if this is an offer (price reduction)
            is_offer = new_price < current_price
            
            # Get product ID
            product_id = holded_product.get('id')
            if not product_id:
                self.logger.error("Product ID not found in Holded product")
                return False
            
            # Update the price
            self.logger.info(f"Updating price for product {product_id}: {current_price} -> {new_price}")
            
            success = self.holded_api.update_product_price(
                product_id=str(product_id),
                price=new_price,
                add_offer_tag=is_offer
            )
            
            if success:
                update_info = {
                    'product_id': product_id,
                    'sku': holded_product.get('sku', 'unknown'),
                    'old_price': current_price,
                    'new_price': new_price,
                    'is_offer': is_offer
                }
                self.price_updates.append(update_info)
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error updating price: {e}")
            return False
    
    def _update_stock_if_different(self, holded_product: Dict[str, Any], new_stock: int) -> bool:
        """
        Update stock if it's different from current stock.
        
        Args:
            holded_product: Holded product data
            new_stock: New stock from file
            
        Returns:
            True if stock was updated, False otherwise
        """
        try:
            # Get current stock from Holded product
            current_stock = None
            for stock_field in ['stock', 'quantity', 'inventory', 'units']:
                if stock_field in holded_product and holded_product[stock_field] is not None:
                    current_stock = int(holded_product[stock_field])
                    break
            
            if current_stock is None:
                self.logger.warning(f"No current stock found for product {holded_product.get('id')}")
                return False
            
            # Check if stock is different
            if current_stock == new_stock:
                return False
            
            # Get product ID
            product_id = holded_product.get('id')
            if not product_id:
                self.logger.error("Product ID not found in Holded product")
                return False
            
            # Update the stock
            self.logger.info(f"Updating stock for product {product_id}: {current_stock} -> {new_stock}")
            
            success = self.holded_api.update_product_stock(
                product_id=str(product_id),
                stock=new_stock
            )
            
            if success:
                update_info = {
                    'product_id': product_id,
                    'sku': holded_product.get('sku', 'unknown'),
                    'old_stock': current_stock,
                    'new_stock': new_stock
                }
                self.stock_updates.append(update_info)
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error updating stock: {e}")
            return False
    
    def get_update_summary(self) -> Dict[str, Any]:
        """
        Get summary of all updates performed.
        
        Returns:
            Dictionary containing update summary
        """
        return {
            'price_updates': self.price_updates,
            'stock_updates': self.stock_updates,
            'total_price_updates': len(self.price_updates),
            'total_stock_updates': len(self.stock_updates),
            'errors': self.errors
        }


def update_inventory_from_files(file_paths: List[str]) -> Dict[str, Any]:
    """
    Main function to update inventory from files.
    
    Args:
        file_paths: List of file paths to process
        
    Returns:
        Dictionary containing update results
    """
    updater = InventoryUpdater()
    
    try:
        # Process the inventory updates
        results = updater.process_inventory_update(file_paths)
        
        # Add detailed summary
        summary = updater.get_update_summary()
        results['summary'] = summary
        
        return results
        
    except Exception as e:
        logging.error(f"Error in inventory update: {e}")
        return {
            'processed_files': 0,
            'processed_products': 0,
            'price_updates': 0,
            'stock_updates': 0,
            'errors': [str(e)],
            'details': []
        } 