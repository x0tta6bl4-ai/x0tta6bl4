<?php
	ULogin(1);
	$Param['id'] += 0;
	if (!$Param['id']) MessageSend(1, 'Не указан ID материала', '/loads');
	$Row = mysqli_fetch_assoc(mysqli_query($CONNECT, "SELECT * FROM `$Page` WHERE `id` = $Param[id]"));
	$Table = $Row['type'];
	if ($_POST['submit']) {
		if ($_POST['area'] != $Row['area']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `area` = '$_POST[area]' WHERE `id` = $Param[id]");
		}
		if ($_POST['number_floor'] != $Row['number_floor']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `number_floor` = '$_POST[number_floor]' WHERE `id` = $Param[id]");
		}
		if ($_POST['floor'] != $Row['floor']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `floor` = '$_POST[floor]' WHERE `id` = $Param[id]");
		}
		if ($_POST['lift'] != $Row['lift']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `lift` = '$_POST[lift]' WHERE `id` = $Param[id]");
		}
		if ($_POST['number_rooms'] != $Row['number_rooms']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `number_rooms` = '$_POST[number_rooms]' WHERE `id` = $Param[id]");
		}
		if ($_POST['number_guests'] != $Row['number_guests']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `number_guests` = '$_POST[number_guests]' WHERE `id` = $Param[id]");
		}
		MessageSend(2, 'Информация сохранена.', '/'.$Row['type'].'/description/id/'.$Param['id']);
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
				<h1 class="basic_title">Заполните все поля для более удобного поиска вашего объекта по фильтрам.</h1>
				<div class="info_box">
					<?php
						echo '
						<form method="POST" action="/'.$Row['type'].'/basic/id/'.$Param['id'].'" class="ac-custom ac-checkbox ac-boxfill" autocomplete="off">
							<div class="select_box">
							<div data-help="select_rooms">
								<select class="cs-select cs-skin-elastic" name="number_rooms">'.str_replace('value="'.$Row['number_rooms'], 'selected value="'.$Row['number_rooms'], '
									<option value="0">Количество комнат</option>
									<option value="1">1 комната</option>
									<option value="2">2 комнаты</option>
									<option value="3">3 комнаты</option>
									<option value="4">4 комнаты</option>
									<option value="5">5 комнат</option>
									<option value="6">6 комнат</option>
									<option value="7">7 комнат</option>
									<option value="8">8 комнат</option>
									<option value="9">9 комнат</option>
									').'</select>
							</div>	
							<div data-help="select_guests">
								<select class="cs-select cs-skin-elastic" name="number_guests">'.str_replace('value="'.$Row['number_guests'], 'selected value="'.$Row['number_guests'], '
									<option value="0">Количество комнат</option>
									<option value="1">1 гость</option>
									<option value="2">2 гостя</option>
									<option value="3">3 гостя</option>
									<option value="4">4 гостя</option>
									<option value="5">5 гостей</option>
									<option value="6">6 гостей</option>
									<option value="7">7 гостей</option>
									<option value="8">8 гостей</option>
									<option value="9">9 и более гостей</option>
									').'</select>
							</div>
							</div>
							<section class="style_input">
								<span data-help="area_help" class="input input--akira">
									<input class="input__field input__field--akira" type="text" name="area" value="'.$Row['area'].'"/>
									<label class="input__label input__label--akira" for="input-1">
										<span class="input__label-content input__label-content--akira">Общая площадь</span>
									</label>
								</span>
								<span data-help="number_floor_help" class="input input--akira">
									<input class="input__field input__field--akira" type="text" name="number_floor" value="'.$Row['number_floor'].'"/>
									<label class="input__label input__label--akira" for="input-2">
										<span class="input__label-content input__label-content--akira">Количество этажей</span>
									</label>
								</span>
								<span data-help="floor_help" class="input input--akira">
									<input class="input__field input__field--akira" type="text" name="floor" value="'.$Row['floor'].'"/>
									<label class="input__label input__label--akira" for="input-3">
										<span class="input__label-content input__label-content--akira">Этаж</span>
									</label>
								</span>
								<div data-help="lift_help" class="checkbox_block checkbox_block_basic">
									<ul>
										<li><input id="lift" name="lift" value="1" type="checkbox"  ';
										if ($Row['lift'] == 1) echo 'checked';
										echo ' 
										><label for="lift">Лифт</label></li>
									</ul>
								</div>
							</section>
							<div id="select_rooms" class="help">Укажите количество комнат в вашем объекте.</div>
							<div id="select_guests" class="help">Укажите количество гостей, которых вы готовы принять в своём объекте.</div>
							<div id="area_help" class="help">Укажите общую площадь вашего объекта.</div>
							<div id="number_floor_help" class="help">Укажите количество этажей в вашем доме.</div>
							<div id="floor_help" class="help">Укажите этаж на котором размещён ваш объект.</div>
							<div id="lift_help" class="help">Укажите есть ли лифт в доме.</div>
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
	<script>
		(function() {
			// trim polyfill : https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/Trim
			if (!String.prototype.trim) {
				(function() {
					// Make sure we trim BOM and NBSP
					var rtrim = /^[\s\uFEFF\xA0]+|[\s\uFEFF\xA0]+$/g;
					String.prototype.trim = function() {
						return this.replace(rtrim, '');
					};
				})();
			}

			[].slice.call( document.querySelectorAll( 'input.input__field' ) ).forEach( function( inputEl ) {
				// in case the input is already filled..
				if( inputEl.value.trim() !== '' ) {
					classie.add( inputEl.parentNode, 'input--filled' );
				}

				// events:
				inputEl.addEventListener( 'focus', onInputFocus );
				inputEl.addEventListener( 'blur', onInputBlur );
			} );
			function onInputFocus( ev ) {
				classie.add( ev.target.parentNode, 'input--filled' );
			}
			function onInputBlur( ev ) {
				if( ev.target.value.trim() === '' ) {
					classie.remove( ev.target.parentNode, 'input--filled' );
				}
			}
		})();
	</script>
</body>
</html>