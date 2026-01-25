<?php
	ULogin(1);
	if($_POST['submit'] and $_POST['text']) {
		$_POST['text'] = FormChars($_POST['text']);
		mysqli_query($CONNECT, "INSERT INTO `chat`  VALUES ('', '$_POST[text]', '$_SESSION[USER_LOGIN]', NOW())");
		exit(header('location: /chat'));
	}
	Head('Чат');
?>
<link rel="stylesheet" type="text/css" href="/resource/css/form.css" />
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
					<div class="ChatBox">
					<?php
						$Query = mysqli_query($CONNECT, 'SELECT * FROM `chat` ORDER By `time` DESC LIMIT 50');
						while ($Row = mysqli_fetch_assoc($Query)) echo '<div class="ChatBlock"><span>'.$Row['user'].' | '.$Row['time'].'</span>'.$Row['message'].'</div>';
					?>
					</div>
					<form method="POST" action="/chat" >
						<textarea class="ChatMessage" name="text" ></textarea>
						<p><button class="btn btn-large btn-primary" type="submit" value="upload" name="submit">Отправить</button></p>
					</form>
				</div>
			</div>
		</div>
	</div>
</body>
</html>