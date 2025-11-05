<?php
session_start();
require_once 'class.user.php';
$user = new USER();

if($user->is_logged_in()!="")
{
	$user->redirect('user.php');
}

if(isset($_POST['btn-submit']))
{
	$email = $_POST['txtemail'];
	
	$stmt = $user->runQuery("SELECT userID FROM tbl_users WHERE userEmail=:email LIMIT 1");
	$stmt->execute(array(":email"=>$email));
	$row = $stmt->fetch(PDO::FETCH_ASSOC);	
	if($stmt->rowCount() == 1)
	{
		$id = base64_encode($row['userID']);
		$code = md5(uniqid(rand()));
		
		$stmt = $user->runQuery("UPDATE tbl_users SET tokenCode=:token WHERE userEmail=:email");
		$stmt->execute(array(":token"=>$code,"email"=>$email));
		
		$message= "
				   Здравствуйте , $email
				   <br /><br />
				   Мы получили запрос на восстановление Вашего пароля, если это было сделано вами, просто нажмите на ссылку ниже.Если же Вы этого не делали, просто проигнорируйте это письмо.
				   <br /><br />
				   Нажмите на ссылку для восстановления пароля
				   <br /><br />
				   <a href='http://login/resetpass.php?id=$id&code=$code'></a>
				   <br /><br />
				   ";
		$subject = "Восстановление пароля";
		
		$user->send_mail($email,$message,$subject);
		
		$msg = "<div class='alert alert-success'>
					<button class='close' data-dismiss='alert'>&times;</button>
					Мы выслали письмо на $email.
					Пожалуйста, перейдите по ссылке, указанной в письме для восстановления пароля.
			  	</div>";
	}
	else
	{
		$msg = "<div class='alert alert-danger'>
					<button class='close' data-dismiss='alert'>&times;</button>
					<strong>Извините!</strong>  Данный email не найден в базе. 
			    </div>";
	}
}
?>

<!DOCTYPE html>
<html> 
  <head>
    <title>Восстановление пароля</title>
	<meta charset="UTF-8" />
	<meta http-equiv="X-UA-Compatible" content="IE=edge"> 
	<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=0" />
	<meta name="description" content="#" />
	<meta name="keywords" content="#" />
	<meta name="author" content="X0TTA6bI4" />
    <!-- Bootstrap -->
     <!-- HTML5 shim, for IE6-8 support of HTML5 elements -->
    <!--[if lt IE 9]>
      <script src="http://html5shim.googlecode.com/svn/trunk/html5.js"></script>
    <![endif]-->
  </head>
  <body id="login">
    <div class="container">

      <form class="form-signin" method="post">
        <h2 class="form-signin-heading">Восстановление пароля</h2><hr />
        
        	<?php
			if(isset($msg))
			{
				echo $msg;
			}
			else
			{
				?>
              	<div class='alert alert-info'>
				Пожалуйста, введите Ваш email. Мы вышлем Вам письмо с ссылкой для восстановления пароля.
				</div>  
                <?php
			}
			?>
        
        <input type="email" class="input-block-level" placeholder="Введите email" name="txtemail" required />
     	<hr />
        <button class="btn btn-danger btn-primary" type="submit" name="btn-submit">Выслать письмо</button>
      </form>

    </div> <!-- /container -->
    <script src="bootstrap/js/jquery-1.9.1.min.js"></script>
    <script src="bootstrap/js/bootstrap.min.js"></script>
  </body>
</html>