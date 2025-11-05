<?php
	$Param['id'] += 0;
	if (!$Param['id']) MessageSend(1, 'Не указан ID материала', '/loads');
	$Row = mysqli_fetch_assoc(mysqli_query($CONNECT, "SELECT `cat`, `name`, `text`, `dimg` FROM `loads` WHERE `id` = $Param[id]"));
	if (!$Row['name']) MessageSend(1, 'Материал не найдена', '/loads');
	if ($_POST['submit'] and $_POST['text'] and $_POST['name'] and $_POST['cat']) {
		$_POST['name'] = FormChars($_POST['name']);
		$_POST['text'] = FormChars($_POST['text']);
		$_POST['cat'] += 0;
		if ($_FILES['img']['tmp_name']) move_uploaded_file($_FILES['img']['tmp_name'], 'catalog/img/'.$Row['dimg'].'/'.$Param['id'].'.jpg');
		mysqli_query($CONNECT, "UPDATE `loads` SET `name` = '$_POST[name]', `cat` = $_POST[cat], `text` = '$_POST[text]' WHERE `id` = $Param[id]");
		MessageSend(2, 'Материал отредактирован.', '/loads/material/id/'.$Param['id']);
	}
	UAccess(2);
	Head('Редактировать файлы');
?>
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
				<div class="form-style">
					<h2>Редактирование файлов</h2>
					<?php
						echo '<form method="POST" action="/loads/edit/id/'.$Param['id'].'" enctype="multipart/form-data">
						<input type="text" name="name" placeholder="Название новости" value="'.$Row['name'].'" required>
						<br><select size="1" name="cat">'.str_replace('value="'.$Row['cat'], 'selected value="'.$Row['cat'], '<option value="1">Категория 1</option><option value="2">Категория 2</option><option value="3">Категория 3</option>').'</select>
						<br>Изображение<input type="file" name="img">
						<br><textarea class="Add" name="text" required>'.str_replace('<br>', '', $Row['text']).'</textarea>
						<br><input type="submit" name="submit" value="Сохранить">
						</form>
						';
					?>
				</div>
			</div>
		</div>
	</div>
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