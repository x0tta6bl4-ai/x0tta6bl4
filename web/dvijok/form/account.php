<?php
	// Завершение сессии
	if ($Module == 'logout' and $_SESSION['USER_LOGIN_IN'] == 1) {
		if ($_COOKIE['user']) {
			setcookie('user','', strtotime('-10 days'), '/');
			unset ($_COOKIE['user']);
		}
		session_unset();
		Location('/login');
	}
	
	//Проверка регистр. данных
	function CheckRegInfo($p1, $p2) {
		global $CONNECT;
		if (mysqli_fetch_assoc(mysqli_query($CONNECT, "SELECT `login` FROM `users` WHERE `login` = '$p1'"))) MessageSend(1, 'Логин <b>'.$_POST['login'].'</b> уже используеться.');
		else if (mysqli_fetch_assoc(mysqli_query($CONNECT, "SELECT `email` FROM `users` WHERE `email` = '$p2'"))) MessageSend(1, 'E-Mail <b>'.$_POST['email'].'</b> уже используеться.');
	}
	
	//Шифрование - SECURITY FIX: secure token вместо md5
	function MIX($p1) {
		// Use HMAC-based approach for consistent but secure tokens
		return hash_hmac('sha256', $p1 . date('d.m.Y H'), 'x0tta6bl4_secret_key_' . date('Y'));
	}
	
		// Редактирование профиля
	if ($Module == 'edit' and $_POST['submit']) {
		ULogin(1);
		$_POST['login'] = FormChars($_POST['login']);
		$_POST['town'] = FormChars($_POST['town']);
		$_POST['opassword'] = FormChars($_POST['opassword']);
		$_POST['npassword'] = FormChars($_POST['npassword']);

		if ($_POST['login'] != $_SESSION['USER_LOGIN']) {
			mysqli_query($CONNECT, "UPDATE `users`  SET `login` = '$_POST[login]' WHERE `id` = $_SESSION[USER_ID]");
			$_SESSION['USER_LOGIN'] = $_POST['login'];
		}
		
		if ($_POST['town'] != $_SESSION['USER_TOWN']) {
			mysqli_query($CONNECT, "UPDATE `users`  SET `town` = '$_POST[town]' WHERE `id` = $_SESSION[USER_ID]");
			$_SESSION['USER_TOWN'] = $_POST['town'];
		}
		if ($_POST['opassword'] or $_POST['npassword']) {
			if (!$_POST['opassword']) MessageSend(2, 'Не указан старый пароль');
			if (!$_POST['npassword']) MessageSend(2, 'Не указан новый пароль');
			// SECURITY FIX: Use proper password verification
			$storedHash = $_SESSION['USER_PASSWORD'];
			$verified = false;
			if (isMD5Hash($storedHash)) {
				$verified = (migrateFromMD5($_POST['opassword'], $storedHash) !== false);
			} else {
				$verified = SecurityUtils::verifyPassword($_POST['opassword'], $storedHash);
			}
			if (!$verified) MessageSend(2, 'Старый пароль указан не верно.');
			// Create new bcrypt hash
			$Password = SecurityUtils::hashPassword($_POST['npassword']);
			mysqli_query($CONNECT, "UPDATE `users`  SET `password` = '$Password' WHERE `id` = $_SESSION[USER_ID]");
			$_SESSION['USER_PASSWORD'] = $Password;
		}
		// Загрузка аватара
		if ($_FILES['avatar']['tmp_name']) {
			if ($_FILES['avatar']['type'] != 'image/jpeg') MessageSend(1, 'Не верный тип изображения.');
			if ($_FILES['avatar']['size'] > 100000) MessageSend(1, 'Размер изображения слишком большой.');
			$Image = imagecreatefromjpeg($_FILES['avatar']['tmp_name']);
			$Size = getimagesize($_FILES['avatar']['tmp_name']);
			$Tmp = imagecreatetruecolor(200, 200);
			imagecopyresampled($Tmp, $Image, 0, 0, 0, 0, 200, 200, $Size[0], $Size[1]);
			if ($_SESSION['USER_AVATAR'] == 0) {
				$Files = glob('resource/avatar/*', GLOB_ONLYDIR);
				foreach($Files as $num => $Dir) {
					$Num ++;
					$Count = sizeof(glob($Dir.'/*.*'));
					if ($Count < 250) {
						$Download = $Dir.'/'.$_SESSION['USER_ID'];
						$_SESSION['USER_AVATAR'] = $Num;
						mysqli_query($CONNECT, "UPDATE `users`  SET `avatar` = $Num WHERE `id` = $_SESSION[USER_ID]");
						break;
					}
				}
			}
			else $Download = 'resource/avatar/'.$_SESSION['USER_AVATAR'].'/'.$_SESSION['USER_ID'];
			imagejpeg($Tmp, $Download.'.jpg');
			imagedestroy($Image);
			imagedestroy($Tmp);
		}
		MessageSend(3, 'Данные изменены.');
	}
				
	// Восстановление пароля
	ULogin(0);
	if ($Module == 'restore' and $Param['code'] and $_SESSION['RESTORE_INFO'] and $_SESSION['RESTORE_CONFIRM']) {
		if (MIX($_SESSION['RESTORE_CONFIRM']) != $Param['code']) MessageSend(1, 'Восстановление не возможно.');
		$Random = RandomString(8);
		$Password = GenPass($Random, $_SESSION['RESTORE_INFO']);
		mysqli_query($CONNECT, "UPDATE `users` SET `password` = '$Password' WHERE `email` = '$_SESSION[RESTORE_INFO]'");
		unset($_SESSION['RESTORE_INFO']);
		unset($_SESSION['RESTORE_CONFIRM']);
		MessageSend(2, 'Пароль успешно изменен, для входа используйте новый пароль <b>'.$Random.'</b>', '/login');
	}
	if ($Module == 'restore' and $_POST['submit']) {
		$_POST['email'] = FormChars($_POST['email'], 1);
		if (!$_POST['email']) MessageSend(1, 'Невозможно обработать форму.');
		$Row = mysqli_fetch_assoc(mysqli_query($CONNECT, "SELECT `id`,`email` FROM `users` WHERE `email` = '$_POST[email]'"));
		if (!$Row['email']) MessageSend(1, 'Пользователь не зарегистрирован');
		$_SESSION['RESTORE_INFO'] = $Row['email'];
		$_SESSION['RESTORE_CONFIRM'] = GenPass($_POST['email'], $_POST['id']);
		mail($Row['email'], 'Mr.Shift', 'Ссылка для восстановления: http://dvijok/account/restore/code/'.MIX($_SESSION['RESTORE_CONFIRM']), 'From: web@mr-shift.ru');
		MessageSend(2, 'На ваш E-mail адрес <b>'.$Row['email'].'</b> отправлено подтерждение смены пароля');
	}	
		
	// Регистрация
	if ($Module == 'register' and $_POST['submit']) {
		$_POST['login'] = FormChars($_POST['login']);
		$_POST['email'] = FormChars($_POST['email']);
		$_POST['password'] = GenPass(FormChars($_POST['password']), $_POST['email']);
		if (!$_POST['login'] or !$_POST['email'] or !$_POST['password']) MessageSend(1, 'Ошибка валидации формы.');
		CheckRegInfo($_POST['login'], $_POST['email']);
		$_SESSION['REGISTER_INFO'] = "$_POST[login],$_POST[email],$_POST[password]";
		$_SESSION['REGISTER_CONFIRM'] = GenPass($_POST['email'], $_POST['login']);
		mail($_POST['email'], 'Регистрация', 'Ссылка для активации: http://dvijok/account/activate/code/'.MIX($_SESSION['REGISTER_CONFIRM']), 'From: web@dvijok.ru');
		MessageSend(3, 'Регистрация акаунта успешно завершена. На указанный E-mail адрес <b>'.$_POST['email'].'</b> отправленно письмо о подтверждении регистрации.');
	}
	else if ($Module == 'activate' and $Param['code'] and $_SESSION['REGISTER_INFO'] and $_SESSION['REGISTER_CONFIRM']) {
		if (MIX($_SESSION['REGISTER_CONFIRM']) != $Param['code']) MessageSend(1, 'Активация не возможна.');
		CheckRegInfo($Exp[0], $Exp[3]);
		$Exp = explode(',', $_SESSION['REGISTER_INFO']);
		mysqli_query($CONNECT, "INSERT INTO `users`  VALUES ('', '$Exp[0]', '$Exp[1]', '$Exp[2]', NOW(), 0, 0, 0)");
		unset($_SESSION['REGISTER_INFO']);
		unset($_SESSION['REGISTER_CONFIRM']);
		MessageSend(3, 'Аккаунт подтвержден.', '/login');
	}
	
	//Вход на сайт - SECURITY FIX: bcrypt verification
	else if ($Module == 'login' and $_POST['submit']) {
		$_POST['email'] = FormChars($_POST['email'], 1);
		$plainPassword = FormChars($_POST['password']);
		if (!$_POST['email'] or !$plainPassword) MessageSend(1, 'Невозможно обработать форму.');
		$Row = mysqli_fetch_assoc(mysqli_query($CONNECT, "SELECT `id`, `regdate`, `email`, `login`, `password`, `avatar`, `town`, `group` FROM `users` WHERE `email` = '$_POST[email]'"));
		if (!$Row) MessageSend(1, 'Не верный email или пароль.');

		// SECURITY: Use proper password verification
		$storedHash = $Row['password'];
		$verified = false;
		$newHash = null;

		if (isMD5Hash($storedHash)) {
			// Legacy MD5 migration
			$newHash = migrateFromMD5($plainPassword, $storedHash);
			$verified = ($newHash !== false);
		} else {
			// Modern bcrypt verification
			$verified = SecurityUtils::verifyPassword($plainPassword, $storedHash);
		}

		if (!$verified) MessageSend(1, 'Не верный email или пароль.');

		// Migrate MD5 hash to bcrypt if needed
		if ($newHash) {
			mysqli_query($CONNECT, "UPDATE `users` SET `password` = '$newHash' WHERE `id` = " . intval($Row['id']));
			$Row['password'] = $newHash;
		}

		$_SESSION['USER_LOGIN_IN'] = 1;
		foreach ($Row as $Key => $Value) $_SESSION['USER_'.strtoupper($Key)] = $Value;
		if ($_REQUEST['remember']) {
			// SECURITY: Use secure token for remember-me instead of password hash
			$rememberToken = SecurityUtils::generateSecureToken(32);
			setcookie('user', $rememberToken, strtotime('+10 days'), '/', '', true, true);
			mysqli_query($CONNECT, "UPDATE `users` SET `remember_token` = '$rememberToken' WHERE `id` = " . intval($Row['id']));
		}
		SecurityUtils::regenerateSessionID(); // Prevent session fixation
		Location('/profile');
	}

?>