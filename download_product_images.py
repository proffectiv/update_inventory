#!/usr/bin/env python3
"""
Conway Products Image Downloader
Downloads product images from Conway bikes website based on CSV product data.
"""

import csv
import requests
import os
import re
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse
import time
import zipfile
from datetime import datetime

# Configure logging (console only - no file logging)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ConwayImageDownloader:
    """Downloads product images from Conway bikes website."""
    
    def __init__(self, csv_file: str, images_dir: str = "product_images", info_csv: str = "Información_EAN_Conway_2025.csv"):
        """Initialize the downloader with CSV file and images directory."""
        self.csv_file = csv_file
        self.info_csv = info_csv
        self.images_dir = Path(images_dir)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Create fresh images directory (remove existing if present)
        if self.images_dir.exists():
            import shutil
            shutil.rmtree(self.images_dir)
            logger.info(f"Cleared existing images directory: {self.images_dir}")
        
        self.images_dir.mkdir(parents=True)
        logger.info(f"Created fresh images directory: {self.images_dir}")
        
        # Track failed downloads for reporting
        self.failed_items = []
        
        # Load the information CSV with image URLs
        self.image_url_lookup = self.load_image_url_lookup()
        
        logger.info(f"Initialized downloader with images directory: {self.images_dir}")
        logger.info(f"Loaded {len(self.image_url_lookup)} image URLs from {info_csv}")
    
    def load_image_url_lookup(self) -> Dict[str, str]:
        """Load the image URL lookup from Información_EAN_Conway_2025.csv."""
        try:
            lookup = {}
            sample_skus = []
            with open(self.info_csv, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for i, row in enumerate(reader):
                    artikelnummer = row.get('Artikelnummer', '').strip()
                    bild_url = row.get('Bild', '').strip()
                    if artikelnummer and bild_url:
                        lookup[artikelnummer] = bild_url
                    
                    # Collect first 10 SKUs for debugging
                    if i < 10 and artikelnummer:
                        sample_skus.append(artikelnummer)
                        
            logger.info(f"Successfully loaded {len(lookup)} image URLs from {self.info_csv}")
            logger.info(f"Sample SKUs from info CSV: {sample_skus[:5]}")
            return lookup
        except Exception as e:
            logger.error(f"Failed to load image URL lookup from {self.info_csv}: {e}")
            return {}
    
    def load_csv_data(self) -> List[Dict[str, Any]]:
        """Load and return the CSV data."""
        try:
            products = []
            sample_skus = []
            with open(self.csv_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for i, row in enumerate(reader):
                    products.append(row)
                    # Collect first 10 SKUs for debugging
                    if i < 10:
                        sku = row.get('Sku Variante', '').strip()
                        if sku:
                            sample_skus.append(sku)
                            
            logger.info(f"Successfully loaded CSV with {len(products)} products")
            logger.info(f"Sample SKUs from products CSV: {sample_skus[:5]}")
            return products
        except Exception as e:
            logger.error(f"Failed to load CSV file {self.csv_file}: {e}")
            raise
    
    def get_product_image_url(self, product_data: Dict[str, Any]) -> Optional[str]:
        """Get direct image URL from lookup table."""
        try:
            sku_variante = str(product_data.get('Sku Variante', '')).strip()
            product_name = str(product_data.get('Nombre', ''))
            
            if not sku_variante:
                logger.warning(f"Missing SKU for product: {product_name}")
                return None
            
            # Try exact match first
            image_url = self.image_url_lookup.get(sku_variante)
            
            # If no exact match, try with leading zeros (8 digits total)
            if not image_url and sku_variante.isdigit():
                padded_sku = sku_variante.zfill(8)
                image_url = self.image_url_lookup.get(padded_sku)
                if image_url:
                    logger.info(f"Found image URL using padded SKU {padded_sku} for {product_name}")
            
            if image_url:
                logger.info(f"Found image URL for {product_name} (SKU: {sku_variante}): {image_url}")
                return image_url
            else:
                logger.warning(f"No image URL found for {product_name} (SKU: {sku_variante})")
                # Check if there are similar SKUs for debugging
                similar_skus = [k for k in self.image_url_lookup.keys() if sku_variante in k or k in sku_variante]
                if similar_skus:
                    logger.info(f"Found similar SKUs in lookup: {similar_skus[:3]}")
                else:
                    logger.info(f"No similar SKUs found. First 5 available SKUs: {list(self.image_url_lookup.keys())[:5]}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting image URL for product {product_data.get('Nombre', 'Unknown')}: {e}")
            return None
    
    def validate_url(self, url: str) -> bool:
        """Check if URL exists and returns OK status."""
        try:
            response = self.session.head(url, timeout=10)
            if response.status_code == 200:
                logger.info(f"URL validation successful: {url}")
                return True
            else:
                logger.warning(f"URL returned status {response.status_code}: {url}")
                return False
        except Exception as e:
            logger.error(f"Error validating URL {url}: {e}")
            return False
    
    
    def create_product_folder(self, product_name: str, color: str = "") -> Path:
        """Create folder for product if it doesn't exist."""
        # Clean product name for folder creation
        base_folder_name = re.sub(r'[<>:"/\\|?*]', '_', product_name.strip())
        
        # If color is provided, create color-specific subfolder
        if color and color.strip():
            clean_color = re.sub(r'[<>:"/\\|?*]', '_', color.strip())
            folder_path = self.images_dir / base_folder_name / clean_color
        else:
            folder_path = self.images_dir / base_folder_name
        
        folder_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created/verified folder: {folder_path}")
        return folder_path
    
    def download_image(self, image_url: str, folder_path: Path, sku_variante: str, color: str = "", frame_type: str = "", size: str = "") -> bool:
        """Download a single image to the specified folder with smart duplicate handling."""
        try:
            response = self.session.get(image_url, timeout=15)
            response.raise_for_status()
            
            # Create meaningful filename including color and frame type info
            filename_parts = [sku_variante]
            
            if color and color.strip():
                clean_color = re.sub(r'[<>:"/\\|?*]', '_', color.strip())
                filename_parts.append(clean_color)
                
            if frame_type and frame_type.strip():
                clean_frame = re.sub(r'[<>:"/\\|?*]', '_', frame_type.strip())
                filename_parts.append(clean_frame)
            
            filename = "_".join(filename_parts) + ".jpg"
            file_path = folder_path / filename
            
            # Check if file already exists
            if file_path.exists():
                logger.info(f"Image already exists: {file_path}")
                return True
            
            # Check if there's already an image for this color+frame combination (different size)
            if color and frame_type:
                clean_color = re.sub(r'[<>:*/\\|?*]', '_', color.strip())
                clean_frame = re.sub(r'[<>:*/\\|?*]', '_', frame_type.strip())
                existing_images = list(folder_path.glob(f"*_{clean_color}_{clean_frame}.jpg"))
                if existing_images:
                    logger.info(f"Image for color '{color}' and frame '{frame_type}' already exists: {existing_images[0]}")
                    return True
            elif color:  # Only color, no frame type
                clean_color = re.sub(r'[<>:*/\\|?*]', '_', color.strip())
                existing_images = list(folder_path.glob(f"*_{clean_color}_*.jpg"))
                if not existing_images:  # Check for color without frame type
                    existing_images = list(folder_path.glob(f"*_{clean_color}.jpg"))
                if existing_images:
                    logger.info(f"Image for color '{color}' already exists: {existing_images[0]}")
                    return True
            
            # Save the image
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Downloaded image: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading image {image_url}: {e}")
            return False
    
    def process_product(self, product_data: Dict[str, Any]) -> bool:
        """Process a single product - get image URL and download."""
        product_name = str(product_data.get('Nombre', 'Unknown'))
        sku_variante = str(product_data.get('Sku Variante', ''))
        color = str(product_data.get('Color', ''))
        frame_type = str(product_data.get('Forma del Cuadro', ''))
        size = str(product_data.get('Talla', ''))
        
        logger.info(f"Processing product: {product_name} (SKU: {sku_variante}, Color: {color}, Frame: {frame_type}, Size: {size})")
        
        # Step 1: Get direct image URL from lookup
        image_url = self.get_product_image_url(product_data)
        if not image_url:
            # Add to failed items list
            failed_item = product_data.copy()
            failed_item['Error_Reason'] = 'Image URL not found in lookup table'
            self.failed_items.append(failed_item)
            logger.error(f"Could not find image URL for {product_name}")
            return False
        
        # Step 2: Create product folder (organized by model)
        folder_path = self.create_product_folder(product_name)
        
        # Step 3: Download image with smart duplicate handling for color + frame type combinations
        success = self.download_image(image_url, folder_path, sku_variante, color, frame_type, size)
        
        if success:
            logger.info(f"Successfully processed image for {product_name} ({color}, {frame_type})")
        else:
            # Add to failed items list
            failed_item = product_data.copy()
            failed_item['Error_Reason'] = 'Failed to download image from URL'
            failed_item['Image_URL'] = image_url
            self.failed_items.append(failed_item)
            logger.error(f"Failed to download image for {product_name}")
            
        return success
    
    def generate_failed_items_report(self):
        """Generate a CSV report of items that failed to download."""
        if not self.failed_items:
            logger.info("No failed items to report")
            return
        
        try:
            report_file = "failed_downloads_report.csv"
            
            # Get all unique keys from failed items (in case some have extra fields)
            all_keys = set()
            for item in self.failed_items:
                all_keys.update(item.keys())
            
            # Sort keys to have a consistent order, put Error_Reason and Image_URL first
            sorted_keys = []
            if 'Error_Reason' in all_keys:
                sorted_keys.append('Error_Reason')
                all_keys.remove('Error_Reason')
            if 'Image_URL' in all_keys:
                sorted_keys.append('Image_URL')
                all_keys.remove('Image_URL')
            sorted_keys.extend(sorted(all_keys))
            
            with open(report_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=sorted_keys)
                writer.writeheader()
                
                for item in self.failed_items:
                    # Fill missing keys with empty strings
                    row = {key: item.get(key, '') for key in sorted_keys}
                    writer.writerow(row)
            
            logger.info(f"Generated failed items report with {len(self.failed_items)} entries: {report_file}")
            
        except Exception as e:
            logger.error(f"Error generating failed items report: {e}")
    
    def process_all_products(self):
        """Process all products in the CSV file."""
        logger.info("Starting image download process for all products")
        
        # Load CSV data
        products = self.load_csv_data()
        
        total_products = len(products)
        successful_downloads = 0
        failed_downloads = 0
        
        for index, product in enumerate(products):
            logger.info(f"Processing product {index + 1}/{total_products}")
            
            try:
                if self.process_product(product):
                    successful_downloads += 1
                else:
                    failed_downloads += 1
            except Exception as e:
                logger.error(f"Unexpected error processing product {product.get('Nombre', 'Unknown')}: {e}")
                # Add to failed items list for unexpected errors
                failed_item = product.copy()
                failed_item['Error_Reason'] = f'Unexpected error: {str(e)}'
                self.failed_items.append(failed_item)
                failed_downloads += 1
            
            # Add delay between products
            time.sleep(1)
        
        # Generate CSV report of failed items
        self.generate_failed_items_report()
        
        # Summary
        logger.info(f"Image download process completed!")
        logger.info(f"Total products processed: {index + 1}")
        logger.info(f"Successful downloads: {successful_downloads}")
        logger.info(f"Failed downloads: {failed_downloads}")
        logger.info(f"Items without images: {len(self.failed_items)}")
        
        if self.failed_items:
            logger.info(f"Failed items report generated: failed_downloads_report.csv")
        else:
            logger.info("No failed items to report!")
        
        # Create ZIP archive if images were downloaded
        if successful_downloads > 0:
            zip_path = self.create_images_zip()
            if zip_path:
                logger.info(f"Images ZIP archive created: {zip_path}")
                return zip_path
        
        return None
    
    def create_images_zip(self) -> Optional[str]:
        """
        Create a ZIP archive containing all downloaded images.
        
        Returns:
            Path to the created ZIP file or None if failed
        """
        try:
            if not self.images_dir.exists():
                logger.warning("Images directory does not exist")
                return None
            
            # Count image files
            image_files = list(self.images_dir.rglob("*"))
            image_files = [f for f in image_files if f.is_file() and f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']]
            
            if not image_files:
                logger.warning("No image files found to archive")
                return None
            
            # Create ZIP filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_filename = f"conway_product_images_{timestamp}.zip"
            zip_path = self.images_dir.parent / zip_filename
            
            logger.info(f"Creating ZIP archive with {len(image_files)} images...")
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for image_file in image_files:
                    # Add file to zip with relative path from images directory
                    arcname = image_file.relative_to(self.images_dir)
                    zipf.write(image_file, arcname)
                    logger.debug(f"Added to ZIP: {arcname}")
            
            # Verify ZIP was created successfully
            if zip_path.exists():
                zip_size = zip_path.stat().st_size
                zip_size_mb = round(zip_size / (1024 * 1024), 2)
                logger.info(f"ZIP archive created successfully: {zip_path} ({zip_size_mb} MB)")
                return str(zip_path)
            else:
                logger.error("ZIP file was not created successfully")
                return None
        
        except Exception as e:
            logger.error(f"Error creating images ZIP archive: {e}")
            return None

def main():
    """Main function to run the image downloader."""
    csv_file = "conway_products_holded_import.csv"
    
    if not os.path.exists(csv_file):
        logger.error(f"CSV file not found: {csv_file}")
        return
    
    downloader = ConwayImageDownloader(csv_file)
    zip_path = downloader.process_all_products()
    
    if zip_path:
        logger.info(f"Process completed with ZIP archive: {zip_path}")
    else:
        logger.info("Process completed without ZIP archive")

if __name__ == "__main__":
    main()