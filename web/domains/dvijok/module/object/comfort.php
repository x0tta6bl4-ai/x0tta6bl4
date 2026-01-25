<?php
	ULogin(1);
	$Param['id'] += 0;
	if (!$Param['id']) MessageSend(1, 'Не указан ID объекта', '/object/myproperty');
	$Row = mysqli_fetch_assoc(mysqli_query($CONNECT, "SELECT * FROM `$Page` WHERE `id` = $Param[id]"));
	$Table = $Row['type'];
	if ($_POST['submit']) { 
		if ($_POST['wifi'] != $Row['wifi']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `wifi` = '$_POST[wifi]' WHERE `id` = $Param[id]");
		}
		if ($_POST['internet'] != $Row['internet']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `internet` = '$_POST[internet]' WHERE `id` = $Param[id]");
		}
		if ($_POST['safe'] != $Row['safe']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `safe` = '$_POST[safe]' WHERE `id` = $Param[id]");
		}
		if ($_POST['parking'] != $Row['parking']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `parking` = '$_POST[parking]' WHERE `id` = $Param[id]");
		}
		if ($_POST['condition'] != $Row['condition']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `condition` = '$_POST[condition]' WHERE `id` = $Param[id]");
		}
		if ($_POST['heating'] != $Row['heating']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `heating` = '$_POST[heating]' WHERE `id` = $Param[id]");
		}
		if ($_POST['mosquito'] != $Row['mosquito']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `mosquito` = '$_POST[mosquito]' WHERE `id` = $Param[id]");
		}
		if ($_POST['intercom'] != $Row['intercom']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `intercom` = '$_POST[intercom]' WHERE `id` = $Param[id]");
		}
		if ($_POST['balcony'] != $Row['balcony']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `balcony` = '$_POST[balcony]' WHERE `id` = $Param[id]");
		}
		if ($_POST['yard'] != $Row['yard']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `yard` = '$_POST[yard]' WHERE `id` = $Param[id]");
		}
		if ($_POST['barbecue'] != $Row['barbecue']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `barbecue` = '$_POST[barbecue]' WHERE `id` = $Param[id]");
		}
		if ($_POST['pool'] != $Row['pool']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `pool` = '$_POST[pool]' WHERE `id` = $Param[id]");
		}
		if ($_POST['fireplace'] != $Row['fireplace']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `fireplace` = '$_POST[fireplace]' WHERE `id` = $Param[id]");
		}
		if ($_POST['sauna'] != $Row['sauna']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `sauna` = '$_POST[sauna]' WHERE `id` = $Param[id]");
		}
		if ($_POST['television_set'] != $Row['television_set']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `television_set` = '$_POST[television_set]' WHERE `id` = $Param[id]");
		}
		if ($_POST['satellite_tv'] != $Row['satellite_tv']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `satellite_tv` = '$_POST[satellite_tv]' WHERE `id` = $Param[id]");
		}
		if ($_POST['blower'] != $Row['blower']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `blower` = '$_POST[blower]' WHERE `id` = $Param[id]");
		}
		if ($_POST['iron'] != $Row['iron']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `iron` = '$_POST[iron]' WHERE `id` = $Param[id]");
		}
		if ($_POST['lcd_tv'] != $Row['lcd_tv']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `lcd_tv` = '$_POST[lcd_tv]' WHERE `id` = $Param[id]");
		}
		if ($_POST['cable_tv'] != $Row['cable_tv']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `cable_tv` = '$_POST[cable_tv]' WHERE `id` = $Param[id]");
		}
		if ($_POST['mobile_heater'] != $Row['mobile_heater']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `mobile_heater` = '$_POST[mobile_heater]' WHERE `id` = $Param[id]");
		}
		if ($_POST['iron_board'] != $Row['iron_board']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `iron_board` = '$_POST[iron_board]' WHERE `id` = $Param[id]");
		}
		MessageSend(2, 'Информация сохранена.', '/'.$Row['type'].'/kitchen/id/'.$Param['id']);
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
							<form  method="POST" action="/'.$Row['type'].'/comfort/id/'.$Param['id'].'" class="ac-custom ac-checkbox ac-boxfill" autocomplete="off">
								<div class="checkbox_block">
									<ul>
										<li><input id="wifi" name="wifi" value="1" type="checkbox" ';
										if ($Row['wifi'] == 1) echo 'checked';
										echo ' 
										><label for="wifi">Wi-Fi</label></li>
										<li><input id="television_set" name="television_set" value="1" type="checkbox" ';
										if ($Row['television_set'] == 1) echo 'checked';
										echo ' 
										><label for="television_set">Телевизор</label></li>
										<li><input id="satellite_tv" name="satellite_tv" value="1" type="checkbox" ';
										if ($Row['satellite_tv'] == 1) echo 'checked';
										echo ' 
										><label for="satellite_tv">Спутниковое ТВ</label></li>
										<li><input id="condition" name="condition" value="1" type="checkbox" ';
										if ($Row['condition'] == 1) echo 'checked';
										echo ' 
										><label for="condition">Кондиционер</label></li>
										<li><input id="blower" name="blower" value="1" type="checkbox" ';
										if ($Row['blower'] == 1) echo 'checked';
										echo ' 
										><label for="blower">Вентилятор</label></li>
										<li><input id="safe" name="safe" value="1" type="checkbox" ';
										if ($Row['safe'] == 1) echo 'checked';
										echo ' 
										><label for="safe">Сейф</label></li>
										<li><input id="iron" name="iron" value="1" type="checkbox" ';
										if ($Row['iron'] == 1) echo 'checked';
										echo ' 
										><label for="iron">Утюг</label></li>
										<li><input id="parking" name="parking" value="1" type="checkbox" ';
										if ($Row['parking'] == 1) echo 'checked';
										echo ' 
										><label for="parking">Парковка</label></li>
										<li><input id="mosquito" name="mosquito" value="1" type="checkbox" ';
										if ($Row['mosquito'] == 1) echo 'checked';
										echo ' 
										><label for="mosquito">Москитные сетки</label></li>
										<li><input id="fireplace" name="fireplace" value="1" type="checkbox" ';
										if ($Row['fireplace'] == 1) echo 'checked';
										echo ' 
										><label for="fireplace">Камин</label></li>
										<li><input id="sauna" name="sauna" value="1" type="checkbox" ';
										if ($Row['sauna'] == 1) echo 'checked';
										echo ' 
										><label for="sauna">Баня/сауна</label></li>
										
									</ul>
								</div>
								<div class="checkbox_block">
									<ul>
										<li><input id="internet" name="internet" value="1" type="checkbox" ';
										if ($Row['internet'] == 1) echo 'checked';
										echo ' 
										><label for="internet">Проводной интернет</label></li> 
										<li><input id="lcd_tv" name="lcd_tv" value="1" type="checkbox" ';
										if ($Row['lcd_tv'] == 1) echo 'checked';
										echo ' 
										><label for="lcd_tv">ЖК-телевизор</label></li>
										<li><input id="cable_tv" name="cable_tv" value="1" type="checkbox" ';
										if ($Row['cable_tv'] == 1) echo 'checked';
										echo ' 
										><label for="cable_tv">Кабельное ТВ</label></li>
										<li><input id="heating" name="heating" value="1" type="checkbox" ';
										if ($Row['heating'] == 1) echo 'checked';
										echo ' 
										><label for="heating">Отопление</label></li>
										<li><input id="mobile_heater" name="mobile_heater" value="1" type="checkbox" ';
										if ($Row['mobile_heater'] == 1) echo 'checked';
										echo ' 
										><label for="mobile_heater">Обогреватель</label></li>
										<li><input id="intercom" name="intercom" value="1" type="checkbox" ';
										if ($Row['intercom'] == 1) echo 'checked';
										echo ' 
										><label for="intercom">Домофон</label></li>
										<li><input id="iron_board" name="iron_board" value="1" type="checkbox" ';
										if ($Row['iron_board'] == 1) echo 'checked';
										echo ' 
										><label for="iron_board">Гладильная доска</label></li>
										<li><input id="balcony" name="balcony" value="1" type="checkbox"  ';
										if ($Row['balcony'] == 1) echo 'checked';
										echo ' 
										><label for="balcony">Балкон</label></li>
										<li><input id="yard" name="yard" value="1" type="checkbox" ';
										if ($Row['yard'] == 1) echo 'checked';
										echo ' 
										><label for="yard">Выгороженный двор</label></li>
										<li><input id="barbecue" name="barbecue" value="1" type="checkbox" ';
										if ($Row['barbecue'] == 1) echo 'checked';
										echo ' 
										><label for="barbecue">Мангал/барбекю</label></li>
										<li><input id="pool" name="pool" value="1" type="checkbox" ';
										if ($Row['pool'] == 1) echo 'checked';
										echo ' 
										><label for="pool">Бассейн</label></li>
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