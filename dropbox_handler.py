"""
Dropbox handler module for monitoring file changes.

This module handles:
- Connecting to Dropbox API
- Monitoring specific folder for the most recent file containing "stock" in its name
- Downloading the most recent stock file if it's new/updated
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
    """Handles Dropbox file monitoring and downloading of the most recent stock file."""
    
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
        Check Dropbox folder for the most recent file containing "stock" in its name.
        
        Returns:
            List containing single most recent stock file path (if found and new/updated)
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
                # Handle path not found error
                if hasattr(e.error, 'get_path') and e.error.get_path() and hasattr(e.error.get_path(), 'is_not_found'):
                    if e.error.get_path().is_not_found():
                        self.logger.error(f"Dropbox folder not found: {self.folder_path}")
                        return downloaded_files
                # Handle other path lookup errors
                elif 'path_lookup' in str(e.error) and 'not_found' in str(e.error):
                    self.logger.error(f"Dropbox folder not found: {self.folder_path}")
                    return downloaded_files
                else:
                    self.logger.error(f"Dropbox API error: {e}")
                    return downloaded_files
            except Exception as e:
                self.logger.error(f"Error connecting to Dropbox: {e}")
                return downloaded_files
            
            # Collect all qualifying stock files
            stock_files = []
            
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
                    
                    # Check if filename contains "stock" (case-insensitive)
                    if "stock" not in file_name.lower():
                        self.logger.debug(f"Skipping file (no 'stock' in name): {file_name}")
                        continue
                    
                    # Update current state for all stock files (for tracking)
                    current_state[file_path] = modified_time
                    
                    # Add to stock files collection
                    stock_files.append({
                        'entry': entry,
                        'file_path': file_path,
                        'file_name': file_name,
                        'modified_time': modified_time,
                        'server_modified': entry.server_modified
                    })
            
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
                        
                        # Check if filename contains "stock" (case-insensitive)
                        if "stock" not in file_name.lower():
                            continue
                        
                        # Update current state
                        current_state[file_path] = modified_time
                        
                        # Add to stock files collection
                        stock_files.append({
                            'entry': entry,
                            'file_path': file_path,
                            'file_name': file_name,
                            'modified_time': modified_time,
                            'server_modified': entry.server_modified
                        })
            
            # Find the most recent stock file
            if stock_files:
                # Sort by modification time (most recent first)
                stock_files.sort(key=lambda x: x['server_modified'], reverse=True)
                most_recent_file = stock_files[0]
                
                self.logger.info(f"Found {len(stock_files)} stock files, most recent: {most_recent_file['file_name']}")
                
                # Check if the most recent file is new or updated
                file_path = most_recent_file['file_path']
                modified_time = most_recent_file['modified_time']
                
                if (file_path not in previous_state or 
                    previous_state[file_path] != modified_time):
                    
                    self.logger.info(f"Processing most recent stock file: {most_recent_file['file_name']}")
                    
                    # Download the most recent file
                    local_path = self._download_file(most_recent_file['entry'])
                    if local_path:
                        downloaded_files.append(local_path)
                else:
                    self.logger.info(f"Most recent stock file unchanged: {most_recent_file['file_name']}")
            else:
                self.logger.info("No stock files found in Dropbox folder")
            
            # Save current state (including all stock files for future reference)
            self._save_state(current_state)
            
            self.logger.info(f"Downloaded {len(downloaded_files)} stock file(s)")
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
    Main function to check for the most recent stock file in Dropbox.
    
    Returns:
        List containing path to the most recent stock file (if found and new/updated)
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