<?php
	ULogin(0);
	Head('Восстановление пароля');
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
					<h2>Регистрация</h2>
					<form method="POST" action="/account/restore">
						<span class="input input--yoko">
							<input class="input__field input__field--yoko" type="email" id="input-2" name="email" required />
							<label class="input__label input__label--yoko" for="input-2">
								<span class="input__label-content input__label-content--yoko">Email</span>
							</label></span>
						<p><button class="btn btn-large btn-primary" type="submit" value="register" name="submit">Отправить</button></p>
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