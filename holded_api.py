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
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Set up session with headers
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
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
    
    def update_product_price(self, product_id: str, price: float, add_offer_tag: bool = False) -> bool:
        """
        Update product price in Holded.
        
        Args:
            product_id: Holded product ID
            price: New price
            add_offer_tag: Whether to add "oferta" tag
            
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self.base_url}/products/{product_id}"
            
            # Prepare update data
            update_data = {
                'price': price
            }
            
            # Add offer tag if needed
            if add_offer_tag:
                # Get current product to preserve existing tags
                current_product = self._get_product_by_id(product_id)
                if current_product:
                    existing_tags = current_product.get('tags', [])
                    if 'oferta' not in [tag.lower() for tag in existing_tags]:
                        existing_tags.append('oferta')
                    update_data['tags'] = existing_tags
                else:
                    update_data['tags'] = ['oferta']
            
            # Make API request
            response = self.session.put(url, json=update_data)
            
            if response.status_code in [200, 201, 204]:
                self.logger.info(f"Successfully updated price for product {product_id}: {price}")
                return True
            else:
                self.logger.error(f"Failed to update price: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error updating product price: {e}")
            return False
    
    def update_product_stock(self, product_id: str, stock: int) -> bool:
        """
        Update product stock in Holded.
        
        Args:
            product_id: Holded product ID
            stock: New stock quantity
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Holded might use a different endpoint for stock updates
            url = f"{self.base_url}/products/{product_id}/stock"
            
            # Try stock endpoint first
            stock_data = {
                'quantity': stock,
                'movement_type': 'set'  # Set absolute stock level
            }
            
            response = self.session.put(url, json=stock_data)
            
            # If stock endpoint doesn't exist, try updating via product endpoint
            if response.status_code == 404:
                url = f"{self.base_url}/products/{product_id}"
                update_data = {'stock': stock}
                response = self.session.put(url, json=update_data)
            
            if response.status_code in [200, 201, 204]:
                self.logger.info(f"Successfully updated stock for product {product_id}: {stock}")
                return True
            else:
                self.logger.error(f"Failed to update stock: {response.status_code} - {response.text}")
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
    
    def format_price_update_json(self, product_id: str, price: float, add_offer_tag: bool = False) -> str:
        """
        Format JSON for price update request.
        
        Args:
            product_id: Holded product ID
            price: New price
            add_offer_tag: Whether to add offer tag
            
        Returns:
            JSON string for the request
        """
        update_data = {
            'price': price
        }
        
        if add_offer_tag:
            update_data['tags'] = ['oferta']
        
        return json.dumps(update_data, indent=2)
    
    def format_stock_update_json(self, product_id: str, stock: int) -> str:
        """
        Format JSON for stock update request.
        
        Args:
            product_id: Holded product ID
            stock: New stock quantity
            
        Returns:
            JSON string for the request
        """
        stock_data = {
            'quantity': stock,
            'movement_type': 'set'
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