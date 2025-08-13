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
import requests

from config import config


class DropboxHandler:
    """Handles Dropbox file monitoring and downloading of the most recent stock file."""
    
    def __init__(self):
        """Initialize Dropbox handler with configuration."""
        self.app_key = config.dropbox_app_key
        self.app_secret = config.dropbox_app_secret
        self.refresh_token = config.dropbox_refresh_token
        self.folder_path = config.dropbox_folder_path
        self.allowed_extensions = config.allowed_extensions
        self.max_file_size = config.max_file_size_mb * 1024 * 1024  # Convert to bytes
        
        # File to store last check timestamps
        self.state_file = 'dropbox_state.json'
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Initialize Dropbox client with refresh token handling
        self.dbx = self._get_dropbox_client()
    
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
    
    def _get_access_token(self) -> Optional[str]:
        """
        Get a valid access token by refreshing the refresh token.
        Always refreshes - no token caching to avoid storing sensitive data.
        
        Returns:
            Valid access token or None if refresh fails
        """
        try:
            # Always refresh token (no persistent storage of sensitive tokens)
            return self._refresh_access_token()
            
        except Exception as e:
            self.logger.error(f"Error getting access token: {e}")
            return None
    
    def _refresh_access_token(self) -> Optional[str]:
        """
        Refresh the access token using the refresh token.
        
        Returns:
            New access token or None if refresh fails
        """
        try:
            url = 'https://api.dropboxapi.com/oauth2/token'
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token,
                'client_id': self.app_key,
                'client_secret': self.app_secret
            }
            
            self.logger.debug(f"Refreshing token with app_key: {self.app_key[:8]}...")
            response = requests.post(url, data=data)
            
            if response.status_code != 200:
                self.logger.error(f"Token refresh failed with status {response.status_code}: {response.text}")
                
            response.raise_for_status()
            
            token_data = response.json()
            access_token = token_data['access_token']
            expires_in = token_data.get('expires_in', 14400)  # Default 4 hours
            expires_at = datetime.now().timestamp() + expires_in
            
            # No token storage - always refresh for security
            
            self.logger.info("Successfully refreshed Dropbox access token")
            return access_token
            
        except Exception as e:
            self.logger.error(f"Error refreshing access token: {e}")
            return None
    
    def _get_dropbox_client(self) -> Optional[dropbox.Dropbox]:
        """
        Get a Dropbox client with a valid access token.
        
        Returns:
            Dropbox client or None if authentication fails
        """
        access_token = self._get_access_token()
        if access_token:
            return dropbox.Dropbox(access_token)
        else:
            self.logger.error("Failed to get valid access token")
            return None
    
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
    
    def _ensure_valid_client(self) -> bool:
        """
        Ensure we have a valid Dropbox client, refreshing token if needed.
        
        Returns:
            True if client is valid, False otherwise
        """
        if not self.dbx:
            self.dbx = self._get_dropbox_client()
        
        if not self.dbx:
            return False
            
        try:
            # Test the connection
            self.dbx.users_get_current_account()
            return True
        except dropbox.exceptions.AuthError:
            # Token might be expired, try to refresh
            self.logger.info("Access token expired, refreshing...")
            self.dbx = self._get_dropbox_client()
            if self.dbx:
                try:
                    self.dbx.users_get_current_account()
                    return True
                except Exception as e:
                    self.logger.error(f"Failed to authenticate with new token: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error checking client: {e}")
            return False
    
    def check_for_updated_files(self) -> List[str]:
        """
        Check Dropbox folder for the most recent file containing "stock" in its name.
        
        Returns:
            List containing single most recent stock file path (if found and new/updated)
        """
        downloaded_files = []
        
        try:
            # Ensure we have a valid client
            if not self._ensure_valid_client():
                self.logger.error("Failed to authenticate with Dropbox")
                return downloaded_files
            
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
            local_filename = f"{file_metadata.name}"
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
    
    def upload_file(self, local_file_path: str, dropbox_file_path: str, overwrite: bool = True) -> bool:
        """
        Upload a file to Dropbox.
        
        Args:
            local_file_path: Path to the local file to upload
            dropbox_file_path: Target path in Dropbox (e.g., '/stock-update/conway_product_images.zip')
            overwrite: Whether to overwrite existing file (default: True)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.exists(local_file_path):
                self.logger.error(f"Local file not found: {local_file_path}")
                return False
            
            file_size = os.path.getsize(local_file_path)
            self.logger.info(f"Uploading file to Dropbox: {local_file_path} ({file_size / (1024*1024):.1f} MB)")
            
            # Choose upload mode based on overwrite setting
            mode = dropbox.files.WriteMode('overwrite') if overwrite else dropbox.files.WriteMode('add')
            
            # For large files (>150MB), use upload sessions
            CHUNK_SIZE = 4 * 1024 * 1024  # 4MB chunks
            
            with open(local_file_path, 'rb') as file:
                if file_size <= CHUNK_SIZE:
                    # Small file - upload in one request
                    file_data = file.read()
                    result = self.dbx.files_upload(
                        file_data,
                        dropbox_file_path,
                        mode=mode,
                        autorename=False
                    )
                else:
                    # Large file - use upload session
                    upload_session_start_result = self.dbx.files_upload_session_start(
                        file.read(CHUNK_SIZE)
                    )
                    cursor = dropbox.files.UploadSessionCursor(
                        session_id=upload_session_start_result.session_id,
                        offset=file.tell()
                    )
                    
                    # Upload remaining chunks
                    while file.tell() < file_size:
                        if (file_size - file.tell()) <= CHUNK_SIZE:
                            # Last chunk
                            commit = dropbox.files.CommitInfo(
                                path=dropbox_file_path,
                                mode=mode,
                                autorename=False
                            )
                            result = self.dbx.files_upload_session_finish(
                                file.read(CHUNK_SIZE),
                                cursor,
                                commit
                            )
                        else:
                            # Middle chunk
                            self.dbx.files_upload_session_append_v2(
                                file.read(CHUNK_SIZE),
                                cursor
                            )
                            cursor.offset = file.tell()
            
            self.logger.info(f"Successfully uploaded file to Dropbox: {dropbox_file_path}")
            self.logger.info(f"File ID: {result.id}")
            return True
            
        except dropbox.exceptions.ApiError as e:
            self.logger.error(f"Dropbox API error during upload: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error uploading file to Dropbox: {e}")
            return False
    
    def generate_shareable_link(self, dropbox_file_path: str) -> Optional[str]:
        """
        Generate a shareable download link for a Dropbox file.
        
        Args:
            dropbox_file_path: Path to the file in Dropbox
            
        Returns:
            Shareable download URL or None if failed
        """
        try:
            # Check if file exists first
            try:
                self.dbx.files_get_metadata(dropbox_file_path)
            except dropbox.exceptions.ApiError as e:
                self.logger.error(f"File not found in Dropbox: {dropbox_file_path} - {e}")
                return None
            
            # Try to get existing shared link first
            try:
                shared_links = self.dbx.sharing_list_shared_links(path=dropbox_file_path, direct_only=True)
                if shared_links.links:
                    link = shared_links.links[0].url
                    self.logger.info(f"Using existing shareable link: {dropbox_file_path}")
                    return link
            except dropbox.exceptions.ApiError as e:
                if "missing_scope" in str(e) or "TokenScopeError" in str(e):
                    self.logger.error(f"Dropbox app missing 'sharing.read' scope. Please regenerate refresh token with proper permissions.")
                    return None
                # No existing link, create new one
                pass
            
            # Create new shareable link
            shared_link_metadata = self.dbx.sharing_create_shared_link_with_settings(
                dropbox_file_path,
                settings=dropbox.sharing.SharedLinkSettings(
                    requested_visibility=dropbox.sharing.RequestedVisibility.public,
                    audience=dropbox.sharing.LinkAudience.public,
                    access=dropbox.sharing.RequestedLinkAccessLevel.viewer
                )
            )
            
            link = shared_link_metadata.url
            self.logger.info(f"Created new shareable link for: {dropbox_file_path}")
            return link
            
        except dropbox.exceptions.ApiError as e:
            if "missing_scope" in str(e) or "TokenScopeError" in str(e):
                self.logger.error(f"Dropbox app missing sharing permissions. Please regenerate refresh token with 'sharing.read' and 'sharing.write' scopes.")
            else:
                self.logger.error(f"Dropbox API error creating shareable link: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error creating shareable link: {e}")
            return None
    
    def test_connection(self) -> bool:
        """
        Test the Dropbox connection.
        
        Returns:
            True if connection is successful
        """
        if not self._ensure_valid_client():
            return False
            
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