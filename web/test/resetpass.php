<?php
// Security: Enable secure session configuration
ini_set('session.cookie_httponly', 1);
ini_set('session.cookie_secure', 1);  // HTTPS only
ini_set('session.cookie_samesite', 'Strict');
session_start();

require_once 'class.user.php';
$user = new USER();

// === SECURITY FIX #1: CSRF Token Generation ===
if (empty($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
}

// === SECURITY FIX #2: Validate URL parameters ===
if(empty($_GET['id']) && empty($_GET['code']))
{
	$user->redirect('index.php');
}

if(isset($_GET['id']) && isset($_GET['code']))
{
	// Decode and validate ID
	$id = base64_decode($_GET['id'], true);
	if ($id === false) {
		$msg = "<div class='alert alert-block'>
				<button class='close' data-dismiss='alert'>&times;</button>
				<strong>Error:</strong> Invalid request format.
				</div>";
		$rows = null;
	} else {
		$code = $_GET['code'];
		
		// === SECURITY FIX #3: Token format validation ===
		// Validate token is hexadecimal and reasonable length
		if (!preg_match('/^[a-f0-9]{64}$/', $code)) {
			$msg = "<div class='alert alert-block'>
					<button class='close' data-dismiss='alert'>&times;</button>
					<strong>Error:</strong> Invalid token format.
					</div>";
			$rows = null;
		} else {
			// === SECURITY FIX #4: Add token expiration check ===
			$stmt = $user->runQuery(
				"SELECT * FROM tbl_users 
				 WHERE userID=:uid AND tokenCode=:token 
				 AND (tokenExpiry IS NULL OR tokenExpiry > NOW()) 
				 LIMIT 1"
			);
			$stmt->execute(array(":uid"=>$id, ":token"=>$code));
			$rows = $stmt->fetch(PDO::FETCH_ASSOC);
		}
	}
	
	if(isset($rows) && $rows && $stmt->rowCount() == 1)
	{
		if(isset($_POST['btn-reset-pass']))
		{
			// === SECURITY FIX #5: CSRF Token Validation ===
			if (empty($_POST['csrf_token']) || $_POST['csrf_token'] !== $_SESSION['csrf_token']) {
				$msg = "<div class='alert alert-block'>
						<button class='close' data-dismiss='alert'>&times;</button>
						<strong>Security Error:</strong> Invalid request token. Please try again.
						</div>";
			}
			else if (
				// === SECURITY FIX #6: Password strength validation ===
				!isset($_POST['pass']) || !isset($_POST['confirm-pass']) ||
				strlen($_POST['pass']) < 12 ||
				!preg_match('/[A-Z]/', $_POST['pass']) ||
				!preg_match('/[0-9]/', $_POST['pass']) ||
				!preg_match('/[^a-zA-Z0-9]/', $_POST['pass'])
			) {
				$msg = "<div class='alert alert-block'>
						<button class='close' data-dismiss='alert'>&times;</button>
						<strong>Password Requirements:</strong> Minimum 12 characters, must include uppercase, number, and special character.
						</div>";
			}
			else
			{
				$pass = $_POST['pass'];
				$cpass = $_POST['confirm-pass'];
				
				if($cpass!==$pass)
				{
					$msg = "<div class='alert alert-block'>
							<button class='close' data-dismiss='alert'>&times;</button>
							<strong>Sorry!</strong>  Password Doesn't match. 
							</div>";
				}
				else
				{
					// === SECURITY FIX #7: Replace MD5 with bcrypt ===
					$password = password_hash($cpass, PASSWORD_BCRYPT, ['cost' => 12]);
					$stmt = $user->runQuery(
						"UPDATE tbl_users 
						 SET userPass=:upass, tokenCode=NULL, tokenExpiry=NULL 
						 WHERE userID=:uid"
					);
					$stmt->execute(array(":upass"=>$password, ":uid"=>$rows['userID']));
					
					// Invalidate CSRF token after successful password change
					unset($_SESSION['csrf_token']);
					
					$msg = "<div class='alert alert-success'>
							<button class='close' data-dismiss='alert'>&times;</button>
							Password Changed Successfully. Redirecting...
							</div>";
					header("refresh:3;index.php");
				}
			}
		}	
	}
	else
	{
		$msg = "<div class='alert alert-block'>
				<button class='close' data-dismiss='alert'>&times;</button>
				No Account Found or Token Expired. Try again.
				</div>";
		$rows = null;
	}
	
	
}

?>
<!DOCTYPE html>
<html>
  <head>
    <title>Password Reset</title>
    <!-- Bootstrap -->
    <link href="bootstrap/css/bootstrap.min.css" rel="stylesheet" media="screen">
    <link href="bootstrap/css/bootstrap-responsive.min.css" rel="stylesheet" media="screen">
    <link href="assets/styles.css" rel="stylesheet" media="screen">
     <!-- HTML5 shim, for IE6-8 support of HTML5 elements -->
    <!--[if lt IE 9]>
      <script src="http://html5shim.googlecode.com/svn/trunk/html5.js"></script>
    <![endif]-->
  </head>
  <body id="login">
    <div class="container">
    	<?php if(isset($rows) && $rows): ?>
    	<div class='alert alert-success'>
			<strong>Hello !</strong>  <?php echo htmlspecialchars($rows['userName']); ?> you are here to reset your forgotten password.
		</div>
		<?php endif; ?>
        <form class="form-signin" method="post">
        <h3 class="form-signin-heading">Password Reset.</h3><hr />
        
        <!-- CSRF Token -->
        <input type="hidden" name="csrf_token" value="<?php echo htmlspecialchars($_SESSION['csrf_token']); ?>">
        
        <?php
        if(isset($msg))
		{
			echo $msg;
		}
		?>
        
        <?php if(isset($rows) && $rows): ?>
        <div class="alert alert-info">
            <strong>Password Requirements:</strong>
            <ul>
                <li>Minimum 12 characters</li>
                <li>At least one uppercase letter</li>
                <li>At least one number</li>
                <li>At least one special character (!@#$%^&*)</li>
            </ul>
        </div>
        <input type="password" class="input-block-level" placeholder="New Password" name="pass" required />
        <input type="password" class="input-block-level" placeholder="Confirm New Password" name="confirm-pass" required />
     	<hr />
        <button class="btn btn-large btn-primary" type="submit" name="btn-reset-pass">Reset Your Password</button>
        <?php endif; ?>
      </form>

    </div> <!-- /container -->
    <script src="bootstrap/js/jquery-1.9.1.min.js"></script>
    <script src="bootstrap/js/bootstrap.min.js"></script>
  </body>
</html>