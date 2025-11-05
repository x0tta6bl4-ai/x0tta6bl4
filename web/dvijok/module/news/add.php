<?php
	ULogin(1);
	if ($_SESSION['USER_GROUP'] == 2) $Active = 1;
	else $Active = 0;
	
	if ($_POST['submit'] and $_POST['text'] and $_POST['name'] and $_POST['cat']){
		$_POST['name'] = FormChars($_POST['name']);
		$_POST['text'] = FormChars($_POST['text']);
		$_POST['cat'] += 0;
		mysqli_query($CONNECT, "INSERT INTO `news`  VALUES ('', '$_POST[name]', $_POST[cat], 0, '$_SESSION[USER_LOGIN]', '$_POST[text]', NOW(), $Active, 0, '')");
		MessageSend(2, 'Новость добавлена', '/news');

	}
	Head('Добавить новость');
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
					<h2>Добавление новостей</h2>
					<form method="POST" action="/news/add">
						<span class="input input--yoko">
							<input class="input__field input__field--yoko" type="text" id="input-1" name="name" required />
							<label class="input__label input__label--yoko" for="input-1">
								<span class="input__label-content input__label-content--yoko">Название</span>
							</label>
						</span>
						<br><select size="1" name="cat"><option value="1">Категория 1</option><option value="2">Категория 2</option><option value="3">Категория 3</option></select>
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