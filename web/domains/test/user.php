<?php
session_start();
require_once 'class.user.php';
$user_home = new USER();
if(!$user_home->is_logged_in()){
	$user_home->redirect('index.php');
}
$stmt = $user_home->runQuery("SELECT * FROM tbl_users WHERE userID=:uid");
$stmt->execute(array(":uid"=>$_SESSION['userSession']));
$row = $stmt->fetch(PDO::FETCH_ASSOC);
?>

<!doctype html>
<html lang="en" class="no-js">
<head>
	<meta charset="UTF-8" />
	<meta http-equiv="X-UA-Compatible" content="IE=edge"> 
	<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=0" />
	<meta name="description" content="#" />
	<meta name="keywords" content="#" />
	<meta name="author" content="X0TTA6bI4" />
	<title>Личный кабинет</title>
	<link rel="stylesheet" href="css/normalize.css"> <!-- CSS reset -->
	<link rel="stylesheet" href="css/style.css"> <!-- Resource style -->
	<script src="js/modernizr.js"></script> <!-- Modernizr -->
</head>
<body>
	<header class="cd-main-header">
		<a href="#0" class="cd-logo"><img src="img/cd-logo.svg" alt="Logo"></a>
		
		<div class="cd-search is-hidden">
			<form action="#0">
				<input type="search" placeholder="Поиск...">
			</form>
		</div> <!-- cd-search -->
		<a href="#0" class="cd-nav-trigger">Меню<span></span></a>
		<nav class="cd-nav">
			<ul class="cd-top-nav">
				<li><a href="#0">Поддержка</a></li>
				<li class="has-children account">
					<a href="#0">
						<img src="img/cd-avatar.png" alt="avatar">
						<?php echo $row['userName']; ?> <i class="caret"></i>
					</a>

					<ul>

						<li><a href="#0">Профиль</a></li>
						<li><a tabindex="-1" href="logout.php">Выход</a></li>
					</ul>
				</li>
			</ul>
		</nav>
	</header> <!-- .cd-main-header -->

	<main class="cd-main-content">
		<nav class="cd-side-nav">
			<ul>
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
		<div class="content-wrapper">
		</div> <!-- .content-wrapper -->
	</main> <!-- .cd-main-content -->
<script src="js/jquery-2.1.4.js"></script>
<script src="js/jquery.menu-aim.js"></script>
<script src="js/main.js"></script> <!-- Resource jQuery -->
</body>
</html>