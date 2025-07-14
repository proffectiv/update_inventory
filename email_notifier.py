"""
Email notifier module for sending confirmation emails.

This module handles:
- Connecting to Strato SMTP server
- Sending inventory update confirmation emails
- Formatting email content with update details
- Handling email delivery errors
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List
import logging
from datetime import datetime

from config import config


class EmailNotifier:
    """Handles email notifications via Strato SMTP."""
    
    def __init__(self):
        """Initialize email notifier with Strato SMTP configuration."""
        self.smtp_host = config.smtp_host
        self.smtp_port = config.smtp_port
        self.username = config.smtp_username
        self.password = config.smtp_password
        self.notification_email = config.notification_email
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def send_update_confirmation(self, update_results: Dict[str, Any]) -> bool:
        """
        Send email confirmation of inventory updates.
        
        Args:
            update_results: Dictionary containing update results and statistics
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        try:
            # Create email content
            subject = self._create_email_subject(update_results)
            body_html = self._create_email_body_html(update_results)
            body_text = self._create_email_body_text(update_results)
            
            # Send the email
            success = self._send_email(
                to_email=self.notification_email,
                subject=subject,
                body_html=body_html,
                body_text=body_text
            )
            
            if success:
                self.logger.info("Update confirmation email sent successfully")
            else:
                self.logger.error("Failed to send update confirmation email")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending update confirmation email: {e}")
            return False
    
    def send_error_notification(self, error_details: Dict[str, Any]) -> bool:
        """
        Send email notification about processing errors.
        
        Args:
            error_details: Dictionary containing error information
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        try:
            # Create error email content
            subject = "❌ Inventory Update Error - Action Required"
            body_html = self._create_error_email_html(error_details)
            body_text = self._create_error_email_text(error_details)
            
            # Send the email
            success = self._send_email(
                to_email=self.notification_email,
                subject=subject,
                body_html=body_html,
                body_text=body_text
            )
            
            if success:
                self.logger.info("Error notification email sent successfully")
            else:
                self.logger.error("Failed to send error notification email")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending error notification email: {e}")
            return False
    
    def _send_email(self, to_email: str, subject: str, body_html: str, body_text: str) -> bool:
        """
        Send email via Strato SMTP.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body_html: HTML email body
            body_text: Plain text email body
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.username
            msg['To'] = to_email
            
            # Add both plain text and HTML versions
            part1 = MIMEText(body_text, 'plain', 'utf-8')
            part2 = MIMEText(body_html, 'html', 'utf-8')
            
            msg.attach(part1)
            msg.attach(part2)
            
            # Connect to SMTP server and send email (using SSL for port 465)
            self.logger.info(f"Connecting to SMTP server: {self.smtp_host}:{self.smtp_port}")
            
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port) as server:
                server.login(self.username, self.password)
                
                # Send email
                text = msg.as_string()
                server.sendmail(self.username, [to_email], text)
                
                self.logger.info(f"Email sent successfully to {to_email}")
                return True
                
        except smtplib.SMTPAuthenticationError as e:
            self.logger.error(f"SMTP authentication failed: {e}")
            return False
        except smtplib.SMTPException as e:
            self.logger.error(f"SMTP error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error sending email: {e}")
            return False
    
    def _create_email_subject(self, update_results: Dict[str, Any]) -> str:
        """
        Create email subject line based on update results.
        
        Args:
            update_results: Update results dictionary
            
        Returns:
            Email subject string
        """
        price_updates = update_results.get('price_updates', 0)
        stock_updates = update_results.get('stock_updates', 0)
        errors = len(update_results.get('errors', []))
        
        # Check for variant warnings
        variant_warnings = []
        if 'details' in update_results:
            for file_detail in update_results['details']:
                if 'variant_warnings' in file_detail:
                    variant_warnings.extend(file_detail['variant_warnings'])
        
        # Also check summary for variant warnings
        if 'summary' in update_results and 'variant_warnings' in update_results['summary']:
            variant_warnings.extend(update_results['summary']['variant_warnings'])
        
        if errors > 0:
            return f"⚠️ Inventory Update Completed with {errors} Errors"
        elif variant_warnings:
            return f"⚠️ Inventory Update - {price_updates} Price, {stock_updates} Stock Updates + {len(variant_warnings)} Manual Required"
        elif price_updates > 0 or stock_updates > 0:
            return f"✅ Inventory Update Successful - {price_updates} Price, {stock_updates} Stock Updates"
        else:
            return "ℹ️ Inventory Update Completed - No Changes Required"
    
    def _create_email_body_html(self, update_results: Dict[str, Any]) -> str:
        """
        Create HTML email body with update details.
        
        Args:
            update_results: Update results dictionary
            
        Returns:
            HTML email body string
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
                <h2>📦 Inventory Update Report</h2>
                <p><strong>Execution Time:</strong> {timestamp}</p>
            </div>
            
            <div class="summary">
                <h3>📊 Summary</h3>
                <ul>
                    <li><strong>Files Processed:</strong> {update_results.get('processed_files', 0)}</li>
                    <li><strong>Products Processed:</strong> {update_results.get('processed_products', 0)}</li>
                    <li><strong>Price Updates:</strong> <span class="success">{update_results.get('price_updates', 0)}</span></li>
                    <li><strong>Stock Updates:</strong> <span class="success">{update_results.get('stock_updates', 0)}</span></li>
                    <li><strong>Errors:</strong> <span class="error">{len(update_results.get('errors', []))}</span></li>
                </ul>
            </div>
        """
        
        # Add price updates details if any
        if 'summary' in update_results and update_results['summary'].get('price_updates'):
            html += """
            <div class="details">
                <h3>💰 Price Updates</h3>
                <table>
                    <tr>
                        <th>SKU</th>
                        <th>Old Price</th>
                        <th>New Price</th>
                        <th>Offer</th>
                    </tr>
            """
            
            for update in update_results['summary']['price_updates'][:10]:  # Limit to first 10
                offer_tag = "🏷️ Yes" if update.get('is_offer', False) else "No"
                
                # Handle variant groups vs individual products
                if 'variant_skus' in update:
                    sku_display = f"Main Product (variants: {', '.join(update['variant_skus'][:3])}{'...' if len(update['variant_skus']) > 3 else ''})"
                else:
                    sku_display = update.get('sku', 'N/A')
                
                html += f"""
                    <tr>
                        <td>{sku_display}</td>
                        <td>€{update.get('old_price', 0):.2f}</td>
                        <td>€{update.get('new_price', 0):.2f}</td>
                        <td>{offer_tag}</td>
                    </tr>
                """
            
            if len(update_results['summary']['price_updates']) > 10:
                html += f"<tr><td colspan='4'>... and {len(update_results['summary']['price_updates']) - 10} more</td></tr>"
            
            html += "</table></div>"
        
        # Add variant warnings if any - organized by type
        variant_warnings = []
        if 'details' in update_results:
            for file_detail in update_results['details']:
                if 'variant_warnings' in file_detail:
                    variant_warnings.extend(file_detail['variant_warnings'])
        
        if variant_warnings:
            # Separate unified price updates from individual variant updates
            unified_warnings = [w for w in variant_warnings if w.get('type') == 'unified_price']
            individual_warnings = [w for w in variant_warnings if w.get('type') == 'individual_prices']
            
            if unified_warnings:
                html += """
                <div class="details">
                    <h3>💰 Global Product Price Updates Required</h3>
                    <p style="color: #f39c12; font-weight: bold;">The following products with variants need unified price updates (same price for all variants):</p>
                    <table>
                        <tr>
                            <th>Product</th>
                            <th>Current Price</th>
                            <th>New Price</th>
                            <th>Variants Affected</th>
                            <th>Offer</th>
                        </tr>
                """
                
                for warning in unified_warnings[:10]:  # Limit to first 10
                    unified = warning['unified_price']
                    current_price = unified.get('current_price', 'N/A')
                    current_price_str = f"€{current_price:.2f}" if current_price != 'N/A' else 'N/A'
                    offer_tag = "🏷️ Yes" if unified.get('is_offer', False) else "No"
                    
                    variant_display = f"{unified['variant_count']} variants"
                    if len(unified['variant_skus']) <= 3:
                        variant_display += f"<br><small>({', '.join(unified['variant_skus'])})</small>"
                    else:
                        variant_display += f"<br><small>({', '.join(unified['variant_skus'][:3])}...)</small>"
                    
                    html += f"""
                        <tr>
                            <td>{warning['main_product_name']}<br><small>ID: {warning['main_product_id']}</small></td>
                            <td>{current_price_str}</td>
                            <td>€{unified['new_price']:.2f}</td>
                            <td>{variant_display}</td>
                            <td>{offer_tag}</td>
                        </tr>
                    """
                
                if len(unified_warnings) > 10:
                    html += f"<tr><td colspan='5'>... and {len(unified_warnings) - 10} more products</td></tr>"
                
                html += "</table></div>"
            
            if individual_warnings:
                html += """
                <div class="details">
                    <h3>⚠️ Individual Variant Price Updates Required</h3>
                    <p style="color: #e74c3c; font-weight: bold;">The following variants have different prices and require individual updates in Holded:</p>
                    <table>
                        <tr>
                            <th>SKU</th>
                            <th>Product</th>
                            <th>Current Price</th>
                            <th>New Price</th>
                            <th>Offer</th>
                            <th>Variant Details</th>
                        </tr>
                """
                
                for warning in individual_warnings[:5]:  # Limit to first 5 products
                    for variant in warning['variant_prices'][:10]:  # Show up to 10 variants per product
                        current_price = variant.get('current_price', 'N/A')
                        current_price_str = f"€{current_price:.2f}" if current_price != 'N/A' else 'N/A'
                        offer_tag = "🏷️ Yes" if variant.get('is_offer', False) else "No"
                        
                        html += f"""
                            <tr>
                                <td><strong>{variant['sku']}</strong></td>
                                <td>{warning['main_product_name']}</td>
                                <td>{current_price_str}</td>
                                <td>€{variant['new_price']:.2f}</td>
                                <td>{offer_tag}</td>
                                <td><small>{variant['variant_details']}</small></td>
                            </tr>
                        """
                
                if len(individual_warnings) > 5:
                    html += f"<tr><td colspan='6'>... and {len(individual_warnings) - 5} more products with individual variants</td></tr>"
                
                html += "</table></div>"
        
        # Add stock updates details if any
        if 'summary' in update_results and update_results['summary'].get('stock_updates'):
            html += """
            <div class="details">
                <h3>📦 Stock Updates</h3>
                <table>
                    <tr>
                        <th>SKU</th>
                        <th>Old Stock</th>
                        <th>New Stock</th>
                        <th>Change</th>
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
                html += f"<tr><td colspan='4'>... and {len(update_results['summary']['stock_updates']) - 10} more</td></tr>"
            
            html += "</table></div>"
        
        # Add errors if any
        if update_results.get('errors'):
            html += """
            <div class="details">
                <h3 class="error">❌ Errors</h3>
                <ul>
            """
            
            for error in update_results['errors'][:5]:  # Limit to first 5 errors
                html += f"<li class='error'>{error}</li>"
            
            if len(update_results['errors']) > 5:
                html += f"<li>... and {len(update_results['errors']) - 5} more errors</li>"
            
            html += "</ul></div>"
        
        html += """
            <div class="footer">
                <p>This is an automated notification from the Inventory Update System.</p>
                <p>If you have any questions, please check the system logs for more details.</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _create_email_body_text(self, update_results: Dict[str, Any]) -> str:
        """
        Create plain text email body with update details.
        
        Args:
            update_results: Update results dictionary
            
        Returns:
            Plain text email body string
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        text = f"""
INVENTORY UPDATE REPORT
Execution Time: {timestamp}

SUMMARY
=======
Files Processed: {update_results.get('processed_files', 0)}
Products Processed: {update_results.get('processed_products', 0)}
Price Updates: {update_results.get('price_updates', 0)}
Stock Updates: {update_results.get('stock_updates', 0)}
Errors: {len(update_results.get('errors', []))}
"""
        
        # Add price updates if any
        if 'summary' in update_results and update_results['summary'].get('price_updates'):
            text += f"\n\nPRICE UPDATES ({len(update_results['summary']['price_updates'])})\n"
            text += "=" * 50 + "\n"
            
            for update in update_results['summary']['price_updates'][:5]:
                offer = " (OFFER)" if update.get('is_offer', False) else ""
                text += f"SKU: {update.get('sku', 'N/A')} | {update.get('old_price', 0):.2f} -> {update.get('new_price', 0):.2f}{offer}\n"
            
            if len(update_results['summary']['price_updates']) > 5:
                text += f"... and {len(update_results['summary']['price_updates']) - 5} more\n"
        
        # Add variant warnings if any - organized by type
        variant_warnings = []
        if 'details' in update_results:
            for file_detail in update_results['details']:
                if 'variant_warnings' in file_detail:
                    variant_warnings.extend(file_detail['variant_warnings'])
        
        if variant_warnings:
            # Separate unified price updates from individual variant updates
            unified_warnings = [w for w in variant_warnings if w.get('type') == 'unified_price']
            individual_warnings = [w for w in variant_warnings if w.get('type') == 'individual_prices']
            
            if unified_warnings:
                text += f"\n\nGLOBAL PRODUCT PRICE UPDATES REQUIRED ({len(unified_warnings)})\n"
                text += "=" * 50 + "\n"
                text += "These products need unified price updates (same price for all variants):\n\n"
                
                for warning in unified_warnings[:5]:
                    unified = warning['unified_price']
                    current_price = unified.get('current_price', 'N/A')
                    current_price_str = f"€{current_price:.2f}" if current_price != 'N/A' else 'N/A'
                    offer_text = " (OFFER)" if unified.get('is_offer', False) else ""
                    
                    text += f"Product: {warning['main_product_name']}\n"
                    text += f"Price: {current_price_str} -> €{unified['new_price']:.2f}{offer_text}\n"
                    text += f"Affects: {unified['variant_count']} variants ({', '.join(unified['variant_skus'][:3])}{'...' if len(unified['variant_skus']) > 3 else ''})\n"
                    text += f"ID: {warning['main_product_id']}\n\n"
                
                if len(unified_warnings) > 5:
                    text += f"... and {len(unified_warnings) - 5} more products\n"
            
            if individual_warnings:
                text += f"\n\nINDIVIDUAL VARIANT PRICE UPDATES REQUIRED\n"
                text += "=" * 50 + "\n"
                text += "These variants have different prices and need individual updates:\n\n"
                
                for warning in individual_warnings[:3]:
                    text += f"Product: {warning['main_product_name']} (ID: {warning['main_product_id']})\n"
                    for variant in warning['variant_prices'][:5]:
                        current_price = variant.get('current_price', 'N/A')
                        current_price_str = f"€{current_price:.2f}" if current_price != 'N/A' else 'N/A'
                        offer_text = " (OFFER)" if variant.get('is_offer', False) else ""
                        text += f"  - {variant['sku']}: {current_price_str} -> €{variant['new_price']:.2f}{offer_text}\n"
                        text += f"    Details: {variant['variant_details']}\n"
                    if len(warning['variant_prices']) > 5:
                        text += f"  ... and {len(warning['variant_prices']) - 5} more variants\n"
                    text += "\n"
                
                if len(individual_warnings) > 3:
                    text += f"... and {len(individual_warnings) - 3} more products with individual variants\n"
        
        # Add stock updates if any
        if 'summary' in update_results and update_results['summary'].get('stock_updates'):
            text += f"\n\nSTOCK UPDATES ({len(update_results['summary']['stock_updates'])})\n"
            text += "=" * 50 + "\n"
            
            for update in update_results['summary']['stock_updates'][:5]:
                old_stock = update.get('old_stock', 0)
                new_stock = update.get('new_stock', 0)
                change = new_stock - old_stock
                text += f"SKU: {update.get('sku', 'N/A')} | {old_stock} -> {new_stock} ({change:+d})\n"
            
            if len(update_results['summary']['stock_updates']) > 5:
                text += f"... and {len(update_results['summary']['stock_updates']) - 5} more\n"
        
        # Add errors if any
        if update_results.get('errors'):
            text += f"\n\nERRORS ({len(update_results['errors'])})\n"
            text += "=" * 50 + "\n"
            
            for error in update_results['errors'][:3]:
                text += f"- {error}\n"
            
            if len(update_results['errors']) > 3:
                text += f"... and {len(update_results['errors']) - 3} more errors\n"
        
        text += "\n\nThis is an automated notification from the Inventory Update System.\n"
        
        return text
    
    def _create_error_email_html(self, error_details: Dict[str, Any]) -> str:
        """Create HTML email for error notifications."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; margin: 20px;">
            <div style="background-color: #f8d7da; color: #721c24; padding: 20px; border-radius: 5px;">
                <h2>❌ Inventory Update Error</h2>
                <p><strong>Time:</strong> {timestamp}</p>
                <p><strong>Error:</strong> {error_details.get('message', 'Unknown error occurred')}</p>
            </div>
            
            <div style="margin: 20px 0;">
                <h3>Details:</h3>
                <pre style="background-color: #f8f9fa; padding: 15px; border-radius: 5px;">
{error_details.get('details', 'No additional details available')}
                </pre>
            </div>
            
            <p>Please check the system logs and retry the operation if necessary.</p>
        </body>
        </html>
        """
        
        return html
    
    def _create_error_email_text(self, error_details: Dict[str, Any]) -> str:
        """Create plain text email for error notifications."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        text = f"""
INVENTORY UPDATE ERROR
Time: {timestamp}

ERROR: {error_details.get('message', 'Unknown error occurred')}

DETAILS:
{error_details.get('details', 'No additional details available')}

Please check the system logs and retry the operation if necessary.
"""
        
        return text


def send_update_notification(update_results: Dict[str, Any]) -> bool:
    """
    Main function to send update notification email.
    
    Args:
        update_results: Dictionary containing update results
        
    Returns:
        True if email was sent successfully, False otherwise
    """
    notifier = EmailNotifier()
    
    try:
        # Send confirmation email
        success = notifier.send_update_confirmation(update_results)
        
        return success
        
    except Exception as e:
        logging.error(f"Error sending update notification: {e}")
        return False


def send_error_notification(error_message: str, error_details: str = "") -> bool:
    """
    Main function to send error notification email.
    
    Args:
        error_message: Main error message
        error_details: Additional error details
        
    Returns:
        True if email was sent successfully, False otherwise
    """
    notifier = EmailNotifier()
    
    try:
        error_info = {
            'message': error_message,
            'details': error_details
        }
        
        # Send error notification
        success = notifier.send_error_notification(error_info)
        
        return success
        
    except Exception as e:
        logging.error(f"Error sending error notification: {e}")
        return False 