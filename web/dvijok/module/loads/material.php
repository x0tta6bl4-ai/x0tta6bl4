<?php
	$Param['id'] += 0;
	if ($Param['id'] == 0) MessageSend(1, 'URL адрес указан неверно.', '/loads');
	$Row = mysqli_fetch_assoc(mysqli_query($CONNECT, 'SELECT `name`, `added`, `date`, `read`, `text`, `active`, `download`, `dimg`, `dfile`, `rate`, `rateusers` FROM `loads` WHERE `id` = '.$Param['id']));
	if (!$Row['name']) MessageSend(1, 'Такой новости не существует.', '/loads');
	if (!$Row['active'] and $_SESSION['USER_GROUP'] != 2) MessageSend(1, 'Новость ожидает модерации.', '/loads');
	mysqli_query($CONNECT, 'UPDATE `loads` SET `read` = `read` + 1 WHERE `id` = '.$Param['id']);
	Head($Row['name']);
?>
<body>
	<div class="container">
		<?php
			include ('include/header.php');
			include ('include/menu.php');
		?>
		<div class="content-wrap">
			<div class="content">
			<?php
				MessageShow();
			?>
				<div class="page">
					<?php
						if (!$Row['active']) $Active = '| <a href="/loads/control/id/'.$Param['id'].'/command/active" class="lol">Активировать новость</a>';
						if ($_SESSION['USER_GROUP'] == 2) $EDIT = '| <a href="/loads/edit/id/'.$Param['id'].'" class="lol">Редактировать новость</a> | <a href="/loads/control/id/'.$Param['id'].'/command/delete" class="lol">Удалить новость</a>'.$Active;
						echo '<a href="'.$Download.'" class="lol">Скачать</a> | Просомтров: '.($Row['read'] + 1).' | Скачивания: '.$Row['download'].' | Добавил: '.$Row['added'].' | Оценок: '.$Row['rate'].' | Дата: '.$Row['date'].' '.$EDIT.'<br><br><a href="/rate/loads/id/'.$Param['id'].'" class="button">Мне нравится</a><br><br><b>'.$Row['name'].'</b><br><img src="/catalog/img/'.$Row['dimg'].'/'.$Param['id'].'.jpg" alt="'.$Row['name'].'" width="50%" height="50%"><br>'.$Row['text'];
						Comments();
					?>
				</div>
			</div>
		</div>
	</div>
</body>
</html>