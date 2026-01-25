<?php
	ULogin(1);
	$Param['id'] += 0;
	if (!$Param['id']) MessageSend(1, 'Не указан ID объекта', '/object/myproperty');
	$Row = mysqli_fetch_assoc(mysqli_query($CONNECT, "SELECT * FROM `$Page` WHERE `id` = $Param[id]"));
	$Table = $Row['type'];
	if ($_POST['submit']) { 
		if ($_POST['shower'] != $Row['shower']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `shower` = '$_POST[shower]' WHERE `id` = $Param[id]");
		}
		if ($_POST['shower_cabin'] != $Row['shower_cabin']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `shower_cabin` = '$_POST[shower_cabin]' WHERE `id` = $Param[id]");
		}
		if ($_POST['bath'] != $Row['bath']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `bath` = '$_POST[bath]' WHERE `id` = $Param[id]");
		}
		if ($_POST['jacuzzi'] != $Row['jacuzzi']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `jacuzzi` = '$_POST[jacuzzi]' WHERE `id` = $Param[id]");
		}
		if ($_POST['toiletry'] != $Row['toiletry']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `toiletry` = '$_POST[toiletry]' WHERE `id` = $Param[id]");
		}
		if ($_POST['towels'] != $Row['towels']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `towels` = '$_POST[towels]' WHERE `id` = $Param[id]");
		}
		if ($_POST['bathrobe'] != $Row['bathrobe']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `bathrobe` = '$_POST[bathrobe]' WHERE `id` = $Param[id]");
		}
		if ($_POST['hairdryer'] != $Row['hairdryer']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `hairdryer` = '$_POST[hairdryer]' WHERE `id` = $Param[id]");
		}
		if ($_POST['hot_water'] != $Row['hot_water']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `hot_water` = '$_POST[hot_water]' WHERE `id` = $Param[id]");
		}
		if ($_POST['summer_shower'] != $Row['summer_shower']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `summer_shower` = '$_POST[summer_shower]' WHERE `id` = $Param[id]");
		}
		if ($_POST['washer'] != $Row['washer']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `washer` = '$_POST[washer]' WHERE `id` = $Param[id]");
		}
		if ($_POST['clothes_dryer'] != $Row['clothes_dryer']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `clothes_dryer` = '$_POST[clothes_dryer]' WHERE `id` = $Param[id]");
		}
		if ($_POST['warm_floor'] != $Row['warm_floor']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `warm_floor` = '$_POST[warm_floor]' WHERE `id` = $Param[id]");
		}
		if ($_POST['no_toilet'] != $Row['no_toilet']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `no_toilet` = '$_POST[no_toilet]' WHERE `id` = $Param[id]");
		}
		MessageSend(2, 'Информация сохранена.', '/'.$Row['type'].'/features/id/'.$Param['id']);
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
							<form  method="POST" action="/'.$Row['type'].'/bathroom/id/'.$Param['id'].'" class="ac-custom ac-checkbox ac-boxfill" autocomplete="off">
								<h3>Основные удобства</h3>
								<div class="checkbox_block">
									<ul>
										<li><input id="hot_water" name="hot_water" value="1" type="checkbox"  ';
										if ($Row['hot_water'] == 1) echo 'checked';
										echo ' 
										><label for="hot_water">Горячая вода</label></li>
										<li><input id="shower" name="shower" value="1" type="checkbox" ';
										if ($Row['shower'] == 1) echo 'checked';
										echo ' 
										><label for="shower">Душ</label></li>
										<li><input id="jacuzzi" name="jacuzzi" value="1" type="checkbox" ';
										if ($Row['jacuzzi'] == 1) echo 'checked';
										echo ' 
										><label for="jacuzzi">Джакузи</label></li>
										<li><input id="towels" name="towels" value="1" type="checkbox" ';
										if ($Row['towels'] == 1) echo 'checked';
										echo ' 
										><label for="towels">Полотенца</label></li>
										<li><input id="washer" name="washer" value="1" type="checkbox" ';
										if ($Row['washer'] == 1) echo 'checked';
										echo ' 
										><label for="washer">Стиральная машина</label></li>
										<li><input id="toiletry" name="toiletry" value="1" type="checkbox" ';
										if ($Row['toiletry'] == 1) echo 'checked';
										echo ' 
										><label for="toiletry">Туалетные принадлежности</label></li>
										<li><input id="warm_floor" name="warm_floor" value="1" type="checkbox" ';
										if ($Row['warm_floor'] == 1) echo 'checked';
										echo ' 
										><label for="warm_floor">Теплые полы</label></li>
										
									</ul>
								</div>
								<div class="checkbox_block">
									<ul> 
										<li><input id="bath" name="bath" value="1" type="checkbox" ';
										if ($Row['bath'] == 1) echo 'checked';
										echo ' 
										><label for="bath">Ванна</label></li>
										<li><input id="shower_cabin" name="shower_cabin" value="1" type="checkbox" ';
										if ($Row['shower_cabin'] == 1) echo 'checked';
										echo ' 
										><label for="shower_cabin">Душевая кабина</label></li>
										<li><input id="summer_shower" name="summer_shower" value="1" type="checkbox" ';
										if ($Row['summer_shower'] == 1) echo 'checked';
										echo ' 
										><label for="summer_shower">Летний душ</label></li>
										<li><input id="bathrobe" name="bathrobe" value="1" type="checkbox" ';
										if ($Row['bathrobe'] == 1) echo 'checked';
										echo ' 
										><label for="bathrobe">Халаты</label></li>
										<li><input id="hairdryer" name="hairdryer" value="1" type="checkbox" ';
										if ($Row['hairdryer'] == 1) echo 'checked';
										echo ' 
										><label for="hairdryer">Фен</label></li>
										<li><input id="clothes_dryer" name="clothes_dryer" value="1" type="checkbox" ';
										if ($Row['clothes_dryer'] == 1) echo 'checked';
										echo ' 
										><label for="clothes_dryer">Сушилка для белья</label></li>
										<li><input id="no_toilet" name="no_toilet" value="1" type="checkbox" ';
										if ($Row['no_toilet'] == 1) echo 'checked';
										echo ' 
										><label for="no_toilet">Туалет за пределом</label></li>
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