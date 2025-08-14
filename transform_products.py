#!/usr/bin/env python3
"""
Conway Products Import Transformer
Transforms product data from multiple CSV files into Holded import format.
"""

import pandas as pd
import re
from datetime import datetime
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

def clean_price(price_str: str) -> float:
    """Clean and convert price string to float."""
    if pd.isna(price_str) or price_str == '':
        return 0.0
    
    # Remove currency symbols and spaces
    cleaned = re.sub(r'[€\s]', '', str(price_str))
    # Replace comma with dot for decimal separator
    cleaned = cleaned.replace(',', '.')
    
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

def clean_stock(stock_str: str) -> int:
    """Clean and convert stock string to int."""
    if pd.isna(stock_str) or stock_str == '':
        return 0
    
    stock_str = str(stock_str).strip()
    if stock_str == '>10':
        return 10
    
    try:
        return int(stock_str)
    except ValueError:
        return 0

def translate_color(color: str) -> str:
    """Translate color names to Spanish with better logic."""
    if pd.isna(color):
        return ''
    
    # Clean the input
    color = str(color).strip()
    
    # Handle specific complex color combinations
    color_mappings = {
        'black metallic / red metallic matt': 'Negro Metálico / Rojo Metálico Mate',
        'black metallic / mint': 'Negro Metálico / Menta',
        'darkpetrol metallic / red': 'Azul Petróleo Oscuro Metálico / Rojo',
        'darkblue metallic / lightblue': 'Azul Oscuro Metálico / Azul Claro',
        'red metallic / shadowgrey metallic': 'Rojo Metálico / Gris Sombra Metálico',
        'black metallic / gold matt': 'Negro Metálico / Dorado Mate',
        'graphitegreymetallic / shadowgrey': 'Gris Grafito Metálico / Gris Sombra',
        'turquoise fade / red': 'Turquesa Degradado / Rojo',
        'turquoise / black': 'Turquesa / Negro',
        'shadowgrey metallic / silver': 'Gris Sombra Metálico / Plateado'
    }
    
    # Check for exact matches first
    color_lower = color.lower()
    for pattern, translation in color_mappings.items():
        if pattern in color_lower:
            return translation
    
    # Basic color translations for individual terms
    color_translations = {
        'black': 'Negro',
        'white': 'Blanco', 
        'red': 'Rojo',
        'blue': 'Azul',
        'green': 'Verde',
        'yellow': 'Amarillo',
        'orange': 'Naranja',
        'grey': 'Gris',
        'gray': 'Gris',
        'silver': 'Plateado',
        'gold': 'Dorado',
        'turquoise': 'Turquesa',
        'mint': 'Menta',
        'metallic': 'Metálico',
        'matt': 'Mate',
        'fade': 'Degradado',
        'lightblue': 'Azul Claro',
        'darkblue': 'Azul Oscuro',
        'shadowgrey': 'Gris Sombra',
        'graphitegrey': 'Gris Grafito',
        'darkpetrol': 'Azul Petróleo Oscuro'
    }
    
    # Replace individual terms
    result = color_lower
    for eng, esp in color_translations.items():
        result = result.replace(eng, esp)
    
    # Capitalize each word
    return ' '.join(word.capitalize() for word in result.split())

def translate_model_year(model_year: str) -> str:
    """Translate model year to Spanish."""
    if pd.isna(model_year):
        return ''
    
    return str(model_year)

def get_wheel_size(ws: str) -> str:
    """Convert wheel size to proper format."""
    if pd.isna(ws) or ws == '':
        return ''
    
    ws_str = str(ws).strip()
    if ws_str == '27':
        return '27.5'
    elif ws_str == '29':
        return '29'
    elif ws_str == '28':
        return '28'
    else:
        # Default to the value if it's already in correct format
        return ws_str

def categorize_bike_type(gruppentext: str) -> str:
    """Categorize bike type based on Gruppentext."""
    if pd.isna(gruppentext):
        return ''
    
    gruppentext_lower = gruppentext.lower()
    
    if 'mtb' in gruppentext_lower or 'hardtail' in gruppentext_lower:
        return 'MTB'
    elif 'suv' in gruppentext_lower:
        return 'SUV'
    elif 'trekking' in gruppentext_lower:
        return 'Trekking'
    elif 'city' in gruppentext_lower:
        return 'City'
    else:
        return 'MTB'  # Default

def categorize_frame_shape(artikeltext: str) -> str:
    """Categorize frame shape based on Gruppentext."""
    if pd.isna(artikeltext):
        return ''
    
    artikeltext_lower = artikeltext.lower()
    
    if 'diamant' in artikeltext_lower or 'herren' in artikeltext_lower:
        return 'Diamante'
    elif 'trapez' in artikeltext_lower:
        return 'Trapecio'
    elif 'wave' in artikeltext_lower:
        return 'Wave'
    else:
        return 'Hardtail'  # Default

def categorize_conway(gruppentext: str) -> str:
    """Categorize Conway type (Mecánica or Eléctrica)."""
    if pd.isna(gruppentext):
        return 'Mecánica'
    
    gruppentext_lower = gruppentext.lower()
    
    if 'elektro' in gruppentext_lower or 'electric' in gruppentext_lower:
        return 'Eléctrica'
    else:
        return 'Mecánica'

def translate_technical_terms(text: str) -> str:
    """Translate technical German terms to Spanish."""
    if pd.isna(text) or text == '':
        return text
    
    translations = {
        'Gang': 'Velocidades',
        'speed': 'Velocidades', 
        'Hardtail': 'Hardtail',
        'Diamant': 'Diamante',
        'Trapez': 'Trapecio',
        'Wave': 'Wave',
        'Herren': 'Diamante',
        'mm': 'mm',
        'Federweg': 'recorrido',
        'tapered': 'cónico',
        'Post Mount': 'Post Mount',
        'schwarz': 'negro',
        'horizontal': 'horizontal',
        'Gen.': 'Gen.',
        'Performance': 'Performance',
        'Line': 'Line',
        'CX': 'CX'
    }
    
    result = str(text)
    for german, spanish in translations.items():
        result = result.replace(german, spanish)
    
    return result

def extract_specific_characteristics(artikeltext: str, stock_row: pd.Series) -> list:
    """Extract specific characteristics from Artikeltext, avoiding duplicates."""
    if pd.isna(artikeltext):
        return []
    
    characteristics = []
    text = str(artikeltext).lower()
    
    # Extract wheel size if mentioned and different from ws column
    wheel_size_from_ws = get_wheel_size(stock_row['ws'])
    if wheel_size_from_ws:
        characteristics.append(f'• Tamaño de rueda: {wheel_size_from_ws}"')
    
    # Extract frame measurements (like 38cm, 41cm, etc.) - this is frame distance/height
    import re
    frame_measurements = re.findall(r'(\d+)cm', text)
    if frame_measurements:
        characteristics.append(f'• Altura del cuadro: {frame_measurements[0]}cm')
    
    # Extract other specific technical info that's not duplicated
    # Look for speed info that's not already covered in transmission
    speed_matches = re.findall(r'(\d+)-gang', text)
    if not speed_matches:  # Only if not found in German
        speed_matches = re.findall(r'(\d+)\s*speed', text)
    
    # Extract brake disc sizes
    disc_matches = re.findall(r'(\d+)/(\d+)\s*mm', text)
    if disc_matches:
        front, rear = disc_matches[0]
        characteristics.append(f'• Discos de freno: {front}mm delantero / {rear}mm trasero')
    
    return characteristics

def build_description(info_row: pd.Series, stock_row: pd.Series) -> str:
    """Build bullet-point description from bike components."""
    description_parts = []
    
    # Frame type using the same logic as categorize_frame_shape
    if pd.notna(info_row.get('Artikeltext')):
        frame_shape = categorize_frame_shape(info_row['Artikeltext'])
        description_parts.append(f'• Tipo de cuadro: {frame_shape}')
    
    # Extract specific characteristics from Artikeltext (avoiding duplicates)
    if pd.notna(info_row.get('Artikeltext')):
        specific_chars = extract_specific_characteristics(info_row['Artikeltext'], stock_row)
        description_parts.extend(specific_chars)
    
    # Suspension (translated)
    if pd.notna(info_row.get('Gabel')):
        translated_suspension = translate_technical_terms(info_row['Gabel'])
        description_parts.append(f'• Suspensión: {translated_suspension}')
    
    # Brakes
    if pd.notna(info_row.get('Bremse')):
        description_parts.append(f'• Frenos: {info_row["Bremse"]}')
    
    # Gears/Drivetrain (translated)
    if pd.notna(info_row.get('Schaltwerk')):
        translated_gears = translate_technical_terms(info_row['Schaltwerk'])
        description_parts.append(f'• Cambio: {translated_gears}')
    
    # System/Motor for electric bikes
    if pd.notna(info_row.get('Motor')):
        description_parts.append(f'• Motor: {info_row["Motor"]}')
    
    if pd.notna(info_row.get('Akku')):
        description_parts.append(f'• Batería: {info_row["Akku"]}')
    
    return '\n'.join(description_parts) if description_parts else ''

def get_first_sku_for_product(stock_df: pd.DataFrame, product_name: str) -> str:
    """Get the first (smallest size) SKU for a product name."""
    product_variants = stock_df[stock_df['Name'] == product_name].copy()
    
    if len(product_variants) == 0:
        return ''
    
    # Sort by size to get the smallest first
    size_order = ['XS', 'S', 'M', 'L', 'XL', 'XXL']
    product_variants['size_order'] = product_variants['size'].apply(
        lambda x: size_order.index(x) if x in size_order else 999
    )
    
    first_variant = product_variants.sort_values('size_order').iloc[0]
    return str(first_variant['Item'])

def main():
    """Main transformation function with enhanced processing metadata."""
    
    # Load the CSV files
    print("Loading CSV files...")
    stock_df = pd.read_csv('stock_Stocklist_CONWAY.csv')
    info_df = pd.read_csv('Información_EAN_Conway_2025.csv')
    template_df = pd.read_csv('Importar Productos.csv')
    
    # Get template columns
    template_columns = template_df.columns.tolist()
    
    # Create output dataframe
    output_data = []
    
    # Enhanced processing tracking
    processing_metadata = {
        'input_products': len(stock_df),
        'output_products': 0,
        'failed_lookups': [],
        'processed_products': 0,
        'success_rate': 0.0
    }
    
    print(f"Processing {len(stock_df)} products...")
    
    # Group stock items by product name to handle variants
    grouped_stock = stock_df.groupby('Name')
    
    for product_name, product_variants in grouped_stock:
        print(f"Processing: {product_name}")
        
        # Get the first SKU for this product (smallest size)
        first_sku = get_first_sku_for_product(stock_df, product_name)
        
        # Process each variant
        for _, stock_row in product_variants.iterrows():
            processing_metadata['processed_products'] += 1
            
            # Find matching info row by Item number
            info_row = info_df[info_df['Artikelnummer'] == stock_row['Item']]
            
            if len(info_row) == 0:
                print(f"Warning: No info found for item {stock_row['Item']}")
                # Track failed lookup
                failed_product = {
                    'sku': str(stock_row['Item']),
                    'name': str(stock_row['Name']),
                    'reason': f'No matching Artikelnummer found in {len(info_df)} EAN info records'
                }
                processing_metadata['failed_lookups'].append(failed_product)
                continue
                
            info_row = info_row.iloc[0]
            
            # Build the output row
            row_data = {}
            
            # Fill template columns
            row_data['SKU'] = first_sku
            row_data['Nombre'] = stock_row['Name']
            row_data['Descripción'] = build_description(info_row, stock_row)
            row_data['Código de barras'] = ''  # Empty as specified
            row_data['Código de fábrica'] = first_sku
            row_data['Talla'] = stock_row['size']
            row_data['Color'] = translate_color(stock_row['color'])
            row_data['Medida de la Rueda'] = get_wheel_size(stock_row['ws'])
            row_data['Tipo de Bici'] = categorize_bike_type(info_row['Gruppentext'])
            row_data['Forma del Cuadro'] = categorize_frame_shape(info_row['Artikeltext'])
            row_data['Año'] = translate_model_year(info_row['Modelljahr'])
            row_data['Sku Variante'] = str(stock_row['Item'])
            # Format EAN as integer without decimals
            ean_value = info_row['EAN']
            if pd.notna(ean_value):
                try:
                    # Convert to int to remove decimals, then back to string
                    ean_int = int(float(ean_value))
                    row_data['Código barras Variante'] = str(ean_int)
                except (ValueError, TypeError):
                    row_data['Código barras Variante'] = str(ean_value)
            else:
                row_data['Código barras Variante'] = ''
            # Fill remaining template columns (these should always be assigned)
            row_data['cat - Cycplus'] = ''  # Empty
            row_data['cat - DARE'] = ''  # Empty
            row_data['cat - Conway'] = categorize_conway(info_row['Gruppentext'])
            row_data['cat - Kogel'] = ''  # Empty
            row_data['Coste (Subtotal)'] = ''  # Empty
            row_data['Precio compra (Subtotal)'] = ''  # Empty
            row_data['Precio venta (Subtotal)'] = f"{clean_price(info_row['EVP']) / 1.21}"
            row_data['Impuesto de venta'] = 21
            row_data['Impuesto de compras'] = ''  # Empty
            row_data['Stock'] = clean_stock(stock_row['Stock qty'])
            row_data['Peso'] = ''  # Empty
            row_data['Fecha de inicio dd/mm/yyyy'] = datetime.now().strftime('%d/%m/%Y')
            row_data['Tags separados por -'] = ''  # Empty
            row_data['Proveedor (Código)'] = '67a5b434b4aa620153059995'
            row_data['Cuenta ventas'] = '700000000'
            row_data['Cuenta compras'] = '600000000'
            row_data['Almacén'] = '67a373952eadb1b9db02a9c4'
            
            output_data.append(row_data)
    
    # Create final dataframe with exact template structure
    output_df = pd.DataFrame(output_data, columns=template_columns)
    
    # Update processing metadata
    processing_metadata['output_products'] = len(output_df)
    if processing_metadata['input_products'] > 0:
        processing_metadata['success_rate'] = (processing_metadata['output_products'] / processing_metadata['input_products']) * 100
    
    # Save to CSV with proper escaping for multiline descriptions
    output_filename = 'conway_products_holded_import.csv'
    output_df.to_csv(output_filename, index=False, quoting=1)  # Quote all fields
    
    print(f"Transformation complete! Output saved to: {output_filename}")
    print(f"Total products processed: {len(output_df)} of {processing_metadata['input_products']} input products ({processing_metadata['success_rate']:.1f}% success rate)")
    
    if processing_metadata['failed_lookups']:
        print(f"Warning: {len(processing_metadata['failed_lookups'])} products failed EAN lookup and were skipped")
        for failed in processing_metadata['failed_lookups'][:3]:  # Show first 3 failures
            print(f"  - SKU {failed['sku']}: {failed['name']} - {failed['reason']}")
        if len(processing_metadata['failed_lookups']) > 3:
            print(f"  ... and {len(processing_metadata['failed_lookups']) - 3} more failures")
    
    # For backward compatibility, still return the dataframe as primary return value
    # The metadata will be available for enhanced workflows
    return output_df

# Global variable to store the last processing metadata
_last_processing_metadata = {}

def main_with_metadata():
    """Enhanced main function that returns both dataframe and metadata."""
    global _last_processing_metadata
    
    # Load the CSV files
    print("Loading CSV files...")
    stock_df = pd.read_csv('stock_Stocklist_CONWAY.csv')
    info_df = pd.read_csv('Información_EAN_Conway_2025.csv')
    template_df = pd.read_csv('Importar Productos.csv')
    
    # Get template columns
    template_columns = template_df.columns.tolist()
    
    # Create output dataframe
    output_data = []
    
    # Enhanced processing tracking
    processing_metadata = {
        'input_products': len(stock_df),
        'output_products': 0,
        'failed_lookups': [],
        'processed_products': 0,
        'success_rate': 0.0
    }
    
    print(f"Processing {len(stock_df)} products...")
    
    # Group stock items by product name to handle variants
    grouped_stock = stock_df.groupby('Name')
    
    for product_name, product_variants in grouped_stock:
        print(f"Processing: {product_name}")
        
        # Get the first SKU for this product (smallest size)
        first_sku = get_first_sku_for_product(stock_df, product_name)
        
        # Process each variant
        for _, stock_row in product_variants.iterrows():
            processing_metadata['processed_products'] += 1
            
            # Find matching info row by Item number
            info_row = info_df[info_df['Artikelnummer'] == stock_row['Item']]
            
            if len(info_row) == 0:
                print(f"Warning: No info found for item {stock_row['Item']}")
                # Track failed lookup
                failed_product = {
                    'sku': str(stock_row['Item']),
                    'name': str(stock_row['Name']),
                    'reason': f'No matching Artikelnummer found in {len(info_df)} EAN info records'
                }
                processing_metadata['failed_lookups'].append(failed_product)
                continue
                
            info_row = info_row.iloc[0]
            
            # Build the output row (same logic as main function)
            row_data = {}
            
            # Fill template columns
            row_data['SKU'] = first_sku
            row_data['Nombre'] = stock_row['Name']
            row_data['Descripción'] = build_description(info_row, stock_row)
            row_data['Código de barras'] = ''  # Empty as specified
            row_data['Código de fábrica'] = first_sku
            row_data['Talla'] = stock_row['size']
            row_data['Color'] = translate_color(stock_row['color'])
            row_data['Medida de la Rueda'] = get_wheel_size(stock_row['ws'])
            row_data['Tipo de Bici'] = categorize_bike_type(info_row['Gruppentext'])
            row_data['Forma del Cuadro'] = categorize_frame_shape(info_row['Artikeltext'])
            row_data['Año'] = translate_model_year(info_row['Modelljahr'])
            row_data['Sku Variante'] = str(stock_row['Item'])
            # Format EAN as integer without decimals
            ean_value = info_row['EAN']
            if pd.notna(ean_value):
                try:
                    # Convert to int to remove decimals, then back to string
                    ean_int = int(float(ean_value))
                    row_data['Código barras Variante'] = str(ean_int)
                except (ValueError, TypeError):
                    row_data['Código barras Variante'] = str(ean_value)
            else:
                row_data['Código barras Variante'] = ''
            
            # Fill remaining template columns (these should always be assigned)
            row_data['cat - Cycplus'] = ''  # Empty
            row_data['cat - DARE'] = ''  # Empty
            row_data['cat - Conway'] = categorize_conway(info_row['Gruppentext'])
            row_data['cat - Kogel'] = ''  # Empty
            row_data['Coste (Subtotal)'] = ''  # Empty
            row_data['Precio compra (Subtotal)'] = ''  # Empty
            row_data['Precio venta (Subtotal)'] = f"{clean_price(info_row['EVP']) / 1.21}"
            row_data['Impuesto de venta'] = 21
            row_data['Impuesto de compras'] = ''  # Empty
            row_data['Stock'] = clean_stock(stock_row['Stock qty'])
            row_data['Peso'] = ''  # Empty
            row_data['Fecha de inicio dd/mm/yyyy'] = datetime.now().strftime('%d/%m/%Y')
            row_data['Tags separados por -'] = ''  # Empty
            row_data['Proveedor (Código)'] = '67a5b434b4aa620153059995'
            row_data['Cuenta ventas'] = '700000000'
            row_data['Cuenta compras'] = '600000000'
            row_data['Almacén'] = '67a373952eadb1b9db02a9c4'
            
            output_data.append(row_data)
    
    # Create final dataframe with exact template structure
    output_df = pd.DataFrame(output_data, columns=template_columns)
    
    # Update processing metadata
    processing_metadata['output_products'] = len(output_df)
    if processing_metadata['input_products'] > 0:
        processing_metadata['success_rate'] = (processing_metadata['output_products'] / processing_metadata['input_products']) * 100
    
    # Store metadata globally for access
    _last_processing_metadata = processing_metadata
    
    # Save to CSV with proper escaping for multiline descriptions
    output_filename = 'conway_products_holded_import.csv'
    output_df.to_csv(output_filename, index=False, quoting=1)  # Quote all fields
    
    print(f"Transformation complete! Output saved to: {output_filename}")
    print(f"Total products processed: {len(output_df)} of {processing_metadata['input_products']} input products ({processing_metadata['success_rate']:.1f}% success rate)")
    
    if processing_metadata['failed_lookups']:
        print(f"Warning: {len(processing_metadata['failed_lookups'])} products failed EAN lookup and were skipped")
        for failed in processing_metadata['failed_lookups'][:3]:  # Show first 3 failures
            print(f"  - SKU {failed['sku']}: {failed['name']} - {failed['reason']}")
        if len(processing_metadata['failed_lookups']) > 3:
            print(f"  ... and {len(processing_metadata['failed_lookups']) - 3} more failures")
    
    return output_df, processing_metadata

def get_last_processing_metadata():
    """Get the metadata from the last transformation run."""
    global _last_processing_metadata
    return _last_processing_metadata.copy()

if __name__ == "__main__":
    result = main()