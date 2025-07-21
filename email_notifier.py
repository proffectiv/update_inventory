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
from typing import Dict, Any, List
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
    
    def send_update_confirmation(self, update_results: Dict[str, Any]) -> bool:
        """
        Envía confirmación por email de las actualizaciones de inventario.
        
        Args:
            update_results: Diccionario que contiene resultados y estadísticas de la actualización
            
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
                body_text=body_text
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
    
    def _send_email(self, to_email: str, subject: str, body_html: str, body_text: str) -> bool:
        """
        Envía email vía SMTP de Strato.
        
        Args:
            to_email: Dirección de email del destinatario
            subject: Asunto del email
            body_html: Cuerpo del email en HTML
            body_text: Cuerpo del email en texto plano
            
        Returns:
            True si es exitoso, False en caso contrario
        """
        try:
            # Crear mensaje
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.username
            msg['To'] = to_email
            
            # Agregar versiones en texto plano y HTML
            part1 = MIMEText(body_text, 'plain', 'utf-8')
            part2 = MIMEText(body_html, 'html', 'utf-8')
            
            msg.attach(part1)
            msg.attach(part2)
            
            # Conectar al servidor SMTP y enviar email (usando SSL para puerto 465)
            self.logger.info(f"Conectando al servidor SMTP: {self.smtp_host}:{self.smtp_port}")
            
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port) as server:
                server.login(self.username, self.password)
                
                # Enviar email
                text = msg.as_string()
                server.sendmail(self.username, [to_email], text)
                
                self.logger.info(f"Email enviado exitosamente a {to_email}")
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
    
    def _create_email_subject(self, update_results: Dict[str, Any]) -> str:
        """
        Crea la línea de asunto del email basada en los resultados de la actualización.
        
        Args:
            update_results: Diccionario de resultados de actualización
            
        Returns:
            Cadena del asunto del email
        """
        stock_updates = update_results.get('stock_updates', 0)
        errors = len(update_results.get('errors', []))
        
        if errors > 0:
            return f"⚠️ Actualización de Inventario Completada con {errors} Errores"
        elif stock_updates > 0:
            return f"✅ Actualización de Inventario Exitosa - {stock_updates} Actualizaciones de Stock"
        else:
            return "ℹ️ Actualización de Inventario Completada - No se Requieren Cambios"
    
    def _create_email_body_html(self, update_results: Dict[str, Any]) -> str:
        """
        Crea el cuerpo del email en HTML con detalles de la actualización.
        
        Args:
            update_results: Diccionario de resultados de actualización
            
        Returns:
            Cadena del cuerpo del email en HTML
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
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
                <h2>📦 Actualización de Inventario</h2>
                <p><strong>Tiempo de Ejecución:</strong> {timestamp}</p>
            </div>
            
            <div class="summary">
                <h3>📊 Resumen</h3>
                <ul>
                    <li><strong>Archivos Procesados:</strong> {update_results.get('processed_files', 0)}</li>
                    <li><strong>Productos Procesados:</strong> {update_results.get('processed_products', 0)}</li>
                    <li><strong>Actualizaciones de Stock:</strong> <span class="success">{update_results.get('stock_updates', 0)}</span></li>
                    <li><strong>Errores:</strong> <span class="error">{len(update_results.get('errors', []))}</span></li>
                </ul>
            </div>
        """
        
        
        
        # Agregar detalles de actualizaciones de stock si los hay
        if 'summary' in update_results and update_results['summary'].get('stock_updates'):
            html += """
            <div class="details">
                <h3>📦 Actualizaciones de Stock</h3>
                <table>
                    <tr>
                        <th>SKU</th>
                        <th>Stock Anterior</th>
                        <th>Stock Nuevo</th>
                        <th>Cambio</th>
                    </tr>
            """
            
            for update in update_results['summary']['stock_updates'][:10]:  # Limit to first 10
                old_stock = update.get('old_stock', 0)
                new_stock = update.get('new_stock', 0)
                change = new_stock - old_stock
                change_str = f"+{change}" if change > 0 else str(change)
                
                html += f"""
                    <tr>
                        <td>{update.get('sku', 'N/A')}</td>
                        <td>{old_stock}</td>
                        <td>{new_stock}</td>
                        <td>{change_str}</td>
                    </tr>
                """
            
            if len(update_results['summary']['stock_updates']) > 10:
                html += f"<tr><td colspan='4'>... y {len(update_results['summary']['stock_updates']) - 10} más</td></tr>"
            
            html += "</table></div>"
        
        # Agregar errores si los hay
        if update_results.get('errors'):
            html += """
            <div class="details">
                <h3 class="error">❌ Errores</h3>
                <ul>
            """
            
            for error in update_results['errors'][:5]:  # Limit to first 5 errors
                html += f"<li class='error'>{error}</li>"
            
            if len(update_results['errors']) > 5:
                html += f"<li>... y {len(update_results['errors']) - 5} errores más</li>"
            
            html += "</ul></div>"
        
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
Errores: {len(update_results.get('errors', []))}
"""
        
        
        
        # Agregar actualizaciones de stock si las hay
        if 'summary' in update_results and update_results['summary'].get('stock_updates'):
            text += f"\n\nACTUALIZACIONES DE STOCK ({len(update_results['summary']['stock_updates'])})\n"
            text += "=" * 50 + "\n"
            
            for update in update_results['summary']['stock_updates'][:5]:
                old_stock = update.get('old_stock', 0)
                new_stock = update.get('new_stock', 0)
                change = new_stock - old_stock
                text += f"SKU: {update.get('sku', 'N/A')} | {old_stock} -> {new_stock} ({change:+d})\n"
            
            if len(update_results['summary']['stock_updates']) > 5:
                text += f"... y {len(update_results['summary']['stock_updates']) - 5} más\n"
        
        # Agregar errores si los hay
        if update_results.get('errors'):
            text += f"\n\nERRORES ({len(update_results['errors'])})\n"
            text += "=" * 50 + "\n"
            
            for error in update_results['errors'][:3]:
                text += f"- {error}\n"
            
            if len(update_results['errors']) > 3:
                text += f"... y {len(update_results['errors']) - 3} errores más\n"
        
        text += "\n\nEsta es una notificación automática del Sistema de Actualización de Inventario.\n"
        
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


def send_update_notification(update_results: Dict[str, Any]) -> bool:
    """
    Función principal para enviar email de notificación de actualización.
    
    Args:
        update_results: Diccionario que contiene resultados de la actualización
        
    Returns:
        True si el email se envió exitosamente, False en caso contrario
    """
    notifier = EmailNotifier()
    
    try:
        # Enviar email de confirmación
        success = notifier.send_update_confirmation(update_results)
        
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