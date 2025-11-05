<?php
	ULogin(1);
	$Param['id'] += 0;
	if (!$Param['id']) MessageSend(1, 'Не указан ID объекта', '/object/myproperty');
	$Row = mysqli_fetch_assoc(mysqli_query($CONNECT, "SELECT * FROM `$Page` WHERE `id` = $Param[id]"));
	$Table = $Row['type'];
	if ($_POST['submit']) { 
		if ($_POST['electric_kettle'] != $Row['electric_kettle']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `electric_kettle` = '$_POST[electric_kettle]' WHERE `id` = $Param[id]");
		}
		if ($_POST['coffee_machine'] != $Row['coffee_machine']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `coffee_machine` = '$_POST[coffee_machine]' WHERE `id` = $Param[id]");
		}
		if ($_POST['electric_stove'] != $Row['electric_stove']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `electric_stove` = '$_POST[electric_stove]' WHERE `id` = $Param[id]");
		}
		if ($_POST['fridge'] != $Row['fridge']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `fridge` = '$_POST[fridge]' WHERE `id` = $Param[id]");
		}
		if ($_POST['microwave'] != $Row['microwave']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `microwave` = '$_POST[microwave]' WHERE `id` = $Param[id]");
		}
		if ($_POST['oven_cupboard'] != $Row['oven_cupboard']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `oven_cupboard` = '$_POST[oven_cupboard]' WHERE `id` = $Param[id]");
		}
		if ($_POST['filter'] != $Row['filter']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `filter` = '$_POST[filter]' WHERE `id` = $Param[id]");
		}
		if ($_POST['gas_stove'] != $Row['gas_stove']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `gas_stove` = '$_POST[gas_stove]' WHERE `id` = $Param[id]");
		}
		if ($_POST['dishwasher'] != $Row['dishwasher']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `dishwasher` = '$_POST[dishwasher]' WHERE `id` = $Param[id]");
		}
		if ($_POST['dishes'] != $Row['dishes']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `dishes` = '$_POST[dishes]' WHERE `id` = $Param[id]");
		}
		MessageSend(2, 'Информация сохранена.', '/'.$Row['type'].'/bathroom/id/'.$Param['id']);
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
							<form  method="POST" action="/'.$Row['type'].'/kitchen/id/'.$Param['id'].'" class="ac-custom ac-checkbox ac-boxfill" autocomplete="off">
								<h3>Основные удобства</h3>
								<div class="checkbox_block">
									<ul>
										<li><input id="gas_stove" name="gas_stove" value="1" type="checkbox"  ';
										if ($Row['gas_stove'] == 1) echo 'checked';
										echo ' 
										><label for="gas_stove">Газовая плита</label></li>
										<li><input id="microwave" name="microwave" value="1" type="checkbox" ';
										if ($Row['microwave'] == 1) echo 'checked';
										echo ' 
										><label for="microwave">Микроволновая печь</label></li>
										<li><input id="electric_kettle" name="electric_kettle" value="1" type="checkbox" ';
										if ($Row['electric_kettle'] == 1) echo 'checked';
										echo ' 
										><label for="electric_kettle">Электрочайник</label></li>
										<li><input id="fridge" name="fridge" value="1" type="checkbox" ';
										if ($Row['fridge'] == 1) echo 'checked';
										echo ' 
										><label for="fridge">Холодильник</label></li>
										<li><input id="dishes" name="dishes" value="1" type="checkbox" ';
										if ($Row['dishes'] == 1) echo 'checked';
										echo ' 
										><label for="dishes">Посуда</label></li>
									</ul>
								</div>
								<div class="checkbox_block">
									<ul> 
										<li><input id="electric_stove" name="electric_stove" value="1" type="checkbox" ';
										if ($Row['electric_stove'] == 1) echo 'checked';
										echo ' 
										><label for="electric_stove">Электрическая плита</label></li>
										<li><input id="oven_cupboard" name="oven_cupboard" value="1" type="checkbox" ';
										if ($Row['oven_cupboard'] == 1) echo 'checked';
										echo ' 
										><label for="oven_cupboard">Духовой шкаф</label></li>
										<li><input id="coffee_machine" name="coffee_machine" value="1" type="checkbox" ';
										if ($Row['coffee_machine'] == 1) echo 'checked';
										echo ' 
										><label for="coffee_machine">Кофеварка</label></li>
										<li><input id="dishwasher" name="dishwasher" value="1" type="checkbox" ';
										if ($Row['dishwasher'] == 1) echo 'checked';
										echo ' 
										><label for="dishwasher">Посудомоечная машина</label></li>
										<li><input id="filter" name="filter" value="1" type="checkbox" ';
										if ($Row['filter'] == 1) echo 'checked';
										echo ' 
										><label for="filter">Фильтр для воды</label></li>
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