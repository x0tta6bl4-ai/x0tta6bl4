<?php
	ULogin(1);
	$Param['id'] += 0;
	if (!$Param['id']) MessageSend(1, 'Не указан ID материала', '/loads');
	$Row = mysqli_fetch_assoc(mysqli_query($CONNECT, "SELECT * FROM `$Page` WHERE `id` = $Param[id]"));
	$Table = $Row['type'];
	if ($_POST['submit']) {
		if ($_POST['title'] != $Row['title']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `title` = '$_POST[title]' WHERE `id` = $Param[id]");
		}
		if ($_POST['description'] != $Row['description']) {
			mysqli_query($CONNECT, "UPDATE `$Table` SET `description` = '$_POST[description]' WHERE `id` = $Param[id]");
		}
		MessageSend(2, 'Информация сохранена.', '/'.$Row['type'].'/sleeps/id/'.$Param['id']);
	}
	Head('Редактировать объект');
?>
<link rel="stylesheet" type="text/css" href="/resource/css/checkbox.css" />
<link rel="stylesheet" type="text/css" href="/resource/css/inputs.css" />
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
				<h1 class="basic_title">Расскажите о вашем объекте.</h1>
				<div class="info_box">
				<?php
					echo '
						<form method="POST" action="/'.$Row['type'].'/description/id/'.$Param['id'].'" class="ac-custom ac-checkbox ac-boxfill" autocomplete="off">
							<span data-help="title_help" class="input input--akira">
								<input class="input__field input__field--akira" type="text" name="title" value="'.$Row['title'].'"/>
								<label class="input__label input__label--akira" for="input-22">
									<span class="input__label-content input__label-content--akira">Название объекта</span>
								</label>
							</span>
							<div data-help="description_help" class="textarea_box">
								<h2 class="description_title">Описание объекта</h2>
								<textarea name="description">'.$Row['description'].'</textarea>
							</div>
							<div id="title_help" class="help">Укажите короткое название вашего объекта.</div>
							<div id="description_help" class="help">Расскажите о вашем объекте подробнее.</div>
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