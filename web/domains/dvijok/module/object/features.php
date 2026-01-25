<?php
	ULogin(1);
	$Param['id'] += 0;
	if (!$Param['id']) MessageSend(1, 'Не указан ID объекта', '/object/myproperty');
	$Row = mysqli_fetch_assoc(mysqli_query($CONNECT, "SELECT * FROM `$Page` WHERE `id` = $Param[id]"));
	$Table = $Row['type'];
	if ($_POST['submit']) { 
		if ($_POST['company'] != $Row['company']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `company` = '$_POST[company]' WHERE `id` = $Param[id]");
		}
		if ($_POST['breakfast'] != $Row['breakfast']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `breakfast` = '$_POST[breakfast]' WHERE `id` = $Param[id]");
		}
		if ($_POST['holiday'] != $Row['holiday']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `holiday` = '$_POST[holiday]' WHERE `id` = $Param[id]");
		}
		if ($_POST['here_pets'] != $Row['here_pets']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `here_pets` = '$_POST[here_pets]' WHERE `id` = $Param[id]");
		}
		if ($_POST['invalid'] != $Row['invalid']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `invalid` = '$_POST[invalid]' WHERE `id` = $Param[id]");
		}
		if ($_POST['family'] != $Row['family']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `family` = '$_POST[family]' WHERE `id` = $Param[id]");
		}
		if ($_POST['with_pets'] != $Row['with_pets']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `with_pets` = '$_POST[with_pets]' WHERE `id` = $Param[id]");
		}
		if ($_POST['smoke'] != $Row['smoke']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `smoke` = '$_POST[smoke]' WHERE `id` = $Param[id]");
		}
		MessageSend(2, 'Информация сохранена.', '/'.$Row['type'].'/photo/id/'.$Param['id']);
	}
	Head('Редактировать объект');
?>
<link rel="stylesheet" type="text/css" href="/resource/css/checkbox.css" />
<link rel="stylesheet" type="text/css" href="/resource/css/inputs.css" />
</head>
<body>
	<div class="container">
		<script src="/resource/js/notificationFx.js"></script>
		<?php
			MessageShow();
			include ('include/header.php');
			include ('include/menu_object.php');
		?>
		<div class="menu-wrap">
			<?php
				include ('include/menu.php');
			?>
		</div>
		<div class="content-wrap">
			<div class="content">
				
				<div class="info_box">
					<?php
						echo '
						<section>
							<form  method="POST" action="/'.$Row['type'].'/features/id/'.$Param['id'].'" class="ac-custom ac-checkbox ac-boxfill" autocomplete="off">
								<h3>Основные удобства</h3>
								<div class="checkbox_block">
									<ul>
										<li><input id="family" name="family" value="1" type="checkbox"  ';
										if ($Row['family'] == 1) echo 'checked';
										echo ' 
										><label for="family">Подходит семьям с детьми</label></li>
										<li><input id="company" name="company" value="1" type="checkbox" ';
										if ($Row['company'] == 1) echo 'checked';
										echo ' 
										><label for="company">Подходит для больших компаний</label></li>
										<li><input id="with_pets" name="with_pets" value="1" type="checkbox" ';
										if ($Row['with_pets'] == 1) echo 'checked';
										echo ' 
										><label for="with_pets">Можно с домашними животными</label></li>
										<li><input id="here_pets" name="here_pets" value="1" type="checkbox" ';
										if ($Row['here_pets'] == 1) echo 'checked';
										echo ' 
										><label for="here_pets">Тут есть животные</label></li>
										<li><input id="smoke" name="smoke" value="1" type="checkbox" ';
										if ($Row['smoke'] == 1) echo 'checked';
										echo ' 
										><label for="smoke">Можно курить в помещении</label></li>
										<li><input id="holiday" name="holiday" value="1" type="checkbox" ';
										if ($Row['holiday'] == 1) echo 'checked';
										echo ' 
										><label for="holiday">Разрешено проведение мероприятий</label></li>
										<li><input id="breakfast" name="breakfast" value="1" type="checkbox" ';
										if ($Row['breakfast'] == 1) echo 'checked';
										echo ' 
										><label for="breakfast">В стоимость входит завтрак</label></li>
										<li><input id="invalid" name="invalid" value="1" type="checkbox" ';
										if ($Row['invalid'] == 1) echo 'checked';
										echo ' 
										><label for="invalid">Подходит для людей с ограниченными возможностями</label></li>
										
									</ul>
								</div>
								<div class="box bg-3">
									<button type="submit" value="save" name="submit" class="button button--nuka">Далее</button>
								</div>
							</form>
						</section>
						';
					?>
					
				</div>
			</div>
			<script src="/resource/js/svgcheckbx.js"></script>
		</div>
	</div>
</body>
</html>