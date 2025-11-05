<?php
	if ($Module) {
		$Module = FormChars($Module);
		$Info = mysqli_fetch_assoc(mysqli_query($CONNECT, "SELECT `id`, `login`, `email`, `regdate`, `avatar` FROM `users` WHERE `email` = '$Module'"));
		if (!$Info['id']) MessageSend(1, 'Пользователь не найден.', '/user');
		if (!$Info['avatar']) $Avatar = 0;
		else $Avatar = "$Info[avatar]/$Info[id]";
		$Draw = '
		<img src="/resource/avatar/'.$Avatar.'.jpg" width="120" height="120" alt="Аватар" align="left">
		<div class="Block">
		ID '.$Info['id'].' ('.UserGroup($Info['group']).')
		<br>Имя '.$Info['login'].'
		<br>E-mail '.$Info['email'].'
		<br>Дата регистрации '.$Info['regdate'].'
		</div>
		<a href="/" class="button ProfileB">Написать</a><br><br>
		<div class="ProfileEdit">
		</div>';
		} 
		else {
			$Query = mysqli_query($CONNECT, 'SELECT `login`, `email` FROM `users` ORDER BY `id` DESC LIMIT 10');
			while ($Row = mysqli_fetch_assoc($Query)) $Draw .= "<a href='/user/$Row[email]'><br>Логин: $Row[login] ( имя: $Row[email] )</a>";
		}

	ULOgin(1);
	Head('Пользователи');
?>
</head>
<body>
	<div class="container">
		<?php
			include ('include/header.php');
			include ('include/menu.php');
		?>
		<div class="content-wrap">
			<div class="content">
				<div class="page">
					<?php echo $Draw ?>
				</div>
			</div>
		</div>
	</div>
</body>
</html>