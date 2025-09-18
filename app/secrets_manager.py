"""
Secure secrets management for Seedkeeper bot
Handles encrypted storage and retrieval of sensitive configuration
"""

import os
import json
import base64
from pathlib import Path
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

logger = logging.getLogger(__name__)


class SecretsManager:
    """Manages encrypted secrets with file-based storage"""
    
    def __init__(self, secrets_dir: str = "/run/secrets"):
        self.secrets_dir = Path(secrets_dir)
        self.cache: Dict[str, str] = {}
        self._cipher: Optional[Fernet] = None
        
    def _get_or_create_key(self) -> bytes:
        """Get or create encryption key from environment or file"""
        key_file = Path("/app/data/.encryption_key")
        
        if key_file.exists():
            with open(key_file, 'rb') as f:
                return f.read()
        
        # Generate new key
        key = Fernet.generate_key()
        
        # Ensure data directory exists
        key_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Save key with restricted permissions
        with open(key_file, 'wb') as f:
            f.write(key)
        
        # Set restrictive permissions (owner read only)
        os.chmod(key_file, 0o400)
        
        return key
    
    def _get_cipher(self) -> Fernet:
        """Get or create Fernet cipher instance"""
        if not self._cipher:
            key = self._get_or_create_key()
            self._cipher = Fernet(key)
        return self._cipher
    
    def get_secret(self, secret_name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get secret value from various sources in order of priority:
        1. Docker secrets (if running in Docker with secrets)
        2. Environment variables (for backward compatibility)
        3. Encrypted file storage
        4. Default value
        """
        
        # Check cache first
        if secret_name in self.cache:
            return self.cache[secret_name]
        
        # Try Docker secrets
        secret_file = self.secrets_dir / secret_name.lower()
        if secret_file.exists():
            try:
                with open(secret_file, 'r') as f:
                    value = f.read().strip()
                    self.cache[secret_name] = value
                    return value
            except Exception as e:
                logger.error(f"Failed to read Docker secret {secret_name}: {e}")
        
        # Try environment variable
        env_value = os.environ.get(secret_name)
        if env_value:
            self.cache[secret_name] = env_value
            return env_value
        
        # Try encrypted file storage
        encrypted_file = Path(f"/app/data/.secrets/{secret_name}.enc")
        if encrypted_file.exists():
            try:
                with open(encrypted_file, 'rb') as f:
                    encrypted_data = f.read()
                    cipher = self._get_cipher()
                    decrypted = cipher.decrypt(encrypted_data).decode('utf-8')
                    self.cache[secret_name] = decrypted
                    return decrypted
            except Exception as e:
                logger.error(f"Failed to decrypt secret {secret_name}: {e}")
        
        return default
    
    def set_secret(self, secret_name: str, value: str) -> bool:
        """Store secret in encrypted file"""
        try:
            # Ensure secrets directory exists
            secrets_dir = Path("/app/data/.secrets")
            secrets_dir.mkdir(parents=True, exist_ok=True)
            
            # Encrypt and store
            cipher = self._get_cipher()
            encrypted = cipher.encrypt(value.encode('utf-8'))
            
            secret_file = secrets_dir / f"{secret_name}.enc"
            with open(secret_file, 'wb') as f:
                f.write(encrypted)
            
            # Set restrictive permissions
            os.chmod(secret_file, 0o600)
            
            # Update cache
            self.cache[secret_name] = value
            
            return True
        except Exception as e:
            logger.error(f"Failed to store secret {secret_name}: {e}")
            return False
    
    def validate_required_secrets(self, required: list) -> tuple[bool, list]:
        """Validate that all required secrets are available"""
        missing = []
        for secret_name in required:
            if not self.get_secret(secret_name):
                missing.append(secret_name)
        
        return len(missing) == 0, missing
    
    def clear_cache(self):
        """Clear cached secrets (useful for rotation)"""
        self.cache.clear()


# Singleton instance
secrets_manager = SecretsManager()


def get_discord_token() -> str:
    """Get Discord bot token from secure storage"""
    token = secrets_manager.get_secret('DISCORD_BOT_TOKEN')
    if not token:
        raise ValueError("Discord bot token not found in secrets")
    return token


def get_anthropic_api_key() -> str:
    """Get Anthropic API key from secure storage"""
    key = secrets_manager.get_secret('ANTHROPIC_API_KEY')
    if not key:
        raise ValueError("Anthropic API key not found in secrets")
    return key


def get_redis_password() -> Optional[str]:
    """Get Redis password if configured"""
    return secrets_manager.get_secret('REDIS_PASSWORD')


def validate_secrets() -> bool:
    """Validate all required secrets are present"""
    required = ['DISCORD_BOT_TOKEN', 'ANTHROPIC_API_KEY']
    valid, missing = secrets_manager.validate_required_secrets(required)
    
    if not valid:
        logger.error(f"Missing required secrets: {', '.join(missing)}")
        logger.info("Please ensure secrets are configured via:")
        logger.info("  1. Docker secrets (recommended for production)")
        logger.info("  2. Environment variables")
        logger.info("  3. Run 'python setup_secrets.py' to configure interactively")
    
    return valid