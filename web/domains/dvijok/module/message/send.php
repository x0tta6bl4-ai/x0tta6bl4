<?php
	ULogin(1);
	if ($_POST['submit'] and $_POST['text'] and $_POST['login']) {
		SendMessage($_POST['login'], $_POST['text']);
		MessageSend(3, 'Сообщение отправлено');
	}
	Head('Отправить сообщение');
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
				<a href="/message/dialog" class="lol">МОИ ДИАЛОГИ</a><br><br>
				<form method="POST" action="/message/send">
					<input type="text" name="login" placeholder="Логин получателя" required>
					<br><textarea class="ChatMessage" name="text" placeholder="Текст сообщения" required></textarea>
					<br><input type="submit" name="submit" value="Отправить">
				</form>
			</div>
		</div>
	</div>
</body>
</html>