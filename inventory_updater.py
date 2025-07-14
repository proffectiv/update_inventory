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
        self.variant_warnings = []  # Track variant warnings separately
    
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
                    
                    # Collect variant warnings
                    if 'variant_warnings' in file_result:
                        self.variant_warnings.extend(file_result['variant_warnings'])
                    
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
            'skipped_products': [],
            'variant_warnings': []  # New: Track variant price conflicts
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
        
        # Group products by main product ID to handle variants correctly
        main_product_groups = self._group_products_by_main_id(file_products, holded_lookup)
        
        # Process each group
        for main_product_id, group_data in main_product_groups.items():
            try:
                # Process price updates for this product group
                price_result = self._process_product_group_prices(group_data, file_result)
                if price_result:
                    file_result['price_updates'] += 1
                
                # Process stock updates for each product in the group
                for product_data in group_data['products']:
                    product = product_data['file_product']
                    holded_product = product_data['holded_product']
                    
                    file_result['processed_products'] += 1
                    
                    # Check for stock differences
                    if 'stock' in product:
                        stock_updated = self._update_stock_if_different(
                            holded_product, product['stock']
                        )
                        if stock_updated:
                            file_result['stock_updates'] += 1
                
            except Exception as e:
                error_msg = f"Error processing product group {main_product_id}: {e}"
                self.logger.error(error_msg)
                file_result['errors'].append(error_msg)
        
        # Process any remaining individual products (non-variants)
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
                
                # Skip if already processed as part of a variant group
                main_product_id = holded_product.get('_main_product_id') or holded_product.get('id')
                if main_product_id in main_product_groups:
                    continue
                
                file_result['processed_products'] += 1
                
                # Check for price differences
                if 'price' in product:
                    price_updated = self._update_price_if_different(
                        holded_product, product
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
    
    def _group_products_by_main_id(self, file_products: List[Dict[str, Any]], holded_lookup: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Group file products by their main product ID to handle variants correctly.
        
        Args:
            file_products: List of products from the file
            holded_lookup: Dictionary mapping SKUs to Holded products
            
        Returns:
            Dictionary mapping main product IDs to grouped product data
        """
        groups = {}
        
        for product in file_products:
            sku = product['sku']
            
            if sku not in holded_lookup:
                continue
            
            holded_product = holded_lookup[sku]
            
            # Only group variants (not main products)
            if not holded_product.get('_is_variant', False):
                continue
            
            main_product_id = holded_product.get('_main_product_id')
            if not main_product_id:
                continue
            
            # Initialize group if needed
            if main_product_id not in groups:
                groups[main_product_id] = {
                    'main_product_id': main_product_id,
                    'main_product_name': holded_product.get('name', 'Unknown'),
                    'products': []
                }
            
            # Add product to group
            groups[main_product_id]['products'].append({
                'file_product': product,
                'holded_product': holded_product
            })
        
        return groups
    
    def _process_product_group_prices(self, group_data: Dict[str, Any], file_result: Dict[str, Any]) -> bool:
        """
        Process price updates for a group of variants belonging to the same main product.
        
        Since Holded API does not allow automatic price updates on products with variants,
        all variant groups are skipped and warnings are generated for manual handling.
        
        Args:
            group_data: Group data containing variants of the same main product
            file_result: File processing results to update
            
        Returns:
            False (no automatic updates performed for variants)
        """
        products = group_data['products']
        main_product_id = group_data['main_product_id']
        main_product_name = group_data['main_product_name']
        
        # Check if all variants have prices in the file
        products_with_prices = [p for p in products if 'price' in p['file_product']]
        
        if not products_with_prices:
            return False
        
        # Extract all prices and check if they're the same
        prices = [p['file_product']['price'] for p in products_with_prices]
        offers = [p['file_product'].get('is_offer', False) for p in products_with_prices]
        
        # Check if all prices are the same (within 0.01 tolerance)
        unique_prices = []
        for price in prices:
            is_duplicate = False
            for existing_price in unique_prices:
                if abs(price - existing_price) < 0.01:
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_prices.append(price)
        
        if len(unique_prices) == 1:
            # All variants have the same price - create unified warning
            target_price = unique_prices[0]
            is_offer = any(offers)  # If any variant is marked as offer
            variant_skus = [p['file_product']['sku'] for p in products_with_prices]
            
            # Get current price for comparison
            first_variant = products_with_prices[0]['holded_product']
            current_price = None
            for price_field in ['price', 'cost', 'amount', 'sell_price']:
                if price_field in first_variant and first_variant[price_field] is not None:
                    current_price = float(first_variant[price_field])
                    break
            
            warning = {
                'main_product_id': main_product_id,
                'main_product_name': main_product_name,
                'type': 'unified_price',  # New: indicates same price across variants
                'reason': 'Product with variants requires manual price update in Holded',
                'unified_price': {
                    'current_price': current_price,
                    'new_price': target_price,
                    'is_offer': is_offer,
                    'variant_skus': variant_skus,
                    'variant_count': len(variant_skus)
                }
            }
            
            file_result['variant_warnings'].append(warning)
            
            offer_text = " (OFFER)" if is_offer else ""
            self.logger.warning(f"UNIFIED VARIANT PRICE UPDATE REQUIRED: Main product {main_product_id} ({main_product_name})")
            self.logger.warning(f"  - All {len(variant_skus)} variants need price update: {current_price} -> {target_price}{offer_text}")
            self.logger.warning(f"  - Variant SKUs: {', '.join(variant_skus)}")
            self.logger.warning("Manual update required in Holded - set main product price")
            
        else:
            # Different prices across variants - create individual variant warning
            variant_info = []
            for product_data in products_with_prices:
                variant = product_data['holded_product']
                price = product_data['file_product']['price']
                sku = product_data['file_product']['sku']
                is_offer = product_data['file_product'].get('is_offer', False)
                
                # Get current price
                current_price = None
                for price_field in ['price', 'cost', 'amount', 'sell_price']:
                    if price_field in variant and variant[price_field] is not None:
                        current_price = float(variant[price_field])
                        break
                
                # Get variant details for display
                details = []
                if '_variant_data' in variant and 'categoryFields' in variant['_variant_data']:
                    for field in variant['_variant_data']['categoryFields']:
                        if 'name' in field and 'field' in field:
                            details.append(f"{field['name']}: {field['field']}")
                
                variant_info.append({
                    'sku': sku,
                    'current_price': current_price,
                    'new_price': price,
                    'is_offer': is_offer,
                    'variant_details': ', '.join(details) if details else 'No details'
                })
            
            warning = {
                'main_product_id': main_product_id,
                'main_product_name': main_product_name,
                'type': 'individual_prices',  # New: indicates different prices per variant
                'reason': 'Variants have different prices - individual updates required',
                'variant_prices': variant_info
            }
            
            file_result['variant_warnings'].append(warning)
            
            self.logger.warning(f"INDIVIDUAL VARIANT PRICE UPDATES REQUIRED: Main product {main_product_id} ({main_product_name})")
            for info in variant_info:
                offer_text = " (OFFER)" if info['is_offer'] else ""
                self.logger.warning(f"  - SKU {info['sku']}: {info.get('current_price', 'N/A')} -> €{info['new_price']:.2f}{offer_text} ({info['variant_details']})")
            self.logger.warning("Manual update required in Holded - update individual variant prices")
        
        return False
    
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
    
    def _update_price_if_different(self, holded_product: Dict[str, Any], new_product: Dict[str, Any]) -> bool:
        """
        Update price if it's different from current price.
        This method now only handles main products. Variants are handled by _process_product_group_prices.
        
        Args:
            holded_product: Holded product data (main product only)
            new_product: New product data from file
            
        Returns:
            True if price was updated, False otherwise
        """
        try:
            # Skip variants - they are handled by group processing
            is_variant = holded_product.get('_is_variant', False)
            if is_variant:
                return False
            
            # Get current price from main product
            current_price = None
            for price_field in ['price', 'cost', 'amount', 'sell_price']:
                if price_field in holded_product and holded_product[price_field] is not None:
                    current_price = float(holded_product[price_field])
                    break
            
            if current_price is None:
                product_name = holded_product.get('name', 'Unknown')
                sku = holded_product.get('sku', 'Unknown')
                self.logger.warning(f"No current price found for product {product_name} (SKU: {sku})")
                return False
            
            # Get new price from the product object
            new_price = float(new_product['price'])
            
            # Check if prices are different (with small tolerance for floating point)
            price_difference = abs(current_price - new_price)
            if price_difference < 0.01:  # Less than 1 cent difference
                return False
            
            # Get offer flag from product data, or determine by price comparison
            is_offer = new_product.get('is_offer', False)
            if not is_offer:
                # Fallback: determine if this is an offer (price reduction)
                is_offer = new_price < current_price
            
            # Get the product ID for the update
            update_id = holded_product.get('id')
            if not update_id:
                self.logger.error("Product ID not found in Holded product")
                return False
            
            offer_text = " (OFFER)" if is_offer else ""
            self.logger.info(f"Updating price for MAIN PRODUCT {update_id}: {current_price} -> {new_price}{offer_text}")
            
            # Update the price - standard main product update
            success = self.holded_api.update_product_price(
                product_id=str(update_id),
                price=new_price,
                add_offer_tag=is_offer
            )
            
            if success:
                update_info = {
                    'product_id': update_id,
                    'sku': holded_product.get('sku', 'unknown'),
                    'product_name': holded_product.get('name', 'Unknown'),
                    'is_variant': False,
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
            'price_updates': self.price_updates,
            'stock_updates': self.stock_updates,
            'total_price_updates': len(self.price_updates),
            'total_stock_updates': len(self.stock_updates),
            'errors': self.errors,
            'variant_warnings': self.variant_warnings # Include variant warnings in summary
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