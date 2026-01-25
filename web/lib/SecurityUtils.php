<?php
/**
 * SecurityUtils.php - Secure utility functions for password hashing, token generation, CSRF protection
 * 
 * REPLACES unsafe functions:
 * - md5($password) → hashPassword($password)
 * - md5(uniqid(rand())) → generateSecureToken()
 * - Missing CSRF protection → generateCSRFToken() + verifyCSRFToken()
 * 
 * PHP Version: 7.4+
 * Author: Security Audit Team
 * Date: 2026-01-12
 */

class SecurityUtils {

    /**
     * Hash a password using bcrypt with work factor 12
     * 
     * @param string $password Plain text password
     * @return string|false Bcrypt hash or false on error
     */
    public static function hashPassword($password) {
        if (empty($password) || !is_string($password)) {
            return false;
        }
        
        $hash = password_hash($password, PASSWORD_BCRYPT, [
            'cost' => 12  // ~100ms on modern hardware, recommended by OWASP
        ]);
        
        if ($hash === false) {
            error_log("ERROR: password_hash() failed");
            return false;
        }
        
        return $hash;
    }

    /**
     * Verify password against bcrypt hash
     * 
     * @param string $password Plain text password to verify
     * @param string $hash Stored bcrypt hash
     * @return bool True if password matches, false otherwise
     */
    public static function verifyPassword($password, $hash) {
        if (empty($password) || empty($hash) || !is_string($password) || !is_string($hash)) {
            return false;
        }
        
        // Always use password_verify to prevent timing attacks
        return password_verify($password, $hash);
    }

    /**
     * Generate cryptographically secure random token
     * Uses random_bytes() (CSPRNG)
     * 
     * @param int $length Desired length in bytes (default 32 = 256 bits)
     * @return string Hex-encoded random token
     */
    public static function generateSecureToken($length = 32) {
        if ($length < 16) {
            $length = 32; // Minimum recommended
        }
        
        try {
            $bytes = random_bytes($length);
            return bin2hex($bytes);
        } catch (Exception $e) {
            error_log("ERROR: Failed to generate secure token: " . $e->getMessage());
            return false;
        }
    }

    /**
     * Verify secure token against stored hash (optional, for token validation)
     * Note: For simple token matching, use direct comparison (token == stored_token)
     * This function is for hashed token comparison if needed
     * 
     * @param string $token Plain token
     * @param string $hash_token Hashed token
     * @return bool True if tokens match
     */
    public static function verifySecureToken($token, $hash_token) {
        if (empty($token) || empty($hash_token)) {
            return false;
        }
        
        // For tokens, we typically store them in plain, so just compare
        // Or use hash_equals for timing-safe comparison
        return hash_equals($token, $hash_token);
    }

    /**
     * Generate CSRF token and store in session
     * Must be called after session_start()
     * 
     * @param string $key Session key name (default: '__csrf_token')
     * @return string Generated CSRF token
     */
    public static function generateCSRFToken($key = '__csrf_token') {
        if (session_status() === PHP_SESSION_NONE) {
            error_log("WARNING: session_start() not called. Initializing session.");
            @session_start();
        }
        
        if (!isset($_SESSION[$key])) {
            $_SESSION[$key] = self::generateSecureToken(32);
        }
        
        return $_SESSION[$key];
    }

    /**
     * Verify CSRF token from request (POST/GET)
     * Checks against session token
     * 
     * @param string $token Token to verify
     * @param string $key Session key name (default: '__csrf_token')
     * @return bool True if valid, false otherwise
     */
    public static function verifyCSRFToken($token, $key = '__csrf_token') {
        if (session_status() === PHP_SESSION_NONE) {
            return false;
        }
        
        if (!isset($_SESSION[$key])) {
            return false;
        }
        
        // Use hash_equals for timing-safe comparison
        return hash_equals($token, $_SESSION[$key]);
    }

    /**
     * Regenerate session ID (call after login)
     * Prevents session fixation attacks
     * 
     * @return bool
     */
    public static function regenerateSessionID() {
        if (session_status() === PHP_SESSION_NONE) {
            @session_start();
        }
        
        return session_regenerate_id(true); // true = delete old session
    }

    /**
     * Generate Content Security Policy (CSP) nonce for inline scripts
     * Store in session, use in script tags: <script nonce="<?php echo $nonce; ?>">
     * 
     * @param string $key Session key (default: '__csp_nonce')
     * @return string Nonce value
     */
    public static function generateCSPNonce($key = '__csp_nonce') {
        if (session_status() === PHP_SESSION_NONE) {
            @session_start();
        }
        
        if (!isset($_SESSION[$key])) {
            $_SESSION[$key] = base64_encode(random_bytes(16));
        }
        
        return $_SESSION[$key];
    }

    /**
     * Escape HTML special characters for safe output
     * REPLACES: htmlspecialchars() with sensible defaults
     * 
     * @param string $string String to escape
     * @return string Escaped string
     */
    public static function escapeHTML($string) {
        return htmlspecialchars($string, ENT_QUOTES, 'UTF-8');
    }

    /**
     * Sanitize email address
     * 
     * @param string $email Email to sanitize
     * @return string|false Sanitized email or false if invalid
     */
    public static function sanitizeEmail($email) {
        return filter_var($email, FILTER_SANITIZE_EMAIL);
    }

    /**
     * Validate email address
     * 
     * @param string $email Email to validate
     * @return bool
     */
    public static function validateEmail($email) {
        return filter_var($email, FILTER_VALIDATE_EMAIL) !== false;
    }

    /**
     * Hash filename for content-id (safer than md5)
     * Used for email attachments
     * 
     * @param string $filename Filename to hash
     * @return string Hash for content-id
     */
    public static function hashFilename($filename) {
        // Use SHA256 instead of MD5, or better: just use a random ID
        return hash('sha256', $filename);
    }

    /**
     * Generate unique ID for email attachments (replaces md5(uniqid()))
     * 
     * @return string Unique identifier
     */
    public static function generateUniqueID() {
        return bin2hex(random_bytes(16));
    }

    /**
     * Validate password strength
     * 
     * @param string $password Password to validate
     * @return array ['valid' => bool, 'errors' => array]
     */
    public static function validatePasswordStrength($password) {
        $errors = [];
        
        if (strlen($password) < 8) {
            $errors[] = "Password must be at least 8 characters";
        }
        if (!preg_match('/[A-Z]/', $password)) {
            $errors[] = "Password must contain uppercase letters";
        }
        if (!preg_match('/[a-z]/', $password)) {
            $errors[] = "Password must contain lowercase letters";
        }
        if (!preg_match('/[0-9]/', $password)) {
            $errors[] = "Password must contain numbers";
        }
        if (!preg_match('/[!@#$%^&*()_+\-=\[\]{};:\'",.<>?\/\\|`~]/', $password)) {
            $errors[] = "Password must contain special characters";
        }
        
        return [
            'valid' => count($errors) === 0,
            'errors' => $errors
        ];
    }

    /**
     * Rate limiting helper (requires Redis or file-based storage)
     * 
     * @param string $identifier IP address or user ID
     * @param int $limit Max requests
     * @param int $window Time window in seconds
     * @return bool True if request is allowed, false if limit exceeded
     */
    public static function checkRateLimit($identifier, $limit = 5, $window = 60) {
        // Simple file-based implementation (not recommended for production)
        // For production, use Redis
        
        $rate_dir = sys_get_temp_dir() . '/rate_limit';
        if (!is_dir($rate_dir)) {
            @mkdir($rate_dir, 0700);
        }
        
        $file = $rate_dir . '/' . md5($identifier) . '.txt';
        $now = time();
        
        if (file_exists($file)) {
            $data = json_decode(file_get_contents($file), true);
            $data['hits'] = array_filter($data['hits'], function($t) use ($now, $window) {
                return ($now - $t) < $window;
            });
            
            if (count($data['hits']) >= $limit) {
                return false;
            }
            
            $data['hits'][] = $now;
            file_put_contents($file, json_encode($data));
            return true;
        } else {
            file_put_contents($file, json_encode(['hits' => [$now]]));
            return true;
        }
    }

    /**
     * Log security event
     * 
     * @param string $event Event type
     * @param string $details Event details
     * @param string $severity one of: 'INFO', 'WARNING', 'CRITICAL'
     */
    public static function logSecurityEvent($event, $details = '', $severity = 'WARNING') {
        $timestamp = date('Y-m-d H:i:s');
        $ip = $_SERVER['REMOTE_ADDR'] ?? 'unknown';
        $log_entry = "[$timestamp] [$severity] [$ip] Event: $event | Details: $details\n";
        
        error_log($log_entry, 3, sys_get_temp_dir() . '/security.log');
    }
}

// ============================================
// MIGRATION HELPERS (for gradual replacement)
// ============================================

/**
 * Helper: Check if password was hashed with old MD5 method
 * Used during migration phase
 * 
 * @param string $plain Plain password
 * @param string $stored_hash Old MD5 hash
 * @return bool
 */
function isMD5Hash($stored_hash) {
    // MD5 hashes are always 32 hex characters
    return (strlen($stored_hash) === 32 && ctype_xdigit($stored_hash));
}

/**
 * Migration: Verify old MD5 password and re-hash with bcrypt
 * Call this during login, if MD5 hash detected, upgrade to bcrypt
 * 
 * @param string $plain Plain password
 * @param string $md5_hash Old MD5 hash
 * @return string|false New bcrypt hash, or false if password doesn't match
 */
function migrateFromMD5($plain, $md5_hash) {
    if (md5($plain) === $md5_hash) {
        // Password is correct, create new bcrypt hash
        return SecurityUtils::hashPassword($plain);
    }
    return false;
}

?>
