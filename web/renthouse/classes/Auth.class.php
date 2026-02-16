<?php

namespace Auth;

// Include security utilities
require_once __DIR__ . '/../../lib/SecurityUtils.php';

class User
{
    private $id;
    private $username;
    private $db;
    private $user_id;

    private $db_host = "localhost";
    private $db_name = "testdb";
    private $db_user = "testdb";
    private $db_pass = "testdb";

    private $is_authorized = false;

    public function __construct($username = null, $password = null)
    {
        $this->username = $username;
        $this->connectDb($this->db_name, $this->db_user, $this->db_pass, $this->db_host);
    }

    public function __destruct()
    {
        $this->db = null;
    }

    public static function isAuthorized()
    {
        if (!empty($_SESSION["user_id"])) {
            return (bool) $_SESSION["user_id"];
        }
        return false;
    }

    /**
     * DEPRECATED: Use SecurityUtils::hashPassword() instead.
     * Kept for backward compatibility if needed, but should not be used for new auth.
     */
    public function passwordHash($password, $salt = null, $iterations = 10)
    {
        return array(
            'hash' => \SecurityUtils::hashPassword($password),
            'salt' => null
        );
    }

    /**
     * DEPRECATED: Salts are now handled internally by bcrypt/sodium.
     */
    public function getSalt($username) {
        $query = "select salt from users where username = :username limit 1";
        $sth = $this->db->prepare($query);
        $sth->execute(array(":username" => $username));
        $row = $sth->fetch();
        if (!$row) {
            return false;
        }
        return $row["salt"];
    }

    public function authorize($username, $password, $remember=false)
    {
        // Correct secure flow: Fetch hash by username, then verify in PHP
        $query = "select id, username, password, salt from users where username = :username limit 1";
        $sth = $this->db->prepare($query);
        $sth->execute(array(":username" => $username));
        $user = $sth->fetch();

        if (!$user) {
            $this->is_authorized = false;
            return false;
        }

        // Verify password
        // 1. Try standard verify (works for bcrypt/argon2)
        if (\SecurityUtils::verifyPassword($password, $user['password'])) {
            $this->user = $user;
            $this->is_authorized = true;
            $this->user_id = $this->user['id'];
            $this->saveSession($remember);
            return true;
        }
        
        // 2. Legacy fallback (if migration is needed and supported)
        // Check if old hash format is MD5 and migrate if so
        if (function_exists('isMD5Hash') && isMD5Hash($user['password'])) {
            // Check legacy salt handling if applicable, or assume raw MD5
            // Implementation depends on legacy logic. 
            // For now, we assume standard migration helper
            $newHash = migrateFromMD5($password, $user['password']);
            if ($newHash) {
                // Password matches legacy hash, update to new hash
                $update = $this->db->prepare("UPDATE users SET password = :pass WHERE id = :id");
                $update->execute([':pass' => $newHash, ':id' => $user['id']]);
                
                $this->user = $user;
                $this->is_authorized = true;
                $this->user_id = $this->user['id'];
                $this->saveSession($remember);
                return true;
            }
        }

        $this->is_authorized = false;
        return false;
    }

    public function logout()
    {
        if (!empty($_SESSION["user_id"])) {
            unset($_SESSION["user_id"]);
        }
    }

    public function saveSession($remember = false, $http_only = true, $days = 7)
    {
        $_SESSION["user_id"] = $this->user_id;

        if ($remember) {
            // Save session id in cookies
            $sid = session_id();

            $expire = time() + $days * 24 * 3600;
            $domain = ""; // default domain
            $secure = false;
            $path = "/";

            $cookie = setcookie("sid", $sid, $expire, $path, $domain, $secure, $http_only);
        }
    }

    public function create($username, $password) {
        $user_exists = $this->getSalt($username);

        if ($user_exists) {
            throw new \Exception("User exists: " . $username, 1);
        }

        $query = "insert into users (username, password, salt)
            values (:username, :password, :salt)";
        $hashes = $this->passwordHash($password);
        $sth = $this->db->prepare($query);

        try {
            $this->db->beginTransaction();
            $result = $sth->execute(
                array(
                    ':username' => $username,
                    ':password' => \SecurityUtils::hashPassword($password),
                    ':salt' => 'bcrypt', // Dummy value for NOT NULL constraint
                )
            );
            $this->db->commit();
        } catch (\PDOException $e) {
            $this->db->rollback();
            echo "Database error: " . $e->getMessage();
            die();
        }

        if (!$result) {
            $info = $sth->errorInfo();
            printf("Database error %d %s", $info[1], $info[2]);
            die();
        } 

        return $result;
    }

    public function connectdb($db_name, $db_user, $db_pass, $db_host = "localhost")
    {
        try {
            $this->db = new \pdo("mysql:host=$db_host;dbname=$db_name", $db_user, $db_pass);
        } catch (\pdoexception $e) {
            echo "database error: " . $e->getmessage();
            die();
        }
        $this->db->query('set names utf8');

        return $this;
    }
}
