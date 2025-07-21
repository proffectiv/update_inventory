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