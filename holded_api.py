"""
Holded API integration module.

This module handles:
- Connecting to Holded API
- Retrieving product list
- Updating product prices
- Updating product stock
- Formatting requests according to Holded API specification
"""

import requests
from typing import List, Dict, Optional, Any
import logging
import json

from config import config


class HoldedAPI:
    """Handles Holded API operations."""
    
    def __init__(self):
        """Initialize Holded API client."""
        self.api_key = config.holded_api_key
        self.base_url = config.holded_base_url.rstrip('/')
        self.warehouse_id = config.holded_warehouse_id
        self.conway_category_id = config.holded_conway_category_id
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Validate required configuration
        if not self.warehouse_id:
            self.logger.error("HOLDED_WAREHOUSE_ID is required for stock updates")
            raise ValueError("Missing required configuration: HOLDED_WAREHOUSE_ID")
        
        # Set up session with headers
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'key': f'{self.api_key}'
        })
    
    def get_all_products(self) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieve all products from Holded.
        
        Returns:
            List of product dictionaries or None if failed
        """
        try:
            all_products = []
            page = 1
            per_page = 100  # Adjust based on Holded API limits
            
            while True:
                self.logger.info(f"Fetching products page {page}")
                
                # Make API request
                url = f"{self.base_url}/products"
                params = {
                    'page': page,
                    'per_page': per_page
                }
                
                response = self.session.get(url, params=params)
                
                if response.status_code != 200:
                    self.logger.error(f"API request failed: {response.status_code} - {response.text}")
                    return None
                
                data = response.json()
                
                # Extract products from response
                if 'products' in data:
                    products = data['products']
                elif isinstance(data, list):
                    products = data
                else:
                    products = [data]
                
                if not products:
                    break
                
                all_products.extend(products)
                
                # Check if there are more pages
                if len(products) < per_page:
                    break
                
                page += 1
            
            self.logger.info(f"Retrieved {len(all_products)} products from Holded")
            return all_products
            
        except Exception as e:
            self.logger.error(f"Error retrieving products from Holded: {e}")
            return None
    
    def get_conway_category_products(self) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieve all products from the Conway category.
        
        Returns:
            List of Conway category products or None if failed
        """
        try:
            all_products = []
            page = 1
            per_page = 100
            
            while True:
                self.logger.info(f"Fetching Conway category products page {page}")
                
                url = f"{self.base_url}/products"
                params = {
                    'page': page,
                    'per_page': per_page,
                    'categoryId': self.conway_category_id
                }
                
                response = self.session.get(url, params=params)
                
                if response.status_code != 200:
                    self.logger.error(f"API request failed: {response.status_code} - {response.text}")
                    return None
                
                data = response.json()
                
                if 'products' in data:
                    products = data['products']
                elif isinstance(data, list):
                    products = data
                else:
                    products = [data]
                
                if not products:
                    break
                
                # Filter products to ensure they belong to Conway category
                conway_products = []
                for product in products:
                    if self._is_conway_product(product):
                        conway_products.append(product)
                
                all_products.extend(conway_products)
                
                if len(products) < per_page:
                    break
                
                page += 1
            
            self.logger.info(f"Retrieved {len(all_products)} Conway category products")
            return all_products
            
        except Exception as e:
            self.logger.error(f"Error retrieving Conway category products: {e}")
            return None
    
    def _is_conway_product(self, product: Dict[str, Any]) -> bool:
        """
        Check if a product belongs to the Conway category.
        
        Args:
            product: Product dictionary from Holded API
            
        Returns:
            True if product is in Conway category
        """
        # Check categoryId field
        if product.get('categoryId') == self.conway_category_id:
            return True
        
        # Check if categoryId is in a nested structure
        if 'category' in product and isinstance(product['category'], dict):
            if product['category'].get('id') == self.conway_category_id:
                return True
        
        # Check categories array if it exists
        if 'categories' in product and isinstance(product['categories'], list):
            for category in product['categories']:
                if isinstance(category, dict) and category.get('id') == self.conway_category_id:
                    return True
                elif str(category) == self.conway_category_id:
                    return True
        
        return False
    
    def get_conway_variant_skus(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all variant SKUs from Conway category products.
        
        Returns:
            Dictionary mapping variant SKUs to product data
        """
        try:
            conway_products = self.get_conway_category_products()
            if not conway_products:
                self.logger.error("Failed to retrieve Conway category products")
                return {}
            
            variant_skus = {}
            
            for product in conway_products:
                # Get main product SKU
                main_sku = None
                for sku_field in ['sku', 'code', 'reference', 'item_code', 'product_code', 'ref']:
                    if sku_field in product and product[sku_field]:
                        main_sku = str(product[sku_field]).strip()
                        break
                
                # Skip main product SKUs - we only want variants
                # Main products should never be in the stock list
                if main_sku:
                    self.logger.debug(f"Skipping main product SKU (not adding to variant lookup): {main_sku}")
                
                # Get variant SKUs
                if 'variants' in product and isinstance(product['variants'], list):
                    for variant in product['variants']:
                        if isinstance(variant, dict):
                            variant_sku = None
                            for sku_field in ['sku', 'code', 'reference', 'item_code', 'ref']:
                                if sku_field in variant and variant[sku_field]:
                                    variant_sku = str(variant[sku_field]).strip()
                                    break
                            
                            if variant_sku:
                                variant_skus[variant_sku] = {
                                    **product,
                                    'price': variant.get('price', product.get('price')),
                                    'cost': variant.get('cost', product.get('cost')),
                                    'stock': variant.get('stock', product.get('stock')),
                                    '_is_variant': True,
                                    '_variant_id': variant.get('id'),
                                    '_variant_data': variant,
                                    '_main_product_id': product.get('id'),
                                    '_variant_sku': variant_sku,
                                    '_is_conway': True
                                }
            
            self.logger.info(f"Found {len(variant_skus)} Conway variant SKUs")
            return variant_skus
            
        except Exception as e:
            self.logger.error(f"Error getting Conway variant SKUs: {e}")
            return {}

    def get_product_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific product by SKU.
        
        Args:
            sku: Product SKU to search for
            
        Returns:
            Product dictionary or None if not found
        """
        try:
            # Search for product by SKU
            url = f"{self.base_url}/products"
            params = {'sku': sku}
            
            response = self.session.get(url, params=params)
            
            if response.status_code != 200:
                self.logger.error(f"API request failed: {response.status_code} - {response.text}")
                return None
            
            data = response.json()
            
            # Handle different response formats
            if isinstance(data, list) and data:
                return data[0]
            elif isinstance(data, dict) and 'products' in data and data['products']:
                return data['products'][0]
            elif isinstance(data, dict) and 'id' in data:
                return data
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error retrieving product by SKU {sku}: {e}")
            return None
    

    def update_product_stock(self, product_id: str, new_stock: int, current_stock: int, variant_id: str = None) -> bool:
        """
        Update product stock in Holded using correct API structure.
        Enhanced to handle both main products and product variants.
        
        Args:
            product_id: Holded product ID (main product ID for variants)
            new_stock: Target stock quantity
            current_stock: Current stock quantity
            variant_id: Variant ID if updating a variant (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Calculate the stock difference (what to add/subtract)
            stock_difference = new_stock - current_stock
            
            if stock_difference == 0:
                self.logger.info(f"No stock change needed for product {product_id}")
                return True
            
            # Use the stock endpoint with correct payload structure
            url = f"{self.base_url}/products/{product_id}/stock"
            
            if variant_id:
                # For variants: warehouse_id -> variant_id -> stock_difference
                stock_data = {
                    "stock": {
                        self.warehouse_id: {
                            variant_id: stock_difference
                        }
                    }
                }
                self.logger.info(f"Updating VARIANT stock {variant_id}: {current_stock} -> {new_stock} (difference: {stock_difference:+d})")
            else:
                # For main products, we might need a different structure
                # Try the main product format first
                stock_data = {
                    "stock": {
                        self.warehouse_id: {
                            product_id: stock_difference
                        }
                    }
                }
                self.logger.info(f"Updating MAIN PRODUCT stock {product_id}: {current_stock} -> {new_stock} (difference: {stock_difference:+d})")
            
            response = self.session.put(url, json=stock_data)
            
            if response.status_code in [200, 201, 204]:
                self.logger.info(f"Successfully updated stock for {'variant' if variant_id else 'product'} {variant_id or product_id}")
                return True
            else:
                self.logger.error(f"Failed to update stock: {response.status_code} - {response.text}")
                self.logger.error(f"Request payload: {stock_data}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error updating product stock: {e}")
            return False
    
    def _get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Get product by ID (internal helper).
        
        Args:
            product_id: Holded product ID
            
        Returns:
            Product dictionary or None if not found
        """
        try:
            url = f"{self.base_url}/products/{product_id}"
            response = self.session.get(url)
            
            if response.status_code == 200:
                return response.json()
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error retrieving product by ID {product_id}: {e}")
            return None
    
    def test_connection(self) -> bool:
        """
        Test the Holded API connection.
        
        Returns:
            True if connection is successful
        """
        try:
            # Try to get company info or a simple endpoint
            url = f"{self.base_url}/company"
            response = self.session.get(url)
            
            # If company endpoint doesn't exist, try products with limit 1
            if response.status_code == 404:
                url = f"{self.base_url}/products"
                params = {'per_page': 1}
                response = self.session.get(url, params=params)
            
            if response.status_code in [200, 201]:
                self.logger.info("Holded API connection successful")
                return True
            else:
                self.logger.error(f"Holded API connection failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Holded API connection test failed: {e}")
            return False
    
    
    def format_stock_update_json(self, product_id: str, new_stock: int, current_stock: int, variant_id: str = None) -> str:
        """
        Format JSON for stock update request using Holded's warehouse structure.
        
        Args:
            product_id: Holded product ID
            new_stock: Target stock quantity
            current_stock: Current stock quantity
            variant_id: Variant ID if updating a variant (optional)
            
        Returns:
            JSON string for the request
        """
        stock_difference = new_stock - current_stock
        
        if variant_id:
            # Variant stock update format
            stock_data = {
                "stock": {
                    self.warehouse_id: {
                        variant_id: stock_difference
                    }
                }
            }
        else:
            # Main product stock update format
            stock_data = {
                "stock": {
                    self.warehouse_id: {
                        product_id: stock_difference
                    }
                }
            }
        
        return json.dumps(stock_data, indent=2)
    
    def get_all_variants_by_product_name(self, product_name: str) -> List[Dict[str, Any]]:
        """
        Get all variants of a product by its name from Conway category products.
        
        Args:
            product_name: Name of the product to search for
            
        Returns:
            List of variant dictionaries (empty list if none found)
        """
        try:
            # Get Conway variant SKUs which includes all variants
            conway_skus = self.get_conway_variant_skus()
            
            if not conway_skus:
                self.logger.warning("No Conway category products found")
                return []
            
            # Normalize the search product name
            normalized_search_name = product_name.strip().lower()
            matching_variants = []
            
            # Find all variants that match the product name
            for sku, holded_product in conway_skus.items():
                existing_name = holded_product.get('name', '').strip().lower()
                
                if existing_name == normalized_search_name:
                    # Add additional useful information
                    variant_info = {
                        **holded_product,
                        '_search_matched': True,
                        '_variant_sku': sku
                    }
                    matching_variants.append(variant_info)
            
            self.logger.info(f"Found {len(matching_variants)} existing variants for product '{product_name}'")
            
            # Log variant details for debugging
            for variant in matching_variants:
                variant_details = []
                if '_variant_data' in variant and 'categoryFields' in variant['_variant_data']:
                    for field in variant['_variant_data']['categoryFields']:
                        if 'name' in field and 'field' in field:
                            variant_details.append(f"{field['name']}: {field['field']}")
                
                self.logger.debug(f"  - Variant SKU: {variant.get('_variant_sku', 'Unknown')} ({', '.join(variant_details)})")
            
            return matching_variants
            
        except Exception as e:
            self.logger.error(f"Error retrieving variants for product '{product_name}': {e}")
            return []
    
    def delete_product_with_variants(self, product_id: str) -> bool:
        """
        Delete a product and all its variants from Holded.
        
        Args:
            product_id: Main product ID to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self.base_url}/products/{product_id}"
            
            self.logger.info(f"Deleting product {product_id} and all its variants...")
            
            response = self.session.delete(url)
            
            if response.status_code in [200, 204]:
                self.logger.info(f"Successfully deleted product {product_id}")
                return True
            else:
                self.logger.error(f"Failed to delete product {product_id}: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error deleting product {product_id}: {e}")
            return False
    
    def get_main_product_id_by_variant_sku(self, variant_sku: str) -> Optional[str]:
        """
        Get the main product ID for a given variant SKU.
        
        Args:
            variant_sku: The variant SKU to lookup
            
        Returns:
            Main product ID or None if not found
        """
        try:
            # Get Conway variant SKUs
            conway_skus = self.get_conway_variant_skus()
            
            if variant_sku in conway_skus:
                variant_data = conway_skus[variant_sku]
                main_product_id = variant_data.get('_main_product_id')
                
                if main_product_id:
                    self.logger.debug(f"Found main product ID {main_product_id} for variant SKU {variant_sku}")
                    return str(main_product_id)
                else:
                    self.logger.warning(f"No main product ID found for variant SKU {variant_sku}")
                    return None
            else:
                self.logger.warning(f"Variant SKU {variant_sku} not found in Conway products")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting main product ID for variant SKU {variant_sku}: {e}")
            return None


def get_holded_products() -> Optional[List[Dict[str, Any]]]:
    """
    Main function to get all products from Holded.
    
    Returns:
        List of product dictionaries or None if failed
    """
    api = HoldedAPI()
    
    try:
        # Test connection first
        if not api.test_connection():
            logging.error("Holded API connection failed")
            return None
        
        # Get all products
        products = api.get_all_products()
        
        return products
        
    except Exception as e:
        logging.error(f"Error getting Holded products: {e}")
        return None 