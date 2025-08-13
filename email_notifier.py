"""
Módulo notificador de email para enviar emails de confirmación.

Este módulo maneja:
- Conexión al servidor SMTP de Strato
- Envío de emails de confirmación de actualización de inventario
- Formateo del contenido del email con detalles de actualización
- Manejo de errores de entrega de email
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from config import config


class EmailNotifier:
    """Maneja notificaciones de email vía SMTP de Strato."""
    
    def __init__(self):
        """Inicializa el notificador de email con la configuración SMTP de Strato."""
        self.smtp_host = config.smtp_host
        self.smtp_port = config.smtp_port
        self.username = config.smtp_username
        self.password = config.smtp_password
        self.notification_email = config.notification_email
        
        # Configurar logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def send_update_confirmation(self, update_results: Dict[str, Any], attachment_files: Optional[Dict[str, str]] = None) -> bool:
        """
        Envía confirmación por email de las actualizaciones de inventario.
        
        Args:
            update_results: Diccionario que contiene resultados y estadísticas de la actualización
            attachment_files: Diccionario opcional con archivos adjuntos {'nombre': 'ruta_archivo'}
            
        Returns:
            True si el email se envió exitosamente, False en caso contrario
        """
        try:
            # Crear contenido del email
            subject = self._create_email_subject(update_results)
            body_html = self._create_email_body_html(update_results)
            body_text = self._create_email_body_text(update_results)
            
            # Enviar el email
            success = self._send_email(
                to_email=self.notification_email,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                attachment_files=attachment_files
            )
            
            if success:
                self.logger.info("Email de confirmación de actualización enviado exitosamente")
            else:
                self.logger.error("Falló el envío del email de confirmación de actualización")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error enviando email de confirmación de actualización: {e}")
            return False
    
    def send_error_notification(self, error_details: Dict[str, Any]) -> bool:
        """
        Envía notificación por email sobre errores de procesamiento.
        
        Args:
            error_details: Diccionario que contiene información del error
            
        Returns:
            True si el email se envió exitosamente, False en caso contrario
        """
        try:
            # Crear contenido del email de error
            subject = "❌ Error de Actualización de Inventario - Acción Requerida"
            body_html = self._create_error_email_html(error_details)
            body_text = self._create_error_email_text(error_details)
            
            # Enviar el email
            success = self._send_email(
                to_email=self.notification_email,
                subject=subject,
                body_html=body_html,
                body_text=body_text
            )
            
            if success:
                self.logger.info("Email de notificación de error enviado exitosamente")
            else:
                self.logger.error("Falló el envío del email de notificación de error")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error enviando email de notificación de error: {e}")
            return False
    
    def _send_email(self, to_email: str, subject: str, body_html: str, body_text: str, attachment_files: Optional[Dict[str, str]] = None) -> bool:
        """
        Envía email vía SMTP de Strato.
        
        Args:
            to_email: Dirección de email del destinatario
            subject: Asunto del email
            body_html: Cuerpo del email en HTML
            body_text: Cuerpo del email en texto plano
            attachment_files: Diccionario opcional con archivos adjuntos {'nombre': 'ruta_archivo'}
            
        Returns:
            True si es exitoso, False en caso contrario
        """
        try:
            # Crear mensaje
            msg = MIMEMultipart('mixed')  # Changed from 'alternative' to 'mixed' to support attachments
            msg['Subject'] = subject
            msg['From'] = self.username
            msg['To'] = to_email
            
            # Create a MIMEMultipart for the body (text and HTML)
            body = MIMEMultipart('alternative')
            part1 = MIMEText(body_text, 'plain', 'utf-8')
            part2 = MIMEText(body_html, 'html', 'utf-8')
            body.attach(part1)
            body.attach(part2)
            
            # Attach the body to the main message
            msg.attach(body)
            
            # Add attachments if provided
            if attachment_files:
                self.logger.info(f"Adding {len(attachment_files)} attachments to email")
                for attachment_name, file_path in attachment_files.items():
                    if file_path and os.path.exists(file_path):
                        try:
                            self._add_attachment(msg, file_path, attachment_name)
                            self.logger.info(f"Added attachment: {attachment_name} ({file_path})")
                        except Exception as e:
                            self.logger.error(f"Failed to add attachment {attachment_name}: {e}")
                    else:
                        self.logger.warning(f"Attachment file not found: {file_path}")
            
            # Conectar al servidor SMTP y enviar email (usando SSL para puerto 465)
            self.logger.info(f"Conectando al servidor SMTP: {self.smtp_host}:{self.smtp_port}")
            
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port) as server:
                server.login(self.username, self.password)
                
                # Enviar email
                text = msg.as_string()
                server.sendmail(self.username, [to_email], text)
                
                self.logger.info(f"Email enviado exitosamente")
                return True
                
        except smtplib.SMTPAuthenticationError as e:
            self.logger.error(f"Falló la autenticación SMTP: {e}")
            return False
        except smtplib.SMTPException as e:
            self.logger.error(f"Error SMTP: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error enviando email: {e}")
            return False
    
    def _add_attachment(self, msg: MIMEMultipart, file_path: str, attachment_name: str):
        """
        Add a file attachment to the email message.
        
        Args:
            msg: MIMEMultipart message to add attachment to
            file_path: Path to the file to attach
            attachment_name: Name to display for the attachment
        """
        try:
            with open(file_path, "rb") as attachment:
                # Create MIMEBase object
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
            
            # Encode the file in ASCII characters to send by email    
            encoders.encode_base64(part)
            
            # Add header with the file name
            filename = os.path.basename(file_path)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {filename}',
            )
            
            # Attach the file to the message
            msg.attach(part)
            
        except Exception as e:
            self.logger.error(f"Error adding attachment {file_path}: {e}")
            raise
    
    def _create_email_subject(self, update_results: Dict[str, Any]) -> str:
        """
        Crea la línea de asunto del email basada en los resultados de la actualización.
        
        Args:
            update_results: Diccionario de resultados de actualización
            
        Returns:
            Cadena del asunto del email
        """
        stock_updates = update_results.get('stock_updates', 0)
        stock_resets = update_results.get('stock_resets', 0)
        new_products = len(update_results.get('new_products_for_creation', []))
        errors = len(update_results.get('errors', []))
        total_changes = stock_updates + stock_resets
        
        if errors > 0:
            return f"⚠️ Actualización de Inventario Completada con {errors} Errores"
        elif new_products > 0 and total_changes > 0:
            return f"✅ Inventario Actualizado - {total_changes} Cambios, {new_products} Productos Nuevos para Crear"
        elif new_products > 0:
            return f"✅ Inventario Revisado - {new_products} Productos Nuevos Requieren Creación Manual"
        elif total_changes > 0:
            if stock_resets > 0:
                return f"✅ Inventario Conway Actualizado - {stock_updates} Actualizaciones de Stock, {stock_resets} Resets"
            else:
                return f"✅ Inventario Conway Actualizado - {stock_updates} Actualizaciones de Stock"
        else:
            return "✅ Actualización de Inventario Completada - No se Requieren Cambios"
    
    def _create_email_body_html(self, update_results: Dict[str, Any]) -> str:
        """
        Crea el cuerpo del email en HTML con detalles de la actualización.
        
        Args:
            update_results: Diccionario de resultados de actualización
            
        Returns:
            Cadena del cuerpo del email en HTML
        """
        timestamp = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f0f8ff; padding: 20px; border-radius: 5px; }}
                .summary {{ background-color: #f9f9f9; padding: 15px; margin: 20px 0; border-radius: 5px; }}
                .success {{ color: #28a745; }}
                .warning {{ color: #ffc107; }}
                .error {{ color: #dc3545; }}
                table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>Actualización de Inventario</h2>
                <p><strong>Tiempo de Ejecución:</strong> {timestamp}</p>
            </div>
            
            <div class="summary">
                <h3>Resumen</h3>
                <ul>
                    <li><strong>Archivos Procesados:</strong> {update_results.get('processed_files', 0)}</li>
                    <li><strong>Productos Procesados:</strong> {update_results.get('processed_products', 0)}</li>
                    <li><strong>Actualizaciones de Stock:</strong> <span class="success">{update_results.get('stock_updates', 0)}</span></li>
                    <li><strong>Stock Resets (Producto agotado):</strong> <span class="warning">{update_results.get('stock_resets', 0)}</span></li>
                    <li><strong>Productos Nuevos (Creación Manual):</strong> <span style="color: #007bff; font-weight: bold;">{len(update_results.get('new_products_for_creation', []))}</span></li>
                    <li><strong>Errores:</strong> <span class="error">{len(update_results.get('errors', []))}</span></li>
                </ul>
            </div>
        """
        
        
        
        # Agregar detalles de actualizaciones de stock si los hay
        if 'summary' in update_results and update_results['summary'].get('stock_updates'):
            stock_updates = update_results['summary']['stock_updates']
            html += f"""
            <div class="details" style="margin-top: 30px;">
                <h3 style="color: #28a745; border-bottom: 2px solid #28a745; padding-bottom: 5px;">
                    Cambios de Stock Aplicados
                </h3>
                <p style="background-color: #d4edda; padding: 10px; border-radius: 5px; border-left: 4px solid #28a745;">
                    Los siguientes productos tuvieron actualizaciones de stock aplicadas en el sistema Holded.
                </p>
                <table style="border-collapse: collapse; width: 100%; max-width: 1000px; margin: 10px 0;">
                    <tr style="background-color: #28a745; color: black;">
                        <th style="border: 1px solid #ddd; padding: 12px; text-align: left;">SKU</th>
                        <th style="border: 1px solid #ddd; padding: 12px; text-align: left;">Producto</th>
                        <th style="border: 1px solid #ddd; padding: 12px; text-align: center;">Stock Anterior</th>
                        <th style="border: 1px solid #ddd; padding: 12px; text-align: center;">Stock Nuevo</th>
                        <th style="border: 1px solid #ddd; padding: 12px; text-align: center;">Acción</th>
                    </tr>
            """
            
            # Show all stock updates
            for i, update in enumerate(stock_updates):
                # Alternate row colors for better readability
                row_style = "background-color: #f9f9f9;" if i % 2 == 0 else "background-color: white;"
                
                old_stock = update.get('old_stock', 0)
                new_stock = update.get('new_stock', 0)
                action = update.get('action', 'update')
                product_name = update.get('product_name', 'N/A')
                
                # Style based on action and stock values
                if action == 'reset':
                    action_text = 'Reset a 0'
                    action_style = 'color: #dc3545; font-weight: bold;'  # Red for resets
                    new_stock_style = 'color: #dc3545; font-weight: bold;'
                else:
                    action_text = 'Actualización'
                    action_style = 'color: #28a745; font-weight: bold;'  # Green for updates
                    new_stock_style = 'color: #28a745; font-weight: bold;' if new_stock > old_stock else 'color: #ffc107; font-weight: bold;'
                
                # Format product name (truncate if too long)
                display_name = product_name[:30] + "..." if len(str(product_name)) > 30 else product_name
                
                html += f"""
                    <tr style="{row_style}">
                        <td style="border: 1px solid #ddd; padding: 8px; font-family: monospace; font-weight: bold;">{update.get('sku', 'N/A')}</td>
                        <td style="border: 1px solid #ddd; padding: 8px;" title="{product_name}">{display_name}</td>
                        <td style="border: 1px solid #ddd; padding: 8px; text-align: center; color: #6c757d;">{old_stock}</td>
                        <td style="border: 1px solid #ddd; padding: 8px; text-align: center; color: black;">{new_stock}</td>
                        <td style="border: 1px solid #ddd; padding: 8px; text-align: center; {new_stock_style}">{action_text}</td>
                    </tr>
                """
            
            html += "</table>"
            
            # Show total count
            html += f"""
            <p style="color: #28a745; font-weight: bold; margin-top: 10px;">
                Total de actualizaciones de stock aplicadas: {len(stock_updates)}
            </p>
            """
            
        
        # Enhanced New Products Section with Categorization
        html += self._create_enhanced_new_products_section(update_results)
        
        # Add Variant Consolidation Section
        html += self._create_variant_consolidation_section(update_results)
        
        # Add Automatic Deletion Results Section
        html += self._create_automatic_deletion_results_section(update_results)
        
        # Add Data Integrity Section
        html += self._create_data_integrity_section(update_results)
        
        # Keep legacy new products for backward compatibility
        new_products = update_results.get('new_products_for_creation', [])
        if new_products and not update_results.get('completely_new_products') and not update_results.get('new_variants_of_existing_products'):
            # Only show legacy section if enhanced data is not available
            html += self._format_new_products_html(new_products)
        
        # Agregar errores si los hay
        if update_results.get('errors'):
            html += """
            <div class="details">
                <h3 class="error">❌ Errores</h3>
                <ul>
            """
            
            for error in update_results['errors']:  # Show all errors
                html += f"<li class='error'>{error}</li>"
            
            
            html += "</ul></div>"
        
        # Add attachment and download section for new products
        html += self._create_attachments_and_downloads_section(update_results)
        
        html += """
            <div class="footer">
                <p>Esta es una notificación automática del Sistema de Actualización de Inventario.</p>
                <p>Si tiene alguna pregunta, por favor revise los logs del sistema para más detalles.</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _create_email_body_text(self, update_results: Dict[str, Any]) -> str:
        """
        Crea el cuerpo del email en texto plano con detalles de la actualización.
        
        Args:
            update_results: Diccionario de resultados de actualización
            
        Returns:
            Cadena del cuerpo del email en texto plano
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        text = f"""
REPORTE DE ACTUALIZACIÓN DE INVENTARIO
Tiempo de Ejecución: {timestamp}

RESUMEN
=======
Archivos Procesados: {update_results.get('processed_files', 0)}
Productos Procesados: {update_results.get('processed_products', 0)}
Actualizaciones de Stock: {update_results.get('stock_updates', 0)}
Stock Resets (Conway SKUs no en archivos): {update_results.get('stock_resets', 0)}
SKUs Omitidos (no Conway): {update_results.get('skipped_not_in_holded', 0)}
Productos Nuevos (Creación Manual): {len(update_results.get('new_products_for_creation', []))}
Errores: {len(update_results.get('errors', []))}
"""
        
        
        
        # Agregar actualizaciones de stock si las hay
        if 'summary' in update_results and update_results['summary'].get('stock_updates'):
            text += f"\n\nCAMBIOS DE STOCK - VARIANTES ({len(update_results['summary']['stock_updates'])})\n"
            text += "=" * 60 + "\n"
            
            for update in update_results['summary']['stock_updates']:
                old_stock = update.get('old_stock', 0)
                new_stock = update.get('new_stock', 0)
                action = update.get('action', 'update')
                product_name = update.get('product_name', 'N/A')[:30]  # Limit name length
                action_text = 'RESET' if action == 'reset' else 'UPDATE'
                
                text += f"SKU: {update.get('sku', 'N/A')} | {product_name}\n"
                text += f"     {old_stock} -> {new_stock} [{action_text}]\n\n"
            
        
        # Agregar sección de productos nuevos si los hay
        new_products = update_results.get('new_products_for_creation', [])
        if new_products:
            text += self._format_new_products_text(new_products)
        
        # Agregar errores si los hay
        if update_results.get('errors'):
            text += f"\n\nERRORES ({len(update_results['errors'])})\n"
            text += "=" * 50 + "\n"
            
            for error in update_results['errors']:
                text += f"- {error}\n"
        
        text += "\n\nEsta es una notificación automática del Sistema de Actualización de Inventario.\n"
        
        return text
    
    def _format_new_products_html(self, new_products: List[Dict[str, Any]]) -> str:
        """
        Formatea la sección HTML para productos nuevos que requieren creación manual.
        
        Args:
            new_products: Lista de productos nuevos encontrados en Excel pero no en Holded
            
        Returns:
            Cadena HTML con la tabla de productos nuevos
        """
        if not new_products:
            return ""
        
        self.logger.info(f"Formatting {len(new_products)} new products for HTML display")
        if new_products:
            self.logger.info(f"Sample product data: {new_products[0]}")
            self.logger.info(f"First product name: '{new_products[0].get('name', 'NOT_FOUND')}'")
            self.logger.info(f"First product source file: '{new_products[0].get('source_file', 'Unknown')}'")
            source_file = new_products[0].get('source_file', 'Unknown')
            if '/' in source_file:
                source_file = source_file.split('/')[-1]
        
        html = f"""
        <div class="details" style="margin-top: 30px;">
            <h3 style="color: #007bff; border-bottom: 2px solid #007bff; padding-bottom: 5px;">
                Productos Nuevos - Requieren Creación Manual en Holded
            </h3>
            <p style="background-color: #e7f3ff; padding: 10px; border-radius: 5px; border-left: 4px solid #007bff;">
                Los siguientes productos se encontraron en los archivos de Excel pero no existen en Holded. 
                Se requiere revisión manual para crear estos productos en el sistema.
            </p>
            <h3>Archivo: <span style="font-weight: normal;">{source_file}</span></h3>
            <table style="border-collapse: collapse; width: 100%; max-width: 1000px; margin: 10px 0;">
                <tr style="background-color: #007bff; color: black;">
                    <th style="border: 1px solid #ddd; padding: 12px; text-align: left;">SKU</th>
                    <th style="border: 1px solid #ddd; padding: 12px; text-align: left;">Nombre</th>
                    <th style="border: 1px solid #ddd; padding: 12px; text-align: left;">Stock</th>
                    <th style="border: 1px solid #ddd; padding: 12px; text-align: left;">Precio</th>
                </tr>
        """
        
        # Show all products
        display_products = new_products
        
        for i, product in enumerate(display_products):
            # Alternate row colors for better readability
            row_style = "background-color: #f9f9f9;" if i % 2 == 0 else "background-color: white;"
            
            # Format stock with highlighting for non-zero values
            stock = product.get('stock', 0)
            stock_style = "font-weight: bold; color: #28a745;" if stock > 0 else "color: #6c757d;"
            
            # Format price
            price = product.get('price', 'N/A')
            price_display = f"{price}€" if isinstance(price, (int, float)) else str(price)
            
            # Use product name if available, otherwise use SKU
            name = product.get('name', '')
            if i == 0:  # Only log for first product
                self.logger.info(f"Processing product: SKU='{product.get('sku')}', name='{name}', has_name={bool(name and name.strip())}")
            
            if name and name.strip():
                display_name = name[:40] + "..." if len(name) > 40 else name
                if i == 0:
                    self.logger.info(f"Using product name: '{display_name}'")
            else:
                display_name = f"Producto {product.get('sku', 'N/A')}"
                if i == 0:
                    self.logger.info(f"Using SKU fallback: '{display_name}'")
            
            # Get filename from full path
            source_file = product.get('source_file', 'Unknown')
            if '/' in source_file:
                source_file = source_file.split('/')[-1]
            
            html += f"""
                <tr style="{row_style}">
                    <td style="border: 1px solid #ddd; padding: 8px; font-family: monospace; font-weight: bold;">{product.get('sku', 'N/A')}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{display_name}</td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: center; color: black;">{stock}</td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{price_display}</td>
                </tr>
            """
        
        html += "</table>"
        
        # Show total count
        html += f"""
        <p style="color: #007bff; font-weight: bold; margin-top: 10px;">
            Total de productos nuevos encontrados: {len(new_products)}
        </p>
        """
        
        # Add action instructions
        html += """
        <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 5px; padding: 15px; margin-top: 15px;">
            <h4 style="color: #856404; margin-top: 0;">🔧 Acciones Requeridas:</h4>
            <ul style="color: #856404; margin-bottom: 0;">
                <li>Revisar cada producto para determinar si debe crearse en Holded</li>
                <li>Para productos válidos, crear manualmente en Holded con la categoría Conway</li>
                <li>Verificar que el SKU coincida exactamente con el archivo Excel</li>
                <li>Configurar el stock inicial según se muestra en la tabla</li>
            </ul>
        </div>
        </div>
        """
        
        return html
    
    def _format_new_products_text(self, new_products: List[Dict[str, Any]]) -> str:
        """
        Formatea la sección de texto plano para productos nuevos.
        
        Args:
            new_products: Lista de productos nuevos encontrados en Excel pero no en Holded
            
        Returns:
            Cadena de texto plano con los productos nuevos
        """
        if not new_products:
            return ""
        
        text = f"\n\nPRODUCTOS NUEVOS REQUIEREN CREACIÓN MANUAL ({len(new_products)})\n"
        text += "=" * 70 + "\n"
        text += "Los siguientes productos se encontraron en Excel pero NO existen en Holded:\n\n"
        
        # Display all products in text format
        display_products = new_products
        
        for product in display_products:
            # Use product name if available, otherwise use SKU  
            name = product.get('name', '')
            if product == display_products[0]:  # Only log for first product
                self.logger.info(f"Text format - Processing product: SKU='{product.get('sku')}', name='{name}', has_name={bool(name and name.strip())}")
            
            if name and name.strip():
                display_name = name[:35] + "..." if len(name) > 35 else name
                if product == display_products[0]:
                    self.logger.info(f"Text format - Using product name: '{display_name}'")
            else:
                display_name = f"Producto {product.get('sku', 'N/A')}"
                if product == display_products[0]:
                    self.logger.info(f"Text format - Using SKU fallback: '{display_name}'")
            
            price = product.get('price', 'N/A')
            price_display = f"{price}€" if isinstance(price, (int, float)) else str(price)
            
            source_file = product.get('source_file', 'Unknown')
            if '/' in source_file:
                source_file = source_file.split('/')[-1]
            
            text += f"SKU: {product.get('sku', 'N/A')}\n"
            text += f"     Nombre: {display_name}\n"
            text += f"     Stock: {product.get('stock', 0)} | Precio: {price_display}\n"
            text += f"     Oferta: {'Sí' if product.get('is_offer', False) else 'No'} | Archivo: {source_file}\n\n"
        
        text += f"Total de productos nuevos: {len(new_products)}\n\n"
        
        text += "ACCIONES REQUERIDAS:\n"
        text += "- Revisar cada producto para validar si debe crearse en Holded\n"
        text += "- Crear manualmente en Holded con categoría Conway\n"
        text += "- Verificar coincidencia exacta del SKU\n"
        text += "- Configurar stock inicial según se indica\n"
        
        return text
    
    def _create_error_email_html(self, error_details: Dict[str, Any]) -> str:
        """Crea email HTML para notificaciones de error."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; margin: 20px;">
            <div style="background-color: #f8d7da; color: #721c24; padding: 20px; border-radius: 5px;">
                <h2>❌ Error de Actualización de Inventario</h2>
                <p><strong>Hora:</strong> {timestamp}</p>
                <p><strong>Error:</strong> {error_details.get('message', 'Ocurrió un error desconocido')}</p>
            </div>
            
            <div style="margin: 20px 0;">
                <h3>Detalles:</h3>
                <pre style="background-color: #f8f9fa; padding: 15px; border-radius: 5px;">
{error_details.get('details', 'No hay detalles adicionales disponibles')}
                </pre>
            </div>
            
            <p>Por favor revise los logs del sistema y reintente la operación si es necesario.</p>
        </body>
        </html>
        """
        
        return html
    
    def _create_error_email_text(self, error_details: Dict[str, Any]) -> str:
        """Crea email en texto plano para notificaciones de error."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        text = f"""
ERROR DE ACTUALIZACIÓN DE INVENTARIO
Hora: {timestamp}

ERROR: {error_details.get('message', 'Ocurrió un error desconocido')}

DETALLES:
{error_details.get('details', 'No hay detalles adicionales disponibles')}

Por favor revise los logs del sistema y reintente la operación si es necesario.
"""
        
        return text
    
    def _create_enhanced_new_products_section(self, update_results: Dict[str, Any]) -> str:
        """Create enhanced new products section with categorization."""
        completely_new = update_results.get('completely_new_products', [])
        new_variants = update_results.get('new_variants_of_existing_products', [])
        
        if not completely_new and not new_variants:
            return ""
        
        html = ""
        
        # Completely New Products Section
        if completely_new:
            html += f"""
            <div class="details" style="margin-top: 30px;">
                <h3 style="color: #007bff; border-bottom: 2px solid #007bff; padding-bottom: 5px;">
                    🆕 Productos Completamente Nuevos ({len(completely_new)})
                </h3>
                <p style="background-color: #e7f3ff; padding: 10px; border-radius: 5px; border-left: 4px solid #007bff;">
                    Los siguientes productos son completamente nuevos y requieren creación manual en Holded.
                </p>
                <table>
                    <thead>
                        <tr>
                            <th>SKU</th>
                            <th>Nombre del Producto</th>
                            <th>Stock</th>
                            <th>Talla</th>
                            <th>Color</th>
                            <th>Medida Rueda</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            for product in completely_new:  # Show all products
                html += f"""
                        <tr>
                            <td>{product.get('sku', 'N/A')}</td>
                            <td>{product.get('name', 'N/A')[:30]}...</td>
                            <td>{product.get('stock', 0)}</td>
                            <td>{product.get('size', 'N/A')}</td>
                            <td>{product.get('color', 'N/A')}</td>
                            <td>{product.get('ws', 'N/A')}</td>
                        </tr>
                """
            
            
            html += """
                    </tbody>
                </table>
            </div>
            """
        
        # New Variants Section
        if new_variants:
            html += f"""
            <div class="details" style="margin-top: 30px;">
                <h3 style="color: #ffc107; border-bottom: 2px solid #ffc107; padding-bottom: 5px;">
                    🔄 Nuevas Variantes de Productos Existentes ({len(new_variants)})
                </h3>
                <p style="background-color: #fff3cd; padding: 10px; border-radius: 5px; border-left: 4px solid #ffc107;">
                    Los siguientes productos son nuevas variantes (tallas/colores) de productos que ya existen en Holded.
                    Los productos existentes serán eliminados y re-importados con todas las variantes.
                </p>
                <table>
                    <thead>
                        <tr>
                            <th>SKU Variante</th>
                            <th>Nombre del Producto</th>
                            <th>Nueva Talla</th>
                            <th>Nuevo Color</th>
                            <th>Stock</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            for product in new_variants:  # Show all variants
                html += f"""
                        <tr>
                            <td>{product.get('sku', 'N/A')}</td>
                            <td>{product.get('name', 'N/A')[:25]}...</td>
                            <td>{product.get('size', 'N/A')}</td>
                            <td>{product.get('color', 'N/A')}</td>
                            <td>{product.get('stock', 0)}</td>
                        </tr>
                """
            
            
            html += """
                    </tbody>
                </table>
            </div>
            """
        
        return html
    
    def _create_variant_consolidation_section(self, update_results: Dict[str, Any]) -> str:
        """Create variant consolidation section."""
        products_for_deletion = update_results.get('products_for_deletion', [])
        
        if not products_for_deletion:
            return ""
        
        html = f"""
        <div class="details" style="margin-top: 30px;">
            <h3 style="color: #dc3545; border-bottom: 2px solid #dc3545; padding-bottom: 5px;">
                🗑️ Productos Programados para Eliminación y Re-importación ({len(products_for_deletion)})
            </h3>
            <p style="background-color: #f8d7da; padding: 10px; border-radius: 5px; border-left: 4px solid #dc3545;">
                Los siguientes productos existentes serán eliminados de Holded antes de la importación 
                para consolidar todas sus variantes bajo un único producto principal.
            </p>
            <table>
                <thead>
                    <tr>
                        <th>Producto ID</th>
                        <th>Nombre del Producto</th>
                        <th>Variantes Existentes</th>
                        <th>Acción</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for product in products_for_deletion:  # Show all products scheduled for deletion
            html += f"""
                    <tr>
                        <td>{product.get('product_id', 'N/A')}</td>
                        <td>{product.get('product_name', 'N/A')[:30]}...</td>
                        <td>{product.get('existing_variants_count', 0)}</td>
                        <td style="color: #dc3545;">Eliminar y Re-importar</td>
                    </tr>
            """
        
        
        html += """
                </tbody>
            </table>
        </div>
        """
        
        return html
    
    def _create_automatic_deletion_results_section(self, update_results: Dict[str, Any]) -> str:
        """Create automatic deletion results section."""
        deletion_results = update_results.get('deletion_results', {})
        
        if not deletion_results or deletion_results.get('total_scheduled', 0) == 0:
            return ""
        
        total_scheduled = deletion_results.get('total_scheduled', 0)
        successful = deletion_results.get('successful_deletions', 0)
        failed = deletion_results.get('failed_deletions', 0)
        deletion_details = deletion_results.get('deletion_details', [])
        success_rate = (successful / total_scheduled * 100) if total_scheduled > 0 else 0
        
        # Choose color based on success rate
        if success_rate == 100:
            color = "#28a745"  # Green for 100% success
            emoji = "✅"
            status_text = "Eliminación Automática Completada"
        elif success_rate >= 75:
            color = "#ffc107"  # Yellow for 75-99% success
            emoji = "⚠️"
            status_text = "Eliminación Automática Parcialmente Exitosa"
        else:
            color = "#dc3545"  # Red for <75% success
            emoji = "❌"
            status_text = "Eliminación Automática con Errores"
        
        html = f"""
        <div class="details" style="margin-top: 30px;">
            <h3 style="color: {color}; border-bottom: 2px solid {color}; padding-bottom: 5px;">
                {emoji} {status_text} ({successful}/{total_scheduled})
            </h3>
            <p style="background-color: {'#d4edda' if success_rate == 100 else '#fff3cd' if success_rate >= 75 else '#f8d7da'}; 
                      padding: 10px; border-radius: 5px; border-left: 4px solid {color};">
                {'Los productos existentes fueron eliminados automáticamente de Holded para permitir la consolidación de variantes.' if success_rate == 100 else
                 f'Se eliminaron automáticamente {successful} de {total_scheduled} productos. {failed} productos requieren eliminación manual.' if success_rate >= 75 else
                 f'La eliminación automática falló para {failed} de {total_scheduled} productos. Se requiere intervención manual.'}
            </p>
            <table>
                <thead>
                    <tr>
                        <th>Producto ID</th>
                        <th>Nombre del Producto</th>
                        <th>Variantes Eliminadas</th>
                        <th>Estado</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for detail in deletion_details:  # Show all deletion results
            product_id = detail.get('product_id', 'N/A')
            product_name = detail.get('product_name', 'N/A')
            variants_count = detail.get('variants_count', 0)
            status = detail.get('status', 'unknown')
            
            if status == 'success':
                status_display = '<span style="color: #28a745; font-weight: bold;">✅ Eliminado</span>'
            elif status == 'failed':
                status_display = '<span style="color: #dc3545; font-weight: bold;">❌ Falló</span>'
            else:
                status_display = '<span style="color: #6c757d; font-weight: bold;">💥 Error</span>'
            
            html += f"""
                    <tr>
                        <td>{product_id[:20]}...</td>
                        <td>{product_name[:30]}...</td>
                        <td>{variants_count}</td>
                        <td>{status_display}</td>
                    </tr>
            """
        
        # Add summary row
        html += f"""
                    <tr style="background-color: #f8f9fa; border-top: 2px solid #dee2e6;">
                        <td colspan="4" style="text-align: center; font-weight: bold; padding: 12px;">
                            Tasa de Éxito: {success_rate:.1f}% ({successful}/{total_scheduled})
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
        """
        
        # Add action needed message if there were failures
        if failed > 0:
            html += f"""
            <div style="background-color: #f8d7da; border: 1px solid #f5c6cb; border-radius: 5px; padding: 10px; margin-top: 10px;">
                <p style="margin: 0; color: #721c24; font-size: 14px;">
                    <strong>⚠️ Acción Requerida:</strong> {failed} productos no pudieron ser eliminados automáticamente. 
                    Elimine manualmente estos productos de Holded antes de importar el archivo CSV para evitar conflictos de SKU.
                </p>
            </div>
            """
        
        return html
    
    def _create_attachments_and_downloads_section(self, update_results: Dict[str, Any]) -> str:
        """Create section for attachments and downloads based on available data."""
        # Check if we have new products that require files
        new_products = update_results.get('new_products_for_creation', [])
        completely_new = update_results.get('completely_new_products', [])
        new_variants = update_results.get('new_variants_of_existing_products', [])
        images_download_link = update_results.get('images_download_link')
        
        
        # Check if we have any new products to process
        has_new_products = bool(new_products or completely_new or new_variants)
        
        if not has_new_products:
            return ""
        
        html = """
        <div class="details" style="margin-top: 30px; background-color: #e7f3ff; border: 2px solid #007bff; border-radius: 8px; padding: 20px;">
            <h3 style="color: #007bff; margin-top: 0;">📎 Archivos para Importación</h3>
            <p style="margin-bottom: 15px;">Los siguientes archivos están disponibles para facilitar la importación de productos:</p>
            <ul style="margin: 0; padding-left: 20px;">
                <li><strong>Conway Products Import.csv</strong> - Archivo adjunto listo para importar a Holded con formato correcto</li>
        """
        
        # Handle images based on whether we have download link or attachment
        if images_download_link and images_download_link != "UPLOADED_NO_LINK":
            # Enhanced workflow with Dropbox link
            html += f"""
                <li><strong>Imágenes de Productos</strong> - Disponibles para descarga en Dropbox 
                    <div style="margin-top: 8px;">
                        <a href="{images_download_link}" 
                           style="background-color: #007bff; color: white; padding: 8px 16px; 
                                  text-decoration: none; border-radius: 4px; font-weight: bold;">
                            📥 Descargar Imágenes ZIP
                        </a>
                    </div>
                </li>
            """
        elif images_download_link == "UPLOADED_NO_LINK":
            # Images uploaded but no shareable link available  
            html += """
                <li><strong>Imágenes de Productos</strong> - Subidas exitosamente a Dropbox
                    <div style="margin-top: 8px; padding: 8px; background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 4px;">
                        <span style="color: #856404; font-size: 14px;">
                            ⚠️ Las imágenes están disponibles en Dropbox en la carpeta '/stock-update/conway_product_images.zip' 
                            pero no se pudo generar un enlace de descarga público debido a configuración de permisos.
                        </span>
                    </div>
                </li>
            """
        else:
            # Legacy workflow or no images available
            html += """
                <li><strong>Product Images.zip</strong> - Imágenes de productos (si están disponibles como archivo adjunto)</li>
            """
        
        html += """
            </ul>
            <div style="background-color: #d1ecf1; border: 1px solid #bee5eb; border-radius: 5px; padding: 10px; margin-top: 15px;">
                <p style="margin: 0; color: #0c5460; font-size: 14px;">
                    💡 <strong>Instrucciones:</strong> 
        """
        
        if images_download_link and images_download_link != "UPLOADED_NO_LINK":
            html += """
                    Descargue el archivo CSV adjunto e impórtelo a Holded. Para las imágenes, haga clic en el botón de descarga 
                    para obtener el archivo ZIP desde Dropbox. Las imágenes se organizan por producto y están listas para usar.
            """
        elif images_download_link == "UPLOADED_NO_LINK":
            html += """
                    Descargue el archivo CSV adjunto e impórtelo a Holded. Las imágenes están disponibles en su cuenta de Dropbox 
                    en la carpeta '/stock-update/conway_product_images.zip'. Acceda manualmente a Dropbox para descargar las imágenes.
            """
        else:
            html += """
                    Descargue los archivos adjuntos y utilícelos para importar los productos nuevos a Holded. 
                    El archivo CSV contiene toda la información necesaria con el formato correcto para importación directa.
            """
        
        html += """
                </p>
            </div>
        </div>
        """
        
        return html
    
    def _create_data_integrity_section(self, update_results: Dict[str, Any]) -> str:
        """Create data integrity issues section."""
        data_issues = update_results.get('data_integrity_issues', [])
        processing_metadata = update_results.get('processing_metadata', {})
        
        if not data_issues and not processing_metadata.get('failed_lookups'):
            return ""
        
        # Combine issues from both sources
        all_issues = list(data_issues)
        if processing_metadata.get('failed_lookups'):
            all_issues.extend(processing_metadata['failed_lookups'])
        
        if not all_issues:
            return ""
        
        html = f"""
        <div class="details" style="margin-top: 30px;">
            <h3 style="color: #6f42c1; border-bottom: 2px solid #6f42c1; padding-bottom: 5px;">
                ⚠️ Problemas de Integridad de Datos ({len(all_issues)})
            </h3>
            <p style="background-color: #f3e5ff; padding: 10px; border-radius: 5px; border-left: 4px solid #6f42c1;">
                Los siguientes productos estaban en el archivo de stock pero no pudieron ser procesados 
                debido a problemas con la información EAN o datos faltantes.
            </p>
            <table>
                <thead>
                    <tr>
                        <th>SKU</th>
                        <th>Nombre del Producto</th>
                        <th>Razón del Fallo</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for issue in all_issues:  # Show all data integrity issues
            html += f"""
                    <tr>
                        <td>{issue.get('sku', 'N/A')}</td>
                        <td>{issue.get('name', 'N/A')[:25]}...</td>
                        <td style="font-size: 12px; color: #666;">{issue.get('reason', 'Razón desconocida')}</td>
                    </tr>
            """
        
        
        # Add processing statistics if available
        if processing_metadata:
            success_rate = processing_metadata.get('success_rate', 0)
            html += f"""
                    <tr style="background-color: #f8f9fa;">
                        <td colspan="3" style="text-align: center; font-weight: bold;">
                            Tasa de Éxito del Procesamiento: {success_rate:.1f}% 
                            ({processing_metadata.get('output_products', 0)}/{processing_metadata.get('input_products', 0)} productos)
                        </td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
            <div style="background-color: #e9ecef; border: 1px solid #dee2e6; border-radius: 5px; padding: 10px; margin-top: 10px;">
                <p style="margin: 0; color: #495057; font-size: 14px;">
                    💡 <strong>Acción Recomendada:</strong> Revise estos productos manualmente para verificar que 
                    la información EAN esté correcta en el archivo 'Información_EAN_Conway_2025.csv' o que 
                    los productos tengan todos los datos requeridos.
                </p>
            </div>
        </div>
        """
        
        return html


def send_update_notification(update_results: Dict[str, Any], attachment_files: Optional[Dict[str, str]] = None) -> bool:
    """
    Función principal para enviar email de notificación de actualización.
    
    Args:
        update_results: Diccionario que contiene resultados de la actualización
        attachment_files: Diccionario opcional con archivos adjuntos {'nombre': 'ruta_archivo'}
        
    Returns:
        True si el email se envió exitosamente, False en caso contrario
    """
    notifier = EmailNotifier()
    
    try:
        # Enviar email de confirmación
        success = notifier.send_update_confirmation(update_results, attachment_files)
        
        return success
        
    except Exception as e:
        logging.error(f"Error enviando notificación de actualización: {e}")
        return False


def send_error_notification(error_message: str, error_details: str = "") -> bool:
    """
    Función principal para enviar email de notificación de error.
    
    Args:
        error_message: Mensaje principal de error
        error_details: Detalles adicionales del error
        
    Returns:
        True si el email se envió exitosamente, False en caso contrario
    """
    notifier = EmailNotifier()
    
    try:
        error_info = {
            'message': error_message,
            'details': error_details
        }
        
        # Enviar notificación de error
        success = notifier.send_error_notification(error_info)
        
        return success
        
    except Exception as e:
        logging.error(f"Error enviando notificación de error: {e}")
        return False 