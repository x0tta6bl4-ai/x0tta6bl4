<?php
	ULogin(1);
	$Param['id'] += 0;
	if (!$Param['id']) MessageSend(1, 'Не указан ID объекта', '/object/myproperty');
	$Row = mysqli_fetch_assoc(mysqli_query($CONNECT, "SELECT * FROM `$Page` WHERE `id` = $Param[id]"));
	$Table = $Row['type'];
	if ($_POST['submit']) {
		if ($_POST['double_beds'] != $Row['double_beds']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `double_beds` = '$_POST[double_beds]' WHERE `id` = $Param[id]");
		}
		if ($_POST['single_beds'] != $Row['single_beds']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `single_beds` = '$_POST[single_beds]' WHERE `id` = $Param[id]");
		}
		if ($_POST['double_sofa'] != $Row['double_sofa']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `double_sofa` = '$_POST[double_sofa]' WHERE `id` = $Param[id]");
		}
		if ($_POST['single_sofa'] != $Row['single_sofa']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `single_sofa` = '$_POST[single_sofa]' WHERE `id` = $Param[id]");
		}
		if ($_POST['bunk_bed'] != $Row['bunk_bed']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `bunk_bed` = '$_POST[bunk_bed]' WHERE `id` = $Param[id]");
		}
		if ($_POST['baby_bed'] != $Row['baby_bed']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `baby_bed` = '$_POST[baby_bed]' WHERE `id` = $Param[id]");
		}
		if ($_POST['armchair'] != $Row['armchair']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `armchair` = '$_POST[armchair]' WHERE `id` = $Param[id]");
		}
		if ($_POST['cot'] != $Row['cot']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `cot` = '$_POST[cot]' WHERE `id` = $Param[id]");
		}
		if ($_POST['air_mattress'] != $Row['air_mattress']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `air_mattress` = '$_POST[air_mattress]' WHERE `id` = $Param[id]");
		}
		if ($_POST['linens'] != $Row['linens']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `linens` = '$_POST[linens]' WHERE `id` = $Param[id]");
		}
		MessageSend(2, 'Информация сохранена.', '/'.$Row['type'].'/comfort/id/'.$Param['id']);
	}
	Head('Редактировать объект');
?>
<link rel="stylesheet" type="text/css" href="/resource/css/checkbox.css" />
<link rel="stylesheet" type="text/css" href="/resource/css/inputs.css" />
<link rel="stylesheet" type="text/css" href="/resource/css/cs-select.css" />
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
				<h1 class="basic_title">Укажите количество и вид спальных мест.</h1>
				<div class="info_box">
					<?php
						echo '
						<form method="POST" action="/'.$Row['type'].'/sleeps/id/'.$Param['id'].'" class="ac-custom ac-checkbox ac-boxfill" autocomplete="off">
							<div class="info_box">
								<div data-help="help_double_beds">
									<select class="cs-select cs-skin-elastic" name="double_beds">'.str_replace('value="'.$Row['double_beds'], 'selected value="'.$Row['double_beds'], '
										<option value="0">Количество двуспальных кроватей</option>
										<option value="1">1 двуспальная кровать</option>
										<option value="2">2 двуспальные кровати</option>
										<option value="3">3 двуспальные кровати</option>
										<option value="4">4 двуспальные кровати</option>
										<option value="5">5 двуспальных кроватей</option>
										<option value="6">6 двуспальных кроватей</option>
										<option value="7">7 двуспальных кроватей</option>
										<option value="8">8 двуспальных кроватей</option>
										<option value="9">9 двуспальных кроватей</option>
									').'</select>
								</div>
								<div data-help="help_single_beds">
									<select class="cs-select cs-skin-elastic" name="single_beds">'.str_replace('value="'.$Row['single_beds'], 'selected value="'.$Row['single_beds'], '
										<option value="0">Количество односпальных кроватей</option>
										<option value="1">1 односпальная кровать</option>
										<option value="2">2 односпальные кровати</option>
										<option value="3">3 односпальные кровати</option>
										<option value="4">4 односпальные кровати</option>
										<option value="5">5 односпальных кроватей</option>
										<option value="6">6 односпальных кроватей</option>
										<option value="7">7 односпальных кроватей</option>
										<option value="8">8 односпальных кроватей</option>
										<option value="9">9 односпальных кроватей</option>
									').'</select>
								</div>
								<div data-help="help_double_sofa">
									<select class="cs-select cs-skin-elastic" name="double_sofa">'.str_replace('value="'.$Row['double_sofa'], 'selected value="'.$Row['double_sofa'], '
										<option value="0">Количество двуспальных диванов</option>
										<option value="1">1 двуспальный диван</option>
										<option value="2">2 двуспальных дивана</option>
										<option value="3">3 двуспальных дивана</option>
										<option value="4">4 двуспальных дивана</option>
										<option value="5">5 двуспальных диванов</option>
										<option value="6">6 двуспальных диванов</option>
										<option value="7">7 двуспальных диванов</option>
										<option value="8">8 двуспальных диванов</option>
										<option value="9">9 двуспальных диванов</option>
									').'</select>
								</div>
								<div data-help="help_single_sofa">
									<select class="cs-select cs-skin-elastic" name="single_sofa">'.str_replace('value="'.$Row['single_sofa'], 'selected value="'.$Row['single_sofa'], '
										<option value="0">Количество односпальных диванов</option>
										<option value="1">1 односпальный диван</option>
										<option value="2">2 односпальных дивана</option>
										<option value="3">3 односпальных дивана</option>
										<option value="4">4 односпальных дивана</option>
										<option value="5">5 односпальных диванов</option>
										<option value="6">6 односпальных диванов</option>
										<option value="7">7 односпальных диванов</option>
										<option value="8">8 односпальных диванов</option>
										<option value="9">9 односпальных диванов</option>
									').'</select>
								</div>
								<div data-help="help_bunk_bed">
									<select class="cs-select cs-skin-elastic" name="bunk_bed">'.str_replace('value="'.$Row['bunk_bed'], 'selected value="'.$Row['bunk_bed'], '
										<option value="0">Количество двухъярусных кроватей</option>
										<option value="1">1 двухъярусная кровать</option>
										<option value="2">2 двухъярусные кровати</option>
										<option value="3">3 двухъярусные кровати</option>
										<option value="4">4 двухъярусные кровати</option>
										<option value="5">5 двухъярусных кроватей</option>
										<option value="6">6 двухъярусных кроватей</option>
										<option value="7">7 двухъярусных кроватей</option>
										<option value="8">8 двухъярусных кроватей</option>
										<option value="9">9 двухъярусных кроватей</option>
									').'</select>
								</div>
								<div data-help="help_baby_bed">
									<select class="cs-select cs-skin-elastic" name="baby_bed">'.str_replace('value="'.$Row['baby_bed'], 'selected value="'.$Row['baby_bed'], '
										<option value="0">Количество детских кроваток</option>
										<option value="1">1 детская кроватка</option>
										<option value="2">2 детские кроватки</option>
										<option value="3">3 детские кроватки</option>
										<option value="4">4 детские кроватки</option>
										<option value="5">5 детских кроваток</option>
										<option value="6">6 детских кроваток</option>
										<option value="7">7 детских кроваток</option>
										<option value="8">8 детских кроваток</option>
										<option value="9">9 детских кроваток</option>
									').'</select>
								</div>
								<div data-help="help_armchair">
									<select class="cs-select cs-skin-elastic" name="armchair">'.str_replace('value="'.$Row['armchair'], 'selected value="'.$Row['armchair'], '
										<option value="0">Количество раскладных кресел</option>
										<option value="1">1 раскладное кресло</option>
										<option value="2">2 раскладных кресла</option>
										<option value="3">3 раскладных кресла</option>
										<option value="4">4 раскладных кресла</option>
										<option value="5">5 раскладных кресел</option>
										<option value="6">6 раскладных кресел</option>
										<option value="7">7 раскладных кресел</option>
										<option value="8">8 раскладных кресел</option>
										<option value="9">9 раскладных кресел</option>
									').'</select>
								</div>
								<div data-help="help_cot">
									<select class="cs-select cs-skin-elastic" name="cot">'.str_replace('value="'.$Row['cot'], 'selected value="'.$Row['cot'], '
										<option value="0">Количество раскладушек</option>
										<option value="1">1 раскладушка</option>
										<option value="2">2 раскладушки</option>
										<option value="3">3 раскладушки</option>
										<option value="4">4 раскладушки</option>
										<option value="5">5 раскладушек</option>
										<option value="6">6 раскладушек</option>
										<option value="7">7 раскладушек</option>
										<option value="8">8 раскладушек</option>
										<option value="9">9 раскладушек</option>
									').'</select>
								</div>
								<div data-help="help_air_mattress">
									<select class="cs-select cs-skin-elastic" name="air_mattress">'.str_replace('value="'.$Row['air_mattress'], 'selected value="'.$Row['air_mattress'], '
										<option value="0">Количество надувных матрасов</option>
										<option value="1">1 надувной матрас</option>
										<option value="2">2 надувных матраса</option>
										<option value="3">3 надувных матраса</option>
										<option value="4">4 надувных матраса</option>
										<option value="5">5 надувных матрасов</option>
										<option value="6">6 надувных матрасов</option>
										<option value="7">7 надувных матрасов</option>
										<option value="8">8 надувных матрасов</option>
										<option value="9">9 надувных матрасов</option>
									').'</select>
								</div>
							</div>
							<div class="checkbox_block checkbox_block_sleeps">
								<ul>
									<li><input id="linens" name="linens" value="1" type="checkbox"  ';
									if ($Row['linens'] == 1) echo 'checked';
									echo ' 
									><label for="linens">Постельное белье</label></li>
								</ul>
							</div>
							<div id="help_double_beds" class="help">Укажите количество двуспальных кроватей.</div>
							<div id="help_single_beds" class="help">Укажите количество односпальных кроватей.</div>
							<div id="help_double_sofa" class="help">Укажите количество двуспальных диванов.</div>
							<div id="help_single_sofa" class="help">Укажите количество односпальных диванов.</div>
							<div id="help_bunk_bed" class="help">Укажите количество двухъярусных кроватей.</div>
							<div id="help_baby_bed" class="help">Укажите количество детских кроваток.</div>
							<div id="help_armchair" class="help">Укажите количество раскладных кресел.</div>
							<div id="help_cot" class="help">Укажите количество раскладушек.</div>
							<div id="help_air_mattress" class="help">Укажите количество надувных матрасов.</div>
							<div class="button_box">
								<button type="submit" value="save" name="submit" class="button button--nuka">Далее</button>
							</div>
					</form>
						';
					?>
					
				</div>
			</div>
		</div>
	</div>
	<script src="/resource/js/svgcheckbx.js"></script>
	<script src="/resource/js/classie.js"></script>
	<script src="/resource/js/selectFx.js"></script>
	<script>
		$("body").on("mouseenter", "[data-help]", function () {
			$(".help").removeClass("active");
			$("#"+$(this).data("help")+"").addClass("active");
		});	
	</script>
	<script>
		(function() {
			[].slice.call( document.querySelectorAll( 'select.cs-select' ) ).forEach( function(el) {	
				new SelectFx(el);
			} );
		})();
	</script>
</body>
</html>