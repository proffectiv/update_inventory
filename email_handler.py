"""
Email handler module for monitoring and processing emails.

This module handles:
- Connecting to IMAP server (Strato)
- Checking for emails with specific keywords and attachments
- Downloading and validating attachments
- Extracting files for processing
"""

import imaplib
import email
from email.message import EmailMessage
import os
import tempfile
from typing import List, Optional, Tuple
import logging

from config import config


class EmailHandler:
    """Handles email monitoring and attachment processing."""
    
    def __init__(self):
        """Initialize email handler with configuration."""
        self.imap_host = config.imap_host
        self.imap_port = config.imap_port
        self.username = config.imap_username
        self.password = config.imap_password
        self.monitored_email = config.monitored_email
        self.keywords = config.email_keywords
        self.allowed_extensions = config.allowed_extensions
        self.max_file_size = config.max_file_size_mb * 1024 * 1024  # Convert to bytes
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def connect_to_imap(self) -> imaplib.IMAP4_SSL:
        """Connect to IMAP server and authenticate."""
        try:
            # Connect to IMAP server
            mail = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            mail.login(self.username, self.password)
            
            self.logger.info(f"Successfully connected to IMAP server: {self.imap_host}")
            return mail
            
        except Exception as e:
            self.logger.error(f"Failed to connect to IMAP server: {e}")
            raise
    
    def check_for_new_emails(self) -> List[Tuple[str, str]]:
        """
        Check for new emails with keywords and attachments.
        
        Returns:
            List of tuples containing (email_id, attachment_filename)
        """
        mail = None
        found_files = []
        
        try:
            mail = self.connect_to_imap()
            mail.select('INBOX')
            
            # Search for unread emails to the monitored address
            search_criteria = f'(UNSEEN TO "{self.monitored_email}")'
            status, message_ids = mail.search(None, search_criteria)
            
            if status != 'OK' or not message_ids[0]:
                self.logger.info("No new emails found")
                return found_files
            
            # Process each email
            for email_id in message_ids[0].split():
                email_id_str = email_id.decode()
                
                # Fetch the email
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                if status != 'OK':
                    continue
                
                # Parse the email
                raw_email = msg_data[0][1]
                email_message = email.message_from_bytes(raw_email)
                
                # Check if email has relevant keywords and attachments
                if self._has_relevant_content(email_message):
                    attachment_files = self._process_attachments(email_message)
                    for filename in attachment_files:
                        found_files.append((email_id_str, filename))
                        
                        # Mark email as read after processing
                        mail.store(email_id, '+FLAGS', '\\Seen')
            
            self.logger.info(f"Found {len(found_files)} relevant files in emails")
            return found_files
            
        except Exception as e:
            self.logger.error(f"Error checking emails: {e}")
            return found_files
            
        finally:
            if mail:
                try:
                    mail.close()
                    mail.logout()
                except:
                    pass
    
    def _has_relevant_content(self, email_message: EmailMessage) -> bool:
        """
        Check if email has relevant keywords in subject or body.
        
        Args:
            email_message: The email message to check
            
        Returns:
            True if email contains relevant keywords
        """
        # Get subject and body text
        subject = email_message.get('Subject', '').lower()
        
        # Get email body
        body = ""
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    body += part.get_payload(decode=True).decode('utf-8', errors='ignore').lower()
        else:
            body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore').lower()
        
        # Check if any keyword is present
        content = f"{subject} {body}"
        has_keywords = any(keyword in content for keyword in self.keywords)
        
        if has_keywords:
            self.logger.info(f"Email contains relevant keywords: {subject}")
        
        return has_keywords
    
    def _process_attachments(self, email_message: EmailMessage) -> List[str]:
        """
        Process and save valid attachments from email.
        
        Args:
            email_message: The email message to process
            
        Returns:
            List of saved attachment filenames
        """
        saved_files = []
        
        # Process attachments
        for part in email_message.walk():
            if part.get_content_disposition() == 'attachment':
                filename = part.get_filename()
                
                if not filename:
                    continue
                
                # Check if file has valid extension
                file_extension = filename.lower().split('.')[-1]
                if file_extension not in self.allowed_extensions:
                    self.logger.info(f"Skipping file with invalid extension: {filename}")
                    continue
                
                # Get file content
                file_content = part.get_payload(decode=True)
                
                # Check file size
                if len(file_content) > self.max_file_size:
                    self.logger.warning(f"File too large, skipping: {filename}")
                    continue
                
                # Save file to temporary directory
                try:
                    temp_dir = tempfile.gettempdir()
                    file_path = os.path.join(temp_dir, f"email_{filename}")
                    
                    with open(file_path, 'wb') as f:
                        f.write(file_content)
                    
                    saved_files.append(file_path)
                    self.logger.info(f"Saved attachment: {file_path}")
                    
                except Exception as e:
                    self.logger.error(f"Error saving attachment {filename}: {e}")
        
        return saved_files
    
    def cleanup_temp_files(self, file_paths: List[str]):
        """
        Clean up temporary files.
        
        Args:
            file_paths: List of file paths to delete
        """
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    self.logger.info(f"Cleaned up temporary file: {file_path}")
            except Exception as e:
                self.logger.warning(f"Could not delete temporary file {file_path}: {e}")


def check_email_trigger() -> List[str]:
    """
    Main function to check for email triggers.
    
    Returns:
        List of file paths to process
    """
    handler = EmailHandler()
    
    try:
        # Check for new emails
        email_files = handler.check_for_new_emails()
        
        # Extract just the file paths
        file_paths = [filename for _, filename in email_files]
        
        return file_paths
        
    except Exception as e:
        logging.error(f"Error in email trigger check: {e}")
        return [] 