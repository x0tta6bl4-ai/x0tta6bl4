<?php
class Database
{

    private $host = "localhost";
    private $db_name = "dbtest";
    private $username = "root";
    private $password = "";

    // SMTP Configuration
    public $smtp_host = "smtp.gmail.com";
    public $smtp_port = 465;
    public $smtp_user = "d0rmid0nt.db@gmail.com";
    public $smtp_pass = "hliupik11288"; // NOTE: Recommend moving to env or separate secure config

    public $conn;

    public function dbConnection()
    {

        $this->conn = null;
        try {
            $this->conn = new PDO("mysql:host=" . $this->host . ";dbname=" . $this->db_name, $this->username, $this->password);
            $this->conn->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        }
        catch (PDOException $exception) {
            echo "Connection error: " . $exception->getMessage();
        }

        return $this->conn;
    }
}
?>