<?php
	ULOgin(1);
	Head('Личный кабинет');
?>
</head>
<body>
	<div class="container">
		<script src="/resource/js/notificationFx.js"></script>
		<?php
			MessageShow();
			include ('include/header.php');
			include ('include/menu.php');
		?>
		<div class="content-wrap">
			<div class="content">
				<div class="page">
					<?php
						if ($_SESSION['USER_AVATAR'] == 0) $Avatar = 0;
						else $Avatar = $_SESSION['USER_AVATAR'].'/'.$_SESSION['USER_ID'];
						echo '
						<img = src="/resource/avatar/'.$Avatar.'.jpg" width="200" height="200" alt="Аватар">
						<br> Группа ('.UserGroup($_SESSION['USER_GROUP']).')
						<br> ID пользователя '.$_SESSION['USER_ID'].'
						<br> Дата регистрации '.$_SESSION['USER_REGDATE'].'
						<br> Email '.$_SESSION['USER_EMAIL'].'
						<br> Имя '.$_SESSION['USER_LOGIN'].'
						<br> Город '.$_SESSION['USER_TOWN'].'
						<br> Аватар '.$_SESSION['USER_AVATAR'].'
						<br> Вход '.$_SESSION['USER_LOGIN_IN'].'
						';
					?>
				</div>
			</div>
		</div>
	</div>
</body>
</html>