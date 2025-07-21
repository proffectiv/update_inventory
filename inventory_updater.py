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
        
        # Process each product individually
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
                
                # Check for stock differences only
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
        Enhanced to handle product variants - searches both main product SKUs and variant SKUs.
        
        Args:
            holded_products: List of Holded products
            
        Returns:
            Dictionary mapping SKUs to product data (includes variant info if applicable)
        """
        lookup = {}
        skipped_products = 0
        variant_skus_found = 0
        
        for product in holded_products:
            # First, try to get SKU from main product - expanded list for better matching
            main_sku = None
            for sku_field in ['sku', 'code', 'reference', 'item_code', 'product_code', 'ref', 'item', 'codigo']:
                if sku_field in product and product[sku_field]:
                    main_sku = str(product[sku_field]).strip()
                    break
            
            # Add main product SKU to lookup if found
            if main_sku:
                lookup[main_sku] = {
                    **product,  # Copy all product data
                    '_is_variant': False,  # Mark as main product
                    '_variant_id': None
                }
                self.logger.debug(f"Added main product SKU: {main_sku}")
            
            # Check for variants - handle both 'variants' and 'attributes' structures
            variants_found = False
            
            # Handle products with 'variants' array (like Cairon 529 SE)
            if 'variants' in product and isinstance(product['variants'], list):
                for variant in product['variants']:
                    if isinstance(variant, dict):
                        # Look for SKU in variant
                        variant_sku = None
                        for sku_field in ['sku', 'code', 'reference', 'item_code', 'ref']:
                            if sku_field in variant and variant[sku_field]:
                                variant_sku = str(variant[sku_field]).strip()
                                break
                        
                        if variant_sku:
                            # Create combined product+variant data for variant SKU
                            variant_product_data = {
                                **product,  # Start with main product data
                                # Override with variant-specific data
                                'price': variant.get('price', product.get('price')),
                                'cost': variant.get('cost', product.get('cost')),
                                'purchasePrice': variant.get('purchasePrice', product.get('purchasePrice')),
                                'stock': variant.get('stock', product.get('stock')),
                                'barcode': variant.get('barcode', product.get('barcode')),
                                # Add variant metadata
                                '_is_variant': True,
                                '_variant_id': variant.get('id'),
                                '_variant_data': variant,
                                '_main_product_id': product.get('id'),
                                '_variant_sku': variant_sku
                            }
                            
                            lookup[variant_sku] = variant_product_data
                            variant_skus_found += 1
                            variants_found = True
                            
                            # Log variant details for debugging
                            variant_details = []
                            if 'categoryFields' in variant:
                                for field in variant['categoryFields']:
                                    if 'name' in field and 'field' in field:
                                        variant_details.append(f"{field['name']}: {field['field']}")
                            
                            self.logger.debug(f"Added variant SKU: {variant_sku} ({', '.join(variant_details)})")
            
            # Handle products with 'attributes' structure (simpler variants)
            elif 'attributes' in product and isinstance(product['attributes'], list):
                # For products with attributes, we already have the main SKU
                # The attributes are more like product properties than separate variants
                variants_found = True
            
            # Track products without valid SKU
            if not main_sku and not variants_found:
                skipped_products += 1
        
        # Enhanced logging
        main_product_skus = sum(1 for v in lookup.values() if not v.get('_is_variant', True))
        
        self.logger.info(f"Created SKU lookup with {len(lookup)} total SKUs:")
        self.logger.info(f"  - Main product SKUs: {main_product_skus}")
        self.logger.info(f"  - Variant SKUs: {variant_skus_found}")
        self.logger.info(f"  - Skipped products without valid SKU: {skipped_products}")
        
        # Log some sample SKUs for debugging
        if lookup:
            sample_skus = list(lookup.keys())[:5]
            self.logger.info(f"Sample Holded SKUs: {sample_skus}")
            
            # Show breakdown of main vs variant SKUs in sample
            for sku in sample_skus[:3]:
                product_data = lookup[sku]
                if product_data.get('_is_variant'):
                    self.logger.info(f"  - {sku}: VARIANT of '{product_data.get('name', 'Unknown')}'")
                else:
                    self.logger.info(f"  - {sku}: MAIN product '{product_data.get('name', 'Unknown')}'")
        
        return lookup
    
    
    def _update_stock_if_different(self, holded_product: Dict[str, Any], new_stock: int) -> bool:
        """
        Update stock if it's different from current stock.
        Enhanced to handle both main products and product variants.
        
        Args:
            holded_product: Holded product data (may include variant data)
            new_stock: New stock from file
            
        Returns:
            True if stock was updated, False otherwise
        """
        try:
            # Determine if this is a variant or main product
            is_variant = holded_product.get('_is_variant', False)
            
            # Get current stock from appropriate source
            current_stock = None
            if is_variant:
                # For variants, use variant-specific stock data
                variant_data = holded_product.get('_variant_data', {})
                for stock_field in ['stock', 'quantity', 'inventory', 'units']:
                    if stock_field in variant_data and variant_data[stock_field] is not None:
                        current_stock = int(variant_data[stock_field])
                        break
                
                # Fallback to main product stock if variant doesn't have stock
                if current_stock is None:
                    for stock_field in ['stock', 'quantity', 'inventory', 'units']:
                        if stock_field in holded_product and holded_product[stock_field] is not None:
                            current_stock = int(holded_product[stock_field])
                            break
            else:
                # For main products, use main product stock
                for stock_field in ['stock', 'quantity', 'inventory', 'units']:
                    if stock_field in holded_product and holded_product[stock_field] is not None:
                        current_stock = int(holded_product[stock_field])
                        break
            
            if current_stock is None:
                product_name = holded_product.get('name', 'Unknown')
                sku = holded_product.get('_variant_sku' if is_variant else 'sku', 'Unknown')
                self.logger.warning(f"No current stock found for {'variant' if is_variant else 'product'} {product_name} (SKU: {sku})")
                return False
            
            # Check if stock is different
            if current_stock == new_stock:
                return False
            
            # Get the appropriate product/variant ID for the update
            if is_variant:
                # For variants, we need both the main product ID and variant ID
                main_product_id = holded_product.get('_main_product_id')
                variant_id = holded_product.get('_variant_id')
                
                if not main_product_id or not variant_id:
                    self.logger.error("Main product ID or variant ID not found in variant product data")
                    return False
                
                # Log variant-specific info
                variant_details = []
                if '_variant_data' in holded_product and 'categoryFields' in holded_product['_variant_data']:
                    for field in holded_product['_variant_data']['categoryFields']:
                        if 'name' in field and 'field' in field:
                            variant_details.append(f"{field['name']}: {field['field']}")
                
                variant_info = f" ({', '.join(variant_details)})" if variant_details else ""
                self.logger.info(f"Updating stock for VARIANT {variant_id}{variant_info}: {current_stock} -> {new_stock}")
                
                # Update the stock using main product ID and variant ID
                success = self.holded_api.update_product_stock(
                    product_id=str(main_product_id),
                    new_stock=new_stock,
                    current_stock=current_stock,
                    variant_id=str(variant_id)
                )
                
            else:
                # For main products, use main product ID
                update_id = holded_product.get('id')
                if not update_id:
                    self.logger.error("Product ID not found in Holded product")
                    return False
                
                self.logger.info(f"Updating stock for MAIN PRODUCT {update_id}: {current_stock} -> {new_stock}")
                
                # Update the stock - standard main product update
                success = self.holded_api.update_product_stock(
                    product_id=str(update_id),
                    new_stock=new_stock,
                    current_stock=current_stock
                )
            
            if success:
                # Use appropriate ID for tracking
                tracking_id = variant_id if is_variant else update_id
                
                update_info = {
                    'product_id': tracking_id,
                    'sku': holded_product.get('_variant_sku' if is_variant else 'sku', 'unknown'),
                    'product_name': holded_product.get('name', 'Unknown'),
                    'is_variant': is_variant,
                    'old_stock': current_stock,
                    'new_stock': new_stock
                }
                
                # Add variant details if applicable
                if is_variant and '_variant_data' in holded_product:
                    variant_data = holded_product['_variant_data']
                    if 'categoryFields' in variant_data:
                        variant_info = {}
                        for field in variant_data['categoryFields']:
                            if 'name' in field and 'field' in field:
                                variant_info[field['name']] = field['field']
                        update_info['variant_details'] = variant_info
                
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
            'stock_updates': self.stock_updates,
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
            'stock_updates': 0,
            'errors': [str(e)],
            'details': []
        } 