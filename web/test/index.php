<?php
	session_start();
	require_once 'class.user.php';require_once __DIR__ . '/../lib/SecurityUtils.php';	$user_login = new USER();
	if($user_login->is_logged_in()!=""){
		$user_login->redirect('user.php');
	}
	if(isset($_POST['btn-login'])){
		$email = trim($_POST['txtemail']);
		$upass = trim($_POST['txtupass']);
		if($user_login->login($email,$upass)){
			$user_login->redirect('user.php');
		}
	}
	$reg_user = new USER();
	if($reg_user->is_logged_in()!=""){
		$reg_user->redirect('user.php');
	}
	if(isset($_POST['btn-signup'])){
		$uname = trim($_POST['txtuname']);
		$email = trim($_POST['txtemail']);
		$upass = trim($_POST['txtpass']);
		$code = SecurityUtils::generateSecureToken(32);
		$stmt = $reg_user->runQuery("SELECT * FROM tbl_users WHERE userEmail=:email_id");
		$stmt->execute(array(":email_id"=>$email));
		$row = $stmt->fetch(PDO::FETCH_ASSOC);
		if($stmt->rowCount() > 0){
			$msg = "
				<div class='alert alert-error'>
					<button class='close' data-dismiss='alert'>&times;</button>
					<strong>Извините!</strong> Данный email уже зарегистрирован.
				</div>
			";
		}
		else{
			if($reg_user->register($uname,$email,$upass,$code)){			
				$id = $reg_user->lasdID();		
				$key = base64_encode($id);
				$id = $key;
				$message = "					
					Здравствуте, $uname,
						<br /><br />
						Добро пожаловать!<br/>
						Что бы завершить регистрацию, нажмите на ссылку<br/>
						<br /><br />
						<a href='http://login/verify.php?id=$id&code=$code'>Активация аккаунта</a>
						<br /><br />
						Спасибо";
				$subject = "Активация аккаунта";
				$reg_user->send_mail($email,$message,$subject);	
				$msg = "
					<div class='alert alert-success'>
						<button class='close' data-dismiss='alert'>&times;</button>
						<strong>Успех!</strong>Мы отправили письмо на $email.
                    Пожалуйста, перейдите по ссылки из письма для активации аккаунта. 
			  		</div>
					";
			}
			else{
				echo "sorry , Query could no execute...";
			}		
		}
	}
?>
<!DOCTYPE html>
<html>
	<head>
		<meta charset="UTF-8" />
		<meta http-equiv="X-UA-Compatible" content="IE=edge"> 
		<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=0" />
		<title>Поиск жилья</title>
		<meta name="description" content="#" />
		<meta name="keywords" content="#" />
		<meta name="author" content="X0TTA6bI4" />
		<link href='https://fonts.googleapis.com/css?family=Kurale&subset=latin,cyrillic' rel='stylesheet' type='text/css'>
		<link rel="stylesheet" type="text/css" href="css/normalize.css" />
		<link rel="stylesheet" type="text/css" href="css/component.css" />
		<link rel="stylesheet" href="css/style.css"> <!-- Resource style -->
		<link rel="stylesheet" type="text/css" href="css/content.css" />
		<link rel="stylesheet" type="text/css" href="css/menu_elastic.css" />
		<script src="js/modernizr.js"></script> <!-- Modernizr -->
		<script src="js/snap.svg-min.js"></script>
		<!--[if IE]>
  		<script src="http://html5shiv.googlecode.com/svn/trunk/html5.js"></script>
		<![endif]-->
	</head>
	<body>
		<div class="container">
			<header class="cd-main-header">
				<a href="#0" class="cd-logo"><img src="img/cd-logo.svg" alt="Logo"></a>
				<div class="cd-search is-hidden">
					<form action="#0">
						<input type="search" placeholder="Поиск...">
					</form>
				</div> <!-- cd-search -->
				<!-- Вход и регистрация -->
				<div class="mockup-content">
					<div class="morph-button morph-button-modal morph-button-modal-2 morph-button-fixed">
						<button type="button">Вход</button>
						<div class="morph-content">
								<div class="content-style-form content-style-form-1">
									<span class="icon icon-close">Закрыть</span>
									<h2>Вход</h2>
									<form class="form-signin" method="post">
										<p><label>Email</label><input type="email" name="txtemail" autofocus></p>
										<p><label>Пароль</label><input type="password" name="txtupass"></p>
										<p><button name="btn-login">Войти</button></p>
										<div class="alert alert-info" style="margin-top:15px;">
											<p><a href="fpass.php">Забыли пароль?</a></p>
										</div>
									</form>
								</div>
						</div>
					</div>
					<div class="morph-button morph-button-modal morph-button-modal-3 morph-button-fixed">
						<button type="button">Регистрация</button>
						<div class="morph-content">
							<div>
								<div class="content-style-form content-style-form-2">
									<span class="icon icon-close">Закрыть</span>
									<h2>Регистрация</h2>
									<form class="form-signin" method="post">
										<p><em class='result_email'></em></p>
										<p><label>Email</label><input type="email" name="txtemail" autofocus></p>
										<p><em class='result_password'></em></p>
										<p><label>Ваше имя</label><input type="text" name="txtuname"></p>
										<p><label>Пароль</label><input type="password" name="txtpass"></p>
										<p><button class="btn btn-large btn-primary" type="submit" name="btn-signup">Отправить</button></p>
										<p><strong>Внимание!</strong> - После регистрации, на ваш email прийдет активационное письмо..</p>
										<div class="alert alert-info" style="margin-top:15px;">
											<p>Уже есть аккаунт? <a href="#">Войдите.</a></p>
										</div>
									</form>
								</div>
							</div>
						</div>
					</div>
				</div>
				<!-- Конец.Вход и регистрация -->
				<button class="menu-button" id="open-button">Open Menu</button>
				<div class="overlay"></div>
			</header>
			<div class="menu-wrap">
				<main class="cd-main-content">
					<button class="close-button" id="close-button">Close Menu</button>
					<nav class="cd-side-nav">
						<ul class="top-nav">
							<li class="cd-label">Личный кабинет</li>
							<li class="has-children overview">
								<a href="#0">Личные данные</a>
								<ul>
									<li><a href="#0">All Data</a></li>
									<li><a href="#0">Category 1</a></li>
									<li><a href="#0">Category 2</a></li>
								</ul>
							</li>
							<li class="has-children notifications">
								<a href="#0">Уведомления<span class="count">3</span></a>
								<ul>
									<li><a href="#0">All Notifications</a></li>
									<li><a href="#0">Friends</a></li>
									<li><a href="#0">Other</a></li>
								</ul>
							</li>
							<li class="has-children comments">
								<a href="#0">Сообщения</a>
								<ul>
									<li><a href="#0">All Comments</a></li>
									<li><a href="#0">Edit Comment</a></li>
									<li><a href="#0">Delete Comment</a></li>
								</ul>
							</li>
							<li class="has-children images">
								<a href="#0">Настройки</a>
								<ul>
									<li><a href="#0">All Images</a></li>
									<li><a href="#0">Edit Image</a></li>
								</ul>
							</li>
						</ul>
						<ul>
							<li class="cd-label">Путешествия</li>
							<li class="has-children bookmarks">
								<a href="#0">Мои бронирования</a>
								<ul>
									<li><a href="#0">Мои бронирования</a></li>
									<li><a href="#0">Заявки на бронирование</a></li>
									<li><a href="#0">Import Bookmark</a></li>
								</ul>
							</li>
							<li class="has-children users">
								<a href="#0">Мои отзывы</a>
								<ul>
									<li><a href="#0">All Users</a></li>
									<li><a href="#0">Edit User</a></li>
									<li><a href="#0">Add User</a></li>
								</ul>
							</li>
						</ul>
						<ul>
							<li class="cd-label">Моя недвижимость</li>
							<li class="has-children bookmarks">
								<a href="#0">Мои объявления</a>
								<ul>
									<li><a href="#0">Мои бронирования</a></li>
									<li><a href="#0">Заявки на бронирование</a></li>
									<li><a href="#0">Import Bookmark</a></li>
								</ul>
							</li>
							<li class="has-children users">
								<a href="#0">Заявки на бронь</a>
								<ul>
									<li><a href="#0">All Users</a></li>
									<li><a href="#0">Edit User</a></li>
									<li><a href="#0">Add User</a></li>
								</ul>
							</li>
							<li class="has-children users">
								<a href="#0">Добавить объект</a>
								<ul>
									<li><a href="#0">All Users</a></li>
									<li><a href="#0">Edit User</a></li>
									<li><a href="#0">Add User</a></li>
								</ul>
							</li>
						</ul>
					</nav>
				</main>
				<div class="morph-shape" id="morph-shape" data-morph-open="M-1,0h101c0,0,0-1,0,395c0,404,0,405,0,405H-1V0z">
					<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 100 800" preserveAspectRatio="none">
						<path d="M-1,0h101c0,0-97.833,153.603-97.833,396.167C2.167,627.579,100,800,100,800H-1V0z"/>
					</svg>
				</div>
			</div>
			<div class="content-wrapper">
						<h1>Что то будет написано</h1>
			</div><!-- /content-wrap -->
					<?php if(isset($msg)) echo $msg;  ?>
					<?php
						if(isset($_GET['error'])){
					?>
					<div class='alert alert-success'>
						<button class='close' data-dismiss='alert'>&times;</button>
						<strong>Wrong Details!</strong> 
					</div>
					<?php
						}
					?>
					<?php 
						if(isset($_GET['inactive'])){
					?>
					<div class='alert alert-error'>
						<button class='close' data-dismiss='alert'>&times;</button>
						<strong>Извините!</strong> Ваш аккаунт не активирован. 
					</div>
					<?php
						}
					?>
		</div><!-- /container -->
		<script src="js/classie.js"></script>
		<script src="js/main3.js"></script>
		<script src="js/uiMorphingButton_fixed.js"></script>
		<script>
			(function() {
				var docElem = window.document.documentElement, didScroll, scrollPosition;
					// trick to prevent scrolling when opening/closing button
				function noScrollFn() {
					window.scrollTo( scrollPosition ? scrollPosition.x : 0, scrollPosition ? scrollPosition.y : 0 );
				}
				function noScroll() {
					window.removeEventListener( 'scroll', scrollHandler );
					window.addEventListener( 'scroll', noScrollFn );
				}
				function scrollFn() {
					window.addEventListener( 'scroll', scrollHandler );
				}
				function canScroll() {
					window.removeEventListener( 'scroll', noScrollFn );
					scrollFn();
				}
				function scrollHandler() {
					if( !didScroll ) {
						didScroll = true;
						setTimeout( function() { scrollPage(); }, 60 );
					}
				};
				function scrollPage() {
					scrollPosition = { x : window.pageXOffset || docElem.scrollLeft, y : window.pageYOffset || docElem.scrollTop };
					didScroll = false;
				};
				scrollFn();
				[].slice.call( document.querySelectorAll( '.morph-button' ) ).forEach( function( bttn ) {
					new UIMorphingButton( bttn, {
						closeEl : '.icon-close',
						onBeforeOpen : function() {
							// don't allow to scroll
						noScroll();
						},
						onAfterOpen : function() {
							// can scroll again
							canScroll();
						},
						onBeforeClose : function() {
							// don't allow to scroll
							noScroll();
						},
						onAfterClose : function() {
							// can scroll again
							canScroll();
						}
					} );
				} );
			})();
		</script>
	</body>
</html>