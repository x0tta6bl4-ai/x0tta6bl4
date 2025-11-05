<?php
	ULogin(0);
	Head('Авторизация');
?>
<link rel="stylesheet" type="text/css" href="/resource/css/buttons.css" />
<link rel="stylesheet" type="text/css" href="/resource/css/form.css" />
</head>
<body>
	<div class="container">
		<?php
			include ('include/header.php');
		?>
		<div class="menu-wrap">
			<?php
				include ('include/menu.php');
			?>
		</div>
		<div class="content-wrap">
			<div class="content">
				<?php
					MessageShow()
				?>
				<div class="form-style">
					<h2>Вход</h2>
					<form method="POST" action="/account/login">
						<span class="input input--yoko">
							<input class="input__field input__field--yoko" type="email" id="input-2" name="email" required />
							<label class="input__label input__label--yoko" for="input-2">
								<span class="input__label-content input__label-content--yoko">Email</span>
							</label></span>
						<span class="input input--yoko">
							<input class="input__field input__field--yoko" type="password" id="input-3" name="password" maxlength="15" pattern="[A-Za-z-0-9]{6,15}" title="Только латиница и цифры. Не менее 6 и не более 15 символов." required />
							<label class="input__label input__label--yoko" for="input-3">
								<span class="input__label-content input__label-content--yoko">Пароль</span>
							</label></span>
						<p><input type="checkbox" name="remember"> Запомнить</p>
						<p><button class="btn btn-large btn-primary" type="submit" value="register" name="submit">Отправить</button></p>
						<div class="alert info">
							<p><a href="/restore">Забыли пароль?</a></p>
						</div>
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