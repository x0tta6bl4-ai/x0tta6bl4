<?php
	ULOgin(1);
	if ($Module == 'delete' and $Param['id']) {
		$Param['id'] += 0;
		$Row = mysqli_fetch_assoc(mysqli_query($CONNECT, "SELECT `uid` FROM `notice` WHERE `id` = $Param[id]"));
		if (!$Row['uid']) MessageSend(1, 'Уведомление не найдено.', '/notice');
		else if ($Row['uid'] != $_SESSION['USER_ID']) MessageSend(1, 'Доступ запрещен.', '/notice');
		mysqli_query($CONNECT, "DELETE FROM `notice` WHERE `id` = $Param[id]");
		MessageSend(1, 'Уведомление удалено.', '/notice');
	}
	Head('Уведомления');
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
					<?php
						MessageShow();
						$Count = mysqli_fetch_row(mysqli_query($CONNECT, "SELECT COUNT(`id`) FROM `notice` WHERE `uid` = $_SESSION[USER_ID]"));
						if (!$Module) {
							$Module = 1;
							$Result = mysqli_query($CONNECT, "SELECT `id`, `status`, `date`, `text` FROM `notice` WHERE `uid` = $_SESSION[USER_ID] ORDER BY `id` DESC LIMIT 0, 5");
						}
						else {
							$Start = ($Module - 1) * 5;
							$Result = mysqli_query($CONNECT, str_replace('START', $Start, "SELECT `id`, `status`, `date`, `text` FROM `notice` WHERE `uid` = $_SESSION[USER_ID] ORDER BY `id` DESC LIMIT START, 5"));
						}
						PageSelector('/notice/', $Module, $Count);
						while ($Row = mysqli_fetch_assoc($Result)) {
							if ($Row['status']) $Status = 'Прочитано';
							else $Status = 'Не прочитано';
							echo '<a href="/notice/delete/id/'.$Row['id'].'"><div class="ChatBlock"><span>'.$Status.' | '.$Row['date'].'</span>'.$Row['text'].'</div></a>';
						}
						mysqli_query($CONNECT, "UPDATE `notice` SET `status` = 1 WHERE `uid` = $_SESSION[USER_ID] AND `status` = 0");

						//SendNotice('Данил', 'Привет еще раз');
					?>
				</div>
			</div>
		</div>
	</div>
</body>
</html>