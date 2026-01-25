<?php 
	if ($_SESSION['USER_GROUP'] == 2) $Active = 1;
	else $Active = 0;
	if ($_POST['submit'] and $_POST['text'] and $_POST['name'] and $_POST['cat']) {
		if ($_FILES['img']['type'] != 'image/jpeg') MessageSend(2, 'Не верный тип изображения.');
		if ($_FILES['file']['type'] != 'application/octet-stream') MessageSend(2, 'Не верный тип файла.');
		$_POST['name'] = FormChars($_POST['name']);
		$_POST['text'] = FormChars($_POST['text']);
		$_POST['cat'] += 0;
		$MaxId = mysqli_fetch_row(mysqli_query($CONNECT, 'SELECT max(`id`) FROM `loads`'));
		if ($MaxId[0] == 0) mysqli_query($CONNECT, 'ALTER TABLE `loads` AUTO_INCREMENT = 1');
		$MaxId[0] += 1;
		foreach(glob('catalog/img/*', GLOB_ONLYDIR) as $num => $Dir) {
			$num_img ++;
			$Count = sizeof(glob($Dir.'/*.*'));
			if ($Count < 250) {
				move_uploaded_file($_FILES['img']['tmp_name'], $Dir.'/'.$MaxId[0].'.jpg');
				break;
			}
		}
		MiniIMG('catalog/img/'.$num_img.'/'.$MaxId[0].'.jpg', 'catalog/mini/'.$num_img.'/'.$MaxId[0].'.jpg', 220, 220);
		foreach(glob('catalog/file/*', GLOB_ONLYDIR) as $num => $Dir) {
			$num_file ++;
			$Count = sizeof(glob($Dir.'/*.*'));
			if ($Count < 250) {
				move_uploaded_file($_FILES['file']['tmp_name'], $Dir.'/'.$MaxId[0].'.zip');
				break;
			}
		}
	mysqli_query($CONNECT, "INSERT INTO `loads`  VALUES ('', '$_POST[name]', $_POST[cat], 0, 0, '$_SESSION[USER_LOGIN]', '$_POST[text]', NOW(), $Active, $num_img, $num_file, 0, '')");
	MessageSend(2, 'Файл добавлен', '/loads');
	}
Head('Добавить файл')
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
					MessageShow()
				?>
				<div class="form-style">
					<h2>Добавление файлов</h2>
					<form method="POST" action="/loads/add" enctype="multipart/form-data">
						<span class="input input--yoko">
							<input class="input__field input__field--yoko" type="text" id="input-1" name="name" required />
							<label class="input__label input__label--yoko" for="input-1">
								<span class="input__label-content input__label-content--yoko">Название</span>
							</label>
						</span>
						<br><select size="1" name="cat"><option value="1">Категория 1</option><option value="2">Категория 2</option><option value="3">Категория 3</option></select>
						<br>Файл<input type="file" name="file">
						<br>Изображение<input type="file" name="img">
						<br><br><textarea class="Add" name="text" required></textarea>
						<p><button class="btn btn-large btn-primary" type="submit" value="register" name="submit">Добавить</button></p>
					</form>
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