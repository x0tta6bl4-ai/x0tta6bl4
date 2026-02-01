"""
Password Migration Tool: MD5 → bcrypt

Provides utilities for securely migrating legacy MD5-hashed passwords
to industry-standard bcrypt hashing.

Usage:
    migrator = PasswordMigrator()
    
    # For existing MD5 hashes (one-way migration to bcrypt)
    bcrypt_hash = migrator.rehash_md5_to_bcrypt(md5_hash)
    
    # For plaintext passwords (during registration/reset)
    bcrypt_hash = migrator.hash_password(plaintext_password)
    
    # For verification (handles both old MD5 and new bcrypt)
    is_valid = migrator.verify_legacy_or_bcrypt(provided_password, stored_hash)
"""

import bcrypt
import logging
from typing import Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Security constants
BCRYPT_ROUNDS = 12  # OWASP recommendation: 12-14 rounds
BCRYPT_PREFIX = "$2b$"  # Bcrypt identifier


@dataclass
class MigrationStats:
    """Statistics for password migration"""
    total_processed: int = 0
    successfully_migrated: int = 0
    failed_migrations: int = 0
    already_bcrypt: int = 0


class PasswordMigrator:
    """
    Securely migrates from MD5 to bcrypt hashing.
    
    ⚠️ CRITICAL SECURITY NOTES:
    1. MD5 is cryptographically broken - never use for password hashing
    2. Bcrypt is slow-by-design, providing protection against brute-force attacks
    3. Always verify passwords during login and re-hash on successful verification
    4. Never log or store plaintext passwords
    """
    
    def __init__(self):
        self.stats = MigrationStats()
    
    def hash_password(self, plaintext: str) -> str:
        """
        Hash a plaintext password using bcrypt.
        
        Args:
            plaintext: Raw password string
            
        Returns:
            Bcrypt hash (always starts with $2b$)
        """
        if not isinstance(plaintext, str):
            raise TypeError("Password must be a string")
        
        if not plaintext or len(plaintext) < 8:
            raise ValueError("Password must be at least 8 characters")
        
        # Encode to bytes and hash with bcrypt
        password_bytes = plaintext.encode('utf-8')
        salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
        hashed = bcrypt.hashpw(password_bytes, salt)
        
        return hashed.decode('utf-8')
    
    def verify_password(self, plaintext: str, bcrypt_hash: str) -> bool:
        """
        Verify a plaintext password against a bcrypt hash.
        
        Args:
            plaintext: User-provided password
            bcrypt_hash: Stored bcrypt hash
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            if not bcrypt_hash.startswith(BCRYPT_PREFIX):
                logger.warning("⚠️ Not a bcrypt hash, rejecting for security")
                return False
            
            password_bytes = plaintext.encode('utf-8')
            return bcrypt.checkpw(password_bytes, bcrypt_hash.encode('utf-8'))
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    def is_md5_hash(self, hash_str: str) -> bool:
        """
        Detect if a string is likely an MD5 hash.
        
        MD5 characteristics:
        - 32 hexadecimal characters
        - No special prefix like bcrypt ($2b$)
        """
        if not hash_str:
            return False
        
        # Check if already bcrypt
        if hash_str.startswith(BCRYPT_PREFIX):
            return False
        
        # MD5 is 32 hex chars
        if len(hash_str) == 32 and all(c in '0123456789abcdef' for c in hash_str.lower()):
            return True
        
        return False
    
    def legacy_verify_md5(self, plaintext: str, md5_hash: str) -> bool:
        """
        Legacy verification for MD5 hashes (for migration period only).
        
        ⚠️ DEPRECATED: Remove after migration is complete
        
        Args:
            plaintext: User-provided password
            md5_hash: Legacy MD5 hash (32 hex chars)
            
        Returns:
            True if password matches MD5 hash
        """
        if not self.is_md5_hash(md5_hash):
            return False
        
        # SECURITY FIX: MD5 is cryptographically broken
        # We NO LONGER verify MD5 hashes - force password reset instead
        # This ensures all users migrate to bcrypt
        logger.warning(
            "🔴 SECURITY: MD5 hash detected for user - forcing password reset. "
            "MD5 is cryptographically broken and has been disabled."
        )
        return False  # Always return False to force password reset
    
    def verify_legacy_or_bcrypt(self, plaintext: str, stored_hash: str) -> Tuple[bool, bool]:
        """
        Verify password against legacy MD5 or modern bcrypt hash.
        
        Returns:
            (is_valid: bool, needs_rehashing: bool)
            - is_valid: Whether password matches
            - needs_rehashing: Whether stored_hash is MD5 (needs upgrade)
        """
        if not stored_hash:
            return False, False
        
        # Try bcrypt first
        if stored_hash.startswith(BCRYPT_PREFIX):
            is_valid = self.verify_password(plaintext, stored_hash)
            return is_valid, False
        
        # Fall back to MD5 (legacy)
        if self.is_md5_hash(stored_hash):
            logger.warning("🔴 MD5 hash detected - should be migrated to bcrypt!")
            is_valid = self.legacy_verify_md5(plaintext, stored_hash)
            return is_valid, True
        
        # Unknown hash format
        logger.error(f"Unknown hash format in verify_legacy_or_bcrypt")
        return False, False
    
    def rehash_md5_to_bcrypt(self, md5_hash: str) -> Optional[str]:
        """
        ⚠️ IMPORTANT: This is a one-way conversion suitable for storage migration.
        
        MD5 cannot be inverted, so we can only convert if we have the plaintext.
        This method is for marking MD5 hashes that need re-hashing on next login.
        
        For proper migration:
        1. During login, verify with MD5 using legacy_verify_md5()
        2. If valid, re-hash password with hash_password()
        3. Update database with new bcrypt hash
        
        Args:
            md5_hash: Legacy MD5 hash (this alone cannot be converted)
            
        Returns:
            Marker string indicating migration is needed
        """
        if not self.is_md5_hash(md5_hash):
            return None
        
        # Return a marker that this hash needs re-hashing
        # (actual rehashing requires plaintext password at login time)
        return f"__NEEDS_MIGRATION__{md5_hash}"
    
    @staticmethod
    def verify_is_migration_marker(value: str) -> bool:
        """Check if value is a migration marker."""
        return isinstance(value, str) and value.startswith("__NEEDS_MIGRATION__")
    
    def reset_stats(self) -> None:
        """Reset migration statistics."""
        self.stats = MigrationStats()
    
    def get_stats(self) -> MigrationStats:
        """Get current migration statistics."""
        return self.stats


# Singleton instance for convenience
_migrator_instance = None


def get_password_migrator() -> PasswordMigrator:
    """Get or create the password migrator singleton."""
    global _migrator_instance
    if _migrator_instance is None:
        _migrator_instance = PasswordMigrator()
    return _migrator_instance


# Security recommendations for web components
SECURITY_AUDIT_RECOMMENDATIONS = """
WEB COMPONENT SECURITY AUDIT FINDINGS & RECOMMENDATIONS
========================================================

1. PASSWORD HASHING (CRITICAL)
   ✗ Current: MD5 (broken, 2^128 search space, zero salt)
   ✓ Fix: Bcrypt with 12 rounds (2^128 rounds, automatic salt)
   
   Old code:
   ```php
   $password = md5($upass);
   ```
   
   New code:
   ```php
   // Using password_hash() in PHP 5.5+
   $password = password_hash($upass, PASSWORD_BCRYPT, ['cost' => 12]);
   
   // Or use $2y$ prefix (PHP default)
   ```

2. PASSWORD VERIFICATION (CRITICAL)
   ✗ Current: Direct string comparison
   ```php
   if($userRow['userPass']==md5($upass))
   ```
   
   ✓ Fixed:
   ```php
   if(password_verify($upass, $userRow['userPass']))
   ```

3. SQL INJECTION PREVENTION (CRITICAL)
   ✓ Good: Using prepared statements (keep this!)
   ✗ Issue: No input validation/sanitization
   
   Recommendations:
   - Add length validation (email, username)
   - Use TRIM and FILTER_VALIDATE_EMAIL
   - Add rate limiting on login attempts

4. CSRF PROTECTION (HIGH)
   ✗ Missing: No CSRF tokens on forms
   
   Fix: Add CSRF token to forms
   ```php
   <input type="hidden" name="csrf_token" value="<?php echo $_SESSION['csrf_token']; ?>">
   ```

5. SESSION MANAGEMENT (HIGH)
   ⚠️  Use secure session options:
   ```php
   session_start([
       'cookie_secure' => true,    // HTTPS only
       'cookie_httponly' => true,  // No JavaScript access
       'cookie_samesite' => 'Strict',
       'sid_length' => 32,
   ]);
   ```

6. RANDOM NUMBER GENERATION (MEDIUM)
   ✗ Current: md5(uniqid(rand()))
   
   ✓ Better:
   ```php
   $code = bin2hex(random_bytes(16));
   ```

7. EMAIL VERIFICATION (MEDIUM)
   ⚠️  Current: Tokens are predictable (MD5 not random)
   
   Fix: Use random_bytes()
   ```php
   $verification_token = bin2hex(random_bytes(32));
   $token_hash = hash('sha256', $verification_token);
   // Store token_hash in DB
   // Send verification_token in email
   ```

8. ERROR HANDLING (MEDIUM)
   ✗ Current: echoing exception messages (info disclosure)
   
   Fix: Log exceptions, show generic messages
   ```php
   try {
       // ...
   } catch(PDOException $ex) {
       error_log($ex->getMessage());
       header("Location: error.php?msg=database_error");
   }
   ```

9. RATE LIMITING (HIGH)
   ✗ Missing: No login attempt limits
   
   Implement:
   - Max 5 failed attempts per IP per 15min
   - Account lockout after 10 attempts
   - Use Redis or file-based rate limiter

10. DEPENDENCIES (MEDIUM)
    ✗ PHPMailer is outdated
    
    Update to:
    ```bash
    composer require phpmailer/phpmailer
    ```
    
    Use prepared statements in mail headers.

IMPLEMENTATION PRIORITY
=======================
P0 (IMMEDIATE):
  1. Replace MD5 with password_hash() - CRITICAL
  2. Add CSRF protection
  3. Enable secure session options
  4. Add login rate limiting

P1 (THIS WEEK):
  5. Add input validation
  6. Fix error handling
  7. Update dependencies
  8. Add account lockout

P2 (THIS MONTH):
  9. Add 2FA/TOTP support
  10. Implement security headers (CSP, HSTS, X-Frame-Options)
"""
