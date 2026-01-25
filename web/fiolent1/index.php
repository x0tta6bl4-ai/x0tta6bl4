<?php
	include_once 'setting.php';
	session_start();
	$CONNECT = mysqli_connect(HOST, USER, PASS, DB);
	
	// Деление ссылки
	if ($_SERVER['REQUEST_URI'] == '/') {
		$Page = 'index';
		$Module = 'index';
	} 
	else {
		$URL_Path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
		$URL_Parts = explode('/', trim($URL_Path, ' /'));
		$Page = array_shift($URL_Parts);
		$Module = array_shift($URL_Parts);
		
		if (!empty($Module)) {
			$Param = array();
			for ($i = 0; $i < count($URL_Parts); $i++) {
				$Param[$URL_Parts[$i]] = $URL_Parts[++$i];
			}
		}
	}

	// Перенаправление
	if ($Page == 'index') include ('page/index.php');
	else if ($Page == 'about') include ('page/about.php');
	else if ($Page == 'resort') include ('page/resort.php');
	else if ($Page == 'gallery') include('page/gallery.php');
	else if ($Page == 'service') include('page/service.php');
	else if ($Page == 'comments') include('page/comments.php');
	else if ($Page == 'contacts') include('page/contacts.php');
	else if ($Page == 'mail') include('page/mail.php');
	
	// Вывод ошибок
	function MessageSend($p1, $p2, $p3 = '') {
		if ($p1 == 1) $p1 = 'Ошибка';
		else if ($p1 == 2) $p1 = 'Подсказка';
		else if ($p1 == 3) $p1 = 'Информация';
		$_SESSION['message'] = '<div class="MessageBlock"><b>'.$p1.'</b>: '.$p2.'</div>';
		if ($p3) $_SERVER['HTTP_REFERER'] = $p3;
		exit(header('Location: '.$_SERVER['HTTP_REFERER']));
	}
	function MessageShow() {
		if ($_SESSION['message'])$Message = $_SESSION['message'];
		echo $Message;
		$_SESSION['message'] = array();
	}
	
	// Чистка спецсимволов
	function FormChars($p1) {
		return nl2br(htmlspecialchars(trim($p1), ENT_QUOTES), false);
	}
	
	//Header
	function HeaderMenu() {
		echo '
			<header class="header">
				<section class="menu">
					<nav class="cl-effect-12">
						<a href="/">Главная</a>
						<a href="/about">О пансионате</a>
						<a href="/resort">Мыс Фиолент</a>
						<a href="/gallery">Фотогалерея</a>
						<a href="/service">Услуги</a>
						<a href="/comments">Отзывы</a>
						<a href="/contacts">Контакты</a>
					</nav>
				</section>
			</header>
		';
	}
	
	function Footer() {
		echo '
			<strong>Footer:</strong>
		';
	}	
	
	// Заголовки
	function Head($p1) {
		echo '
			<!DOCTYPE html>
			<html>
				<head>
				<meta charset="UTF-8" />
				<meta http-equiv="X-UA-Compatible" content="IE=edge">
				<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=0" />
				<title>'.$p1.'</title>
				<meta name="description" content="#" />
				<meta name="keywords" content="#" />
				<meta name="author" content="X0TTA6bI4" />
				<link rel="icon" href="/resource/img/favicon.ico" />
				<link rel="stylesheet" type="text/css" href="/resource/css/normalize.css" />
				<link rel="stylesheet" type="text/css" href="/resource/css/component.css" />
				<script src="/resource/js/modernizr.custom.js"></script>
				<script src="/resource/js/jquery-2.2.0.min.js"></script>
		';
	}
?>
