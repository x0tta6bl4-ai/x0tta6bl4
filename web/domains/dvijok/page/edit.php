<?php
	ULogin(1);
	Head('Личный кабинет');
?>
<link rel="stylesheet" type="text/css" href="/resource/css/form.css" />
</head>
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
				<div class="page">
					<?php
						if ($_SESSION['USER_AVATAR'] == 0) $Avatar = 0;
						else $Avatar = $_SESSION['USER_AVATAR'].'/'.$_SESSION['USER_ID'];
						echo '
							<img = src="/resource/avatar/'.$Avatar.'.jpg" width="200" height="200" alt="Аватар">
							<br> ID ползователя '.$_SESSION['USER_ID'].'
							<br> Дата регистрации '.$_SESSION['USER_REGDATE'].'
							<br> Email '.$_SESSION['USER_EMAIL'].'
							<br> Имя '.$_SESSION['USER_LOGIN'].'
							<br> Город '.$_SESSION['USER_TOWN'].'
							<br> Аватар '.$_SESSION['USER_AVATAR'].'
							<br> Вход '.$_SESSION['USER_LOGIN_IN'].'
							<form method="POST" action="/account/edit" enctype="multipart/form-data">
								<input type="file" name="avatar">
								<span class="input input--yoko">
									<input class="input__field input__field--yoko" type="text" id="input-1" name="login" maxlength="15" pattern="[А-Яа-яЁё]{3,15}" title="Только кирилица. Не менее 3 и не более 15 символов." value="'.$_SESSION['USER_LOGIN'].'" />
									<label class="input__label input__label--yoko" for="input-1">
										<span class="input__label-content input__label-content--yoko">Ваше имя</span>
									</label>
								</span>
								<span class="input input--yoko">
									<input class="input__field input__field--yoko" type="text" id="input-1" name="town" maxlength="15" value="'.$_SESSION['USER_TOWN'].'" />
									<label class="input__label input__label--yoko" for="input-1">
										<span class="input__label-content input__label-content--yoko">Ваш город</span>
									</label>
								</span>
								<span class="input input--yoko">
							<input class="input__field input__field--yoko" type="password" id="input-2" name="opassword" maxlength="15" pattern="[A-Za-z-0-9]{6,15}" title="Только латиница и цифры. Не менее 6 и не более 15 символов." />
							<label class="input__label input__label--yoko" for="input-2">
								<span class="input__label-content input__label-content--yoko">Старый пароль</span>
							</label></span>
						<span class="input input--yoko">
							<input class="input__field input__field--yoko" type="password" id="input-3" name="npassword" maxlength="15" pattern="[A-Za-z-0-9]{6,15}" title="Только латиница и цифры. Не менее 6 и не более 15 символов." />
							<label class="input__label input__label--yoko" for="input-3">
								<span class="input__label-content input__label-content--yoko">Новый пароль</span>
							</label></span>
								<p><button class="btn btn-large btn-primary" type="submit" value="upload" name="submit">Загрузить</button></p>
							</form>
						';
						?>
						
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
			</div>
		</div>
	</div>
</body>
</html>