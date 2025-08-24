"""
OAuth 2.0 authentication handler for OData services.
Supports Client Credentials and Authorization Code flows.
"""

import sys
import time
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode
import requests


class OAuthTokenManager:
    """Manages OAuth 2.0 tokens with automatic refresh."""
    
    def __init__(self, client_id: str, client_secret: str, token_url: str,
                 scope: Optional[str] = None, verbose: bool = False):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.scope = scope
        self.verbose = verbose
        
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._expires_at: float = 0
        self._token_type: str = "Bearer"
    
    def get_authorization_header(self) -> Dict[str, str]:
        """Get the Authorization header with current valid token."""
        token = self._get_valid_token()
        return {"Authorization": f"{self._token_type} {token}"}
    
    def _get_valid_token(self) -> str:
        """Get a valid access token, refreshing if necessary."""
        if self._access_token and time.time() < self._expires_at - 30:
            # Token is valid (with 30-second buffer)
            return self._access_token
            
        # Need to get a new token
        self._fetch_token()
        return self._access_token
    
    def _fetch_token(self):
        """Fetch a new access token using client credentials flow."""
        if self.verbose:
            print(f"Fetching OAuth token from {self.token_url}", file=sys.stderr)
            
        payload = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        if self.scope:
            payload['scope'] = self.scope
            
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        
        try:
            response = requests.post(self.token_url, data=payload, headers=headers)
            response.raise_for_status()
            
            token_data = response.json()
            self._access_token = token_data['access_token']
            self._token_type = token_data.get('token_type', 'Bearer')
            expires_in = token_data.get('expires_in', 3600)  # Default 1 hour
            self._expires_at = time.time() + expires_in
            
            # Store refresh token if provided
            if 'refresh_token' in token_data:
                self._refresh_token = token_data['refresh_token']
                
            if self.verbose:
                print(f"OAuth token obtained, expires in {expires_in} seconds", file=sys.stderr)
                
        except requests.RequestException as e:
            raise Exception(f"OAuth token fetch failed: {e}")
    
    def refresh_access_token(self):
        """Refresh the access token using refresh token."""
        if not self._refresh_token:
            # Fall back to client credentials flow
            self._fetch_token()
            return
            
        payload = {
            'grant_type': 'refresh_token',
            'refresh_token': self._refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        
        try:
            response = requests.post(self.token_url, data=payload, headers=headers)
            response.raise_for_status()
            
            token_data = response.json()
            self._access_token = token_data['access_token']
            self._token_type = token_data.get('token_type', 'Bearer')
            expires_in = token_data.get('expires_in', 3600)
            self._expires_at = time.time() + expires_in
            
            # Update refresh token if new one provided
            if 'refresh_token' in token_data:
                self._refresh_token = token_data['refresh_token']
                
            if self.verbose:
                print(f"OAuth token refreshed, expires in {expires_in} seconds", file=sys.stderr)
                
        except requests.RequestException as e:
            if self.verbose:
                print(f"Token refresh failed, falling back to client credentials: {e}", file=sys.stderr)
            # Fall back to client credentials flow
            self._fetch_token()


class OAuthConfig:
    """OAuth configuration helper."""
    
    @staticmethod
    def from_environment() -> Optional[Dict[str, str]]:
        """Create OAuth config from environment variables."""
        import os
        
        client_id = os.getenv('OAUTH_CLIENT_ID') or os.getenv('ODATA_OAUTH_CLIENT_ID')
        client_secret = os.getenv('OAUTH_CLIENT_SECRET') or os.getenv('ODATA_OAUTH_CLIENT_SECRET')
        token_url = os.getenv('OAUTH_TOKEN_URL') or os.getenv('ODATA_OAUTH_TOKEN_URL')
        
        if not all([client_id, client_secret, token_url]):
            return None
            
        return {
            'client_id': client_id,
            'client_secret': client_secret,
            'token_url': token_url,
            'scope': os.getenv('OAUTH_SCOPE') or os.getenv('ODATA_OAUTH_SCOPE')
        }
    
    @staticmethod
    def microsoft_graph(tenant_id: str = "common") -> Dict[str, str]:
        """Get Microsoft Graph OAuth endpoints."""
        return {
            'token_url': f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token',
            'scope': 'https://graph.microsoft.com/.default'
        }
    
    @staticmethod 
    def sap_oauth(sap_host: str) -> Dict[str, str]:
        """Get SAP OAuth endpoints (OIDC)."""
        return {
            'token_url': f'https://{sap_host}/sap/bc/sec/oauth2/token',
            'scope': 'odata_read odata_write'
        }