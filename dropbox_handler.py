"""
Dropbox handler module for monitoring file changes.

This module handles:
- Connecting to Dropbox API
- Monitoring specific folder for new/updated files
- Downloading files with allowed extensions
- Tracking file modification times to detect changes
"""

import dropbox
import os
import tempfile
from typing import List, Dict, Optional
import logging
from datetime import datetime, timezone
import json

from config import config


class DropboxHandler:
    """Handles Dropbox file monitoring and downloading."""
    
    def __init__(self):
        """Initialize Dropbox handler with configuration."""
        self.access_token = config.dropbox_access_token
        self.folder_path = config.dropbox_folder_path
        self.allowed_extensions = config.allowed_extensions
        self.max_file_size = config.max_file_size_mb * 1024 * 1024  # Convert to bytes
        
        # File to store last check timestamps
        self.state_file = 'dropbox_state.json'
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Initialize Dropbox client
        self.dbx = dropbox.Dropbox(self.access_token)
    
    def _load_state(self) -> Dict[str, str]:
        """
        Load the last check state from file.
        
        Returns:
            Dictionary mapping file paths to last modified timestamps
        """
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.warning(f"Could not load state file: {e}")
        
        return {}
    
    def _save_state(self, state: Dict[str, str]):
        """
        Save the current state to file.
        
        Args:
            state: Dictionary mapping file paths to last modified timestamps
        """
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            self.logger.error(f"Could not save state file: {e}")
    
    def check_for_updated_files(self) -> List[str]:
        """
        Check Dropbox folder for new or updated files.
        
        Returns:
            List of downloaded file paths
        """
        downloaded_files = []
        
        try:
            # Load previous state
            previous_state = self._load_state()
            current_state = {}
            
            # List files in the monitored folder
            self.logger.info(f"Checking Dropbox folder: {self.folder_path}")
            
            try:
                result = self.dbx.files_list_folder(self.folder_path, recursive=True)
            except dropbox.exceptions.ApiError as e:
                if e.error.is_path_not_found():
                    self.logger.error(f"Dropbox folder not found: {self.folder_path}")
                    return downloaded_files
                else:
                    raise
            
            # Process each file
            for entry in result.entries:
                if isinstance(entry, dropbox.files.FileMetadata):
                    file_path = entry.path_lower
                    file_name = entry.name
                    file_size = entry.size
                    modified_time = entry.server_modified.isoformat()
                    
                    # Check if file has allowed extension
                    file_extension = file_name.lower().split('.')[-1]
                    if file_extension not in self.allowed_extensions:
                        continue
                    
                    # Check file size
                    if file_size > self.max_file_size:
                        self.logger.warning(f"File too large, skipping: {file_name}")
                        continue
                    
                    # Update current state
                    current_state[file_path] = modified_time
                    
                    # Check if file is new or updated
                    if (file_path not in previous_state or 
                        previous_state[file_path] != modified_time):
                        
                        self.logger.info(f"Detected new/updated file: {file_name}")
                        
                        # Download the file
                        local_path = self._download_file(entry)
                        if local_path:
                            downloaded_files.append(local_path)
            
            # Handle pagination if there are more files
            while result.has_more:
                result = self.dbx.files_list_folder_continue(result.cursor)
                
                for entry in result.entries:
                    if isinstance(entry, dropbox.files.FileMetadata):
                        file_path = entry.path_lower
                        file_name = entry.name
                        file_size = entry.size
                        modified_time = entry.server_modified.isoformat()
                        
                        # Check file extension and size
                        file_extension = file_name.lower().split('.')[-1]
                        if file_extension not in self.allowed_extensions:
                            continue
                        
                        if file_size > self.max_file_size:
                            continue
                        
                        # Update current state
                        current_state[file_path] = modified_time
                        
                        # Check if file is new or updated
                        if (file_path not in previous_state or 
                            previous_state[file_path] != modified_time):
                            
                            local_path = self._download_file(entry)
                            if local_path:
                                downloaded_files.append(local_path)
            
            # Save current state
            self._save_state(current_state)
            
            self.logger.info(f"Found {len(downloaded_files)} new/updated files")
            return downloaded_files
            
        except Exception as e:
            self.logger.error(f"Error checking Dropbox files: {e}")
            return downloaded_files
    
    def _download_file(self, file_metadata: dropbox.files.FileMetadata) -> Optional[str]:
        """
        Download a file from Dropbox to local temporary directory.
        
        Args:
            file_metadata: Dropbox file metadata
            
        Returns:
            Local file path if successful, None otherwise
        """
        try:
            # Create temporary file path
            temp_dir = tempfile.gettempdir()
            local_filename = f"dropbox_{file_metadata.name}"
            local_path = os.path.join(temp_dir, local_filename)
            
            # Download the file
            self.logger.info(f"Downloading file: {file_metadata.name}")
            
            with open(local_path, 'wb') as f:
                metadata, response = self.dbx.files_download(file_metadata.path_lower)
                f.write(response.content)
            
            self.logger.info(f"Downloaded file to: {local_path}")
            return local_path
            
        except Exception as e:
            self.logger.error(f"Error downloading file {file_metadata.name}: {e}")
            return None
    
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
    
    def test_connection(self) -> bool:
        """
        Test the Dropbox connection.
        
        Returns:
            True if connection is successful
        """
        try:
            account_info = self.dbx.users_get_current_account()
            self.logger.info(f"Connected to Dropbox account: {account_info.email}")
            return True
        except Exception as e:
            self.logger.error(f"Dropbox connection failed: {e}")
            return False


def check_dropbox_trigger() -> List[str]:
    """
    Main function to check for Dropbox triggers.
    
    Returns:
        List of file paths to process
    """
    handler = DropboxHandler()
    
    try:
        # Test connection first
        if not handler.test_connection():
            logging.error("Dropbox connection failed")
            return []
        
        # Check for updated files
        file_paths = handler.check_for_updated_files()
        
        return file_paths
        
    except Exception as e:
        logging.error(f"Error in Dropbox trigger check: {e}")
        return [] 