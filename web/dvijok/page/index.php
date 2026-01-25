<?php
	Head('Главная');
?>
<link rel="stylesheet" type="text/css" href="/resource/css/preview.css" />
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
					MessageShow();
					//while ($Row = mysqli_fetch_assoc($Query)) echo '<a href="/loads/material/id/'.$Row['id'].'"><img src="/catalog/mini/'.$Row['dimg'].'/'.$Row['id'].'.jpg" class="lm" alt="'.$Row['name'].'" title="'.$Row['name'].'"></a>';
				?>
				<ul class="cd-items cd-container">
					<?php
						$Query = mysqli_query($CONNECT, 'SELECT `id`, `dimg`, `date` FROM `loads` ORDER BY `date` DESC LIMIT 12');
						while ($Row = mysqli_fetch_assoc($Query)) echo '
					<li class="cd-item">
						<img src="/resource/img/item-1.jpg" alt="Item Preview">
						<a href="#object'.$Row['id'].'" class="cd-trigger">Подробнее</a>
						<div class="quick-view-content">
							<div class="quick-view-content-wrapper">
								<div class="cd-slider-wrapper">
									<ul class="cd-slider">
										<li class="selected"><img src="/resource/img/item-1.jpg" alt="Product 1"></li>
										<li><img src="/resource/img/item-2.jpg" alt="Product 2"></li>
										<li><img src="/resource/img/item-3.jpg" alt="Product 3"></li>
									</ul> <!-- cd-slider -->
						
									<ul class="cd-slider-navigation">
										<li><a class="cd-next" href="#0">Prev</a></li>
										<li><a class="cd-prev" href="#0">Next</a></li>
									</ul> <!-- cd-slider-navigation -->
								</div> <!-- cd-slider-wrapper -->
					
								<div class="cd-item-info">
									<h2>'.$Row['date'].'</h2>
									<p>'.$Row['date'].'</p>
						
									<ul class="cd-item-action">
										<li><button class="add-to-cart">Добавить к сравнению</button></li>					
										<li><a href="#">Подробнее</a></li>	
									</ul> <!-- cd-item-action -->
								</div> <!-- cd-item-info -->
							</div>
						</div>
					</li> <!-- cd-item -->
					';
					?>
				</ul> <!-- cd-items -->
				<div id="cd-quick-view" class="cd-quick-view">
					<a href="#" class="cd-close">Close</a>
				</div> <!-- cd-quick-view -->

				<div id="cd-quick-view-coverlay"></div>
			</div>
		</div>
		<script src="/resource/js/velocity.min.js"></script>
		<script src="/resource/js/main2.js"></script>
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
</body>
</html>