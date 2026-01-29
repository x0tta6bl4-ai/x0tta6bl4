<?php
	include_once 'setting.php';
	require_once __DIR__ . '/../lib/SecurityUtils.php';
	session_start();
	$CONNECT = mysqli_connect(HOST, USER, PASS, DB);
	$_COOKIE['user'] = FormChars($_COOKIE['user'], 1);
	
	// Создание куки
	if (!$_SESSION['USER_LOGIN_IN'] and $_COOKIE['user']) {
		$Row = mysqli_fetch_assoc(mysqli_query($CONNECT, "SELECT `id`, `name`, `regdate`, `email`, `country`, `avatar`, `login`, `group` FROM `users` WHERE `password` = '$_COOKIE[user]'"));
		if (!$Row) {
			setcookie('user', '', strtotime('-30 days'), '/');
			unset($_COOKIE['user']);
			MessageSend(1, 'Ошибка авторизации', '/');
		}
		$_SESSION['USER_LOGIN_IN'] = 1;
		foreach ($Row as $Key => $Value) $_SESSION['USER_'.strtoupper($Key)] = $Value;
	}
	
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

	//Проверка уведомлений
	if ($_SESSION['USER_LOGIN_IN']) {
		if ($Page != 'notice') {
			$Num = mysqli_fetch_row(mysqli_query($CONNECT, "SELECT COUNT(`id`) FROM `notice` WHERE `status` = 0 AND `uid` = $_SESSION[USER_ID]"));
			if ($Num[0]) MessageSend(2, 'У вас есть непрочитанные уведомления. <a href="/notice">Прочитать ( <b>'.$Num[0].'</b> )</a>', '', 0);
		}
	}
	
	// Перенаправление
	if ($Page == 'index') include ('page/index.php');
	else if ($Page == 'register') include ('page/register.php');
	else if ($Page == 'login') include ('page/login.php');
	else if ($Page == 'account') include ('form/account.php');
	else if ($Page == 'profile') include('page/profile.php');
	else if ($Page == 'restore') include('page/restore.php');
	else if ($Page == 'change') include('page/change.php');
	else if ($Page == 'edit') include('page/edit.php');
	else if ($Page == 'chat') include('page/chat.php');
	else if ($Page == 'user') include('page/user.php');
	else if ($Page == 'search') include('page/search.php');
	else if ($Page == 'notice') include('page/notice.php');
	else if ($Page == 'rate') include('form/rate.php');
	
	else if ($Page == 'news') {
		if (!$Module or $Page == 'news' and $Module == 'category' or $Page == 'news' and $Module == 'main') include('module/news/main.php');
		else if ($Module == 'material') {
			include('module/comments/main.php');
			include('module/news/material.php');
		}
		else if ($Module == 'add') include('module/news/add.php');
		else if ($Module == 'edit') include('module/news/edit.php');
		else if ($Module == 'control') include('module/news/control.php');
	}
	else if ($Page == 'loads') {
		if (!$Module or $Page == 'loads' and $Module == 'category' or $Page == 'loads' and $Module == 'main') include('module/loads/main.php');
		else if ($Module == 'material') {
			include('module/comments/main.php');
			include('module/loads/material.php');
		}
		else if ($Module == 'add') include('module/loads/add.php');
		else if ($Module == 'edit') include('module/loads/edit.php');
		else if ($Module == 'control') include('module/loads/control.php');
		else if ($Module == 'download') include('module/loads/download.php');
	}
	else if ($Page == 'comments') {
		if ($Module == 'add') include('module/comments/add.php');
		else if ($Module == 'control') include('module/comments/control.php');
	}
	else if ($Page == 'admin') {
		if ($_SESSION['ADMIN_LOGIN_IN']) {
			if(!$Module) include('module/admin/main.php');
			else if($Module == 'stats') include('module/admin/stats.php');
			else if($Module == 'query') include('module/admin/query.php');
		}
		else {
			if($Module == '1234') {
				$_SESSION['ADMIN_LOGIN_IN'] = 1;
				MessageSend(3, 'Вход администратора выполнен успешно.', '/admin');
			}
		}
	}

	//Перенаправление
	function Location ($p1) {
		if (!$p1) $p1 = $_SERVER['HTTP_REFERER'];
		exit(header('Location: '.$p1));
	}
	
	// Проверка регистрации
	function ULogin($p1) {
		if ($p1 <= 0 and $_SESSION['USER_LOGIN_IN'] != $p1) MessageSend(1, 'Данная страница доступна только для гостей.', '/');
		else if ($_SESSION['USER_LOGIN_IN'] != $p1) MessageSend(1, 'Данная сртаница доступна только для пользователей.', '/');
	}
	
	// Деление пользователей на группы
	function UserGroup($p1) {
		if ($p1 == 0) return 'Пользователь';
		else if ($p1 == 1) return 'Модератор';
		else if ($p1 == 2) return 'Администратор';
		else if ($p1 == -1) return 'Заблокирован';
	}
	
	// Доступ пользователей
	function UAccess($p1) {
		global $CONNECT;
		ULogin(1);
		if ($_SESSION['USER_GROUP'] < $p1) MessageSend(1, 'У вас нет прав доступа для просмотра данной страницйы сайта.', '/');
	}

	// Вывод ошибок
	function MessageSend($p1, $p2, $p3 = '', $p4 = 1) {
		if ($p1 == 1) $p1 = 'Ошибка';
		else if ($p1 == 2) $p1 = 'Подсказка';
		else if ($p1 == 3) $p1 = 'Информация';
		$_SESSION['message'] = '<div class="MessageBlock"><b>'.$p1.'</b>: '.$p2.'</div>';
		if ($p4) {
			Location($p3);
		}
	}
	
	function MessageShow() {
		if ($_SESSION['message'])$Message = $_SESSION['message'];
		echo $Message;
		$_SESSION['message'] = array();
	}
	
	// Генератор пароля - SECURITY FIX: bcrypt вместо md5
	function GenPass ($p1, $p2 = '') {
		return SecurityUtils::hashPassword($p1);
	}

	// Верификация пароля - SECURITY FIX
	function VerifyPass($password, $hash) {
		if (isMD5Hash($hash)) {
			// Legacy MD5 - attempt migration
			return migrateFromMD5($password, $hash);
		}
		return SecurityUtils::verifyPassword($password, $hash);
	}
	
	// Чистка спецсимволов
	function FormChars($p1, $p2 = 0) {
		global $CONNECT;
		if ($p2) return mysqli_real_escape_string($CONNECT, $p1);
		else return nl2br(htmlspecialchars(trim($p1), ENT_QUOTES), false);
	}
	
	// Генератор случайного пароля
	function RandomString($p1) {
		$Char = '0123456789abcdefghijklmnopqrstuvwxyz';
		for ($i = 0; $i < $p1; $i ++) $String .= $Char[rand(0, strlen($Char) - 1)];
		return $String;
	}
	
	//Миниатюры
	function MiniIMG($p1, $p2, $p3, $p4, $p5 = 50) {
		/*
		$p1 - Путь к изображению, которое нужно уменьшить.
		$p2 - Директория, куда будет сохранена уменьшенная копия.
		$p3 - Ширина уменьшенной копии.
		$p4 - Высота уменьшенной копии.
		$p5 - Качество уменьшенной копии.
		*/
		$Scr = imagecreatefromjpeg($p1);
		$Size = getimagesize($p1);
		$Tmp = imagecreatetruecolor($p3, $p4);
		imagecopyresampled($Tmp, $Scr, 0, 0, 0, 0, $p3, $p4, $Size[0], $Size[1]);
		imagejpeg($Tmp, $p2, $p5);
		imagedestroy($Scr);
		imagedestroy($Tmp);
	}
	
	// Присваиванеи ID модулю
	function ModuleID($p1) {
		if ($p1 == 'news') return 1;
		else if ($p1 == 'loads') return 2;
		else MessageSend(1, 'Модуль не найден.', '/');
	}
	
	//Поиск
	function SearchForm() {
		global $Page;
		echo '<form method="POST" action="/search/'.$Page.'"><input type="text" name="text" value="'.$_SESSION['SEARCH'].'" placeholder="Что искать?" required><input type="submit" name="submit" value="Поиск"></form>';	
	}
	
	//Уведомления
	function SendNotice($p1, $p2) {
		global $CONNECT;
		$Row = mysqli_fetch_assoc(mysqli_query($CONNECT, "SELECT `id` FROM `users` WHERE `login` = '$p1'"));
		if (!$Row['id']) echo 'Ошибка';
		mysqli_query($CONNECT, "INSERT INTO `notice` VALUES ('', $Row[id], 0, NOW(), '$p2')");
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
				<link rel="stylesheet" type="text/css" href="/resource/css/header.css" />
				<link rel="stylesheet" type="text/css" href="/resource/css/menu.css" />
				<link rel="stylesheet" type="text/css" href="/resource/css/content.css" />
				<script src="/resource/js/modernizr.custom.js"></script></head>
				<script src="/resource/js/snap.svg-min.js"></script>
		';
	}
	
	// Переключатель страниц
	function PageSelector($p1, $p2, $p3, $p4 = 5) {
		$Page = ceil($p3[0] / $p4);
		if ($Page > 1) {
			echo '
				<div class="PageSelector">
			';
			for ($i = ($p2 - 3); $i < ($Page + 1); $i++) {
				if ($i > 0 and $i <= ($p2 + 3)) {
					if ($p2 == $i) $Swch = 'SwchItemCur';
					else $Swch = 'SwchItem';
					echo '
						<a class="" href="'.$p1.$i.'">'.$i.'</a>
					';
				}
			}
			echo '
				</div>
			';
		}
	}
	
	// Кнопки входа в шапке
	function Buttons() {
		if ($_SESSION['USER_AVATAR'] == 0) $Avatar = 0;
		else $Avatar = $_SESSION['USER_AVATAR'].'/'.$_SESSION['USER_ID'];
		if ($_SESSION['USER_LOGIN_IN'] != 1) $Buttons = '
		<div class="mockup-content">
			<div class="morph-button morph-button-modal morph-button-modal-2 morph-button-fixed">
				<button type="button">Вход</button>
				<div class="morph-content">
					<div class="content-style-form content-style-form-1">
						<span class="icon icon-close">Закрыть</span>
						<h2>Вход</h2>
						<form method="POST" action="/account/login">
							<span class="input input--yoko">
								<input class="input__field input__field--yoko" type="email" id="input-2" name="email" required />
								<label class="input__label input__label--yoko" for="input-2">
									<span class="input__label-content input__label-content--yoko">Email</span>
								</label></span>
							<span class="input input--yoko">
								<input class="input__field input__field--yoko" type="password" id="input-3" name="password" maxlength="15" pattern="[A-Za-z-0-9]{6,15}" title="Только латиница и цифры. Не менее 6 и не более 15 символов." required />
								<label class="input__label input__label--yoko" for="input-3">
									<span class="input__label-content input__label-content--yoko">Пароль</span>
								</label></span>
							<p><input type="checkbox" name="remember"> Запомнить</p>
							<p><button class="btn btn-large btn-primary" type="submit" value="register" name="submit">Отправить</button></p>
							<div class="alert info">
								<p><a href="/restore">Забыли пароль?</a></p>
							</div>
						</form>
					</div>
				</div>
			</div>
			<div class="morph-button morph-button-modal morph-button-modal-3 morph-button-fixed">
				<button type="button">Регистрация</button>
				<div class="morph-content">
					<div class="content-style-form content-style-form-2">
						<span class="icon icon-close">Закрыть</span>
						<h2>Регистрация</h2>
						<form class="form-signin" method="post" action="account/register">
							<span class="input input--yoko">
								<input class="input__field input__field--yoko" type="text" id="input-1" name="login" maxlength="15" pattern="[А-Яа-яЁё]{3,15}" title="Только кирилица. Не менее 3 и не более 15 символов." required autofocus />
								<label class="input__label input__label--yoko" for="input-1">
									<span class="input__label-content input__label-content--yoko">Ваше имя</span>
								</label>
								<svg class="graphic graphic--yoko" width="300%" height="100%" viewBox="0 0 1200 60" preserveAspectRatio="none">
									<path d="M0,56.5c0,0,298.666,0,399.333,0C448.336,56.5,513.994,46,597,46c77.327,0,135,10.5,200.999,10.5c95.996,0,402.001,0,402.001,0"/>
								</svg>
							</span>
							<span class="input input--yoko">
								<input class="input__field input__field--yoko" type="email" id="input-2" name="email" required />
								<label class="input__label input__label--yoko" for="input-2">
									<span class="input__label-content input__label-content--yoko">Email</span>
								</label>
								<svg class="graphic graphic--yoko" width="300%" height="100%" viewBox="0 0 1200 60" preserveAspectRatio="none">
									<path d="M0,56.5c0,0,298.666,0,399.333,0C448.336,56.5,513.994,46,597,46c77.327,0,135,10.5,200.999,10.5c95.996,0,402.001,0,402.001,0"/>
								</svg>
							</span>
							<span class="input input--yoko">
								<input class="input__field input__field--yoko" type="password" id="input-3" name="password" maxlength="15" pattern="[A-Za-z-0-9]{6,15}" title="Только латиница и цифры. Не менее 6 и не более 15 символов." required />
								<label class="input__label input__label--yoko" for="input-3">
									<span class="input__label-content input__label-content--yoko">Пароль</span>
								</label>
								<svg class="graphic graphic--yoko" width="300%" height="100%" viewBox="0 0 1200 60" preserveAspectRatio="none">
									<path d="M0,56.5c0,0,298.666,0,399.333,0C448.336,56.5,513.994,46,597,46c77.327,0,135,10.5,200.999,10.5c95.996,0,402.001,0,402.001,0"/>
								</svg>
							</span>
							<p><button class="btn btn-large btn-primary" type="submit" value="register" name="submit">Отправить</button></p>
							<p><strong>Внимание!</strong> - После регистрации, на ваш email прийдет активационное письмо..</p>
							<div class="alert alert-info" style="margin-top:15px;">
								<p>Уже есть аккаунт? <a href="#">Войдите.</a></p>
							</div>
						</form>
					</div>
				</div>
			</div>
		</div>
		';
		else $Buttons = '
		<nav class="cd-nav">
			<ul class="cd-top-nav">
				<li class="has-children account">
					<a href="#0">
						<img = src="/resource/avatar/'.$Avatar.'.jpg" width="200" height="200" alt="Аватар">
						'.$_SESSION['USER_LOGIN'].'<i class="caret"></i>
					</a>

					<ul>

						<li><a href="/profile">Профиль</a></li>
						<li><a tabindex="-1" href="/account/logout">Выход</a></li>
					</ul>
				</li>
			</ul>
		</nav>
		';
		echo $Buttons;
	}
?>
