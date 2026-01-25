<!DOCTYPE html>
<html lang="en" class="no-js">
	<head>
		<meta charset="UTF-8" />
		<meta http-equiv="X-UA-Compatible" content="IE=edge"> 
		<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=0" />
		<title>Поиск жилья</title>
		<meta name="description" content="#" />
		<meta name="keywords" content="#" />
		<meta name="author" content="X0TTA6bI4" />
		<link href='https://fonts.googleapis.com/css?family=Kurale&subset=latin,cyrillic' rel='stylesheet' type='text/css'>
		<link rel="stylesheet" type="text/css" href="css/normalize.css" />
		<link rel="stylesheet" type="text/css" href="css/component.css" />
		<link rel="stylesheet" type="text/css" href="css/content.css" />
		<script src="js/modernizr.custom.js"></script>
		<!--[if IE]>
  		<script src="http://html5shiv.googlecode.com/svn/trunk/html5.js"></script>
		<![endif]-->
	</head>
	<body>
		<div class="container">
			<header class="header_menu">
				<div class="logo"></div>
				<!-- Вход и регистрация -->
				<div class="mockup-content">
					<div class="morph-button morph-button-modal morph-button-modal-2 morph-button-fixed">
						<button type="button">Вход</button>
						<div class="morph-content">
							<div>
								<div class="content-style-form content-style-form-1">
									<span class="icon icon-close">Закрыть</span>
									<h2>Вход</h2>
									<form>
										<p><label>Email</label><input type="text" required /></p>
										<p><label>Пароль</label><input type="password" required /></p>
										<p><button>Войти</button></p>
									</form>
								</div>
							</div>
						</div>
					</div>
					<div class="morph-button morph-button-modal morph-button-modal-3 morph-button-fixed">
						<button type="button">Регистрация</button>
						<div class="morph-content">
							<div>
								<div class="content-style-form content-style-form-2">
									<span class="icon icon-close">Закрыть</span>
									<h2>Регистрация</h2>
									<form method="post" action="index.php">
										<p><label>Email</label><input type="text" class="email" /></p>
										<p><label>Пароль</label><input type="password" class="password" /></p>
										<p><label>Подтверждение пароля</label><input type="password" class="r_password" /></p>
										<p><button type="submit" name="submit">Отправить</button></p>
									</form>
								</div>
							</div>
						</div>
					</div>
				</div>
				<!-- Конец.Вход и регистрация -->
				<script src="js/classie.js"></script>
				<script src="js/uiMorphingButton_fixed.js"></script>
				<script>
					(function() {
						var docElem = window.document.documentElement, didScroll, scrollPosition;

						// trick to prevent scrolling when opening/closing button
						function noScrollFn() {
							window.scrollTo( scrollPosition ? scrollPosition.x : 0, scrollPosition ? scrollPosition.y : 0 );
						}

						function noScroll() {
							window.removeEventListener( 'scroll', scrollHandler );
							window.addEventListener( 'scroll', noScrollFn );
						}

						function scrollFn() {
							window.addEventListener( 'scroll', scrollHandler );
						}

						function canScroll() {
							window.removeEventListener( 'scroll', noScrollFn );
							scrollFn();
						}

						function scrollHandler() {
							if( !didScroll ) {
								didScroll = true;
								setTimeout( function() { scrollPage(); }, 60 );
							}
						};

						function scrollPage() {
							scrollPosition = { x : window.pageXOffset || docElem.scrollLeft, y : window.pageYOffset || docElem.scrollTop };
							didScroll = false;
						};

						scrollFn();

						[].slice.call( document.querySelectorAll( '.morph-button' ) ).forEach( function( bttn ) {
							new UIMorphingButton( bttn, {
								closeEl : '.icon-close',
								onBeforeOpen : function() {
									// don't allow to scroll
									noScroll();
								},
								onAfterOpen : function() {
									// can scroll again
									canScroll();
								},
								onBeforeClose : function() {
									// don't allow to scroll
									noScroll();
								},
								onAfterClose : function() {
									// can scroll again
									canScroll();
								}
							} );
						} );
					})();
				</script>
				<!-- Поиск -->
				<div id="morphsearch" class="morphsearch">
					<form class="morphsearch-form">
						<input class="morphsearch-input" type="search" placeholder="Поиск..."/>
						<button class="morphsearch-submit" type="submit">Поиск</button>
					</form>
					<div class="morphsearch-content">
						<div class="dummy-column">
							<h2>People</h2>
						</div>
						<div class="dummy-column">
							<h2>Popular</h2>
						</div>
						<div class="dummy-column">
							<h2>Recent</h2>
						</div>
					</div><!-- /morphsearch-content -->
					<span class="morphsearch-close"></span>
				</div>
				<!-- Конец. Поиск -->
			</header>
			<div class="overlay"></div>
		</div><!-- /container -->
		<script>
			(function() {
				var morphSearch = document.getElementById( 'morphsearch' ),
					input = morphSearch.querySelector( 'input.morphsearch-input' ),
					ctrlClose = morphSearch.querySelector( 'span.morphsearch-close' ),
					isOpen = isAnimating = false,
					// show/hide search area
					toggleSearch = function(evt) {
						// return if open and the input gets focused
						if( evt.type.toLowerCase() === 'focus' && isOpen ) return false;

						var offsets = morphsearch.getBoundingClientRect();
						if( isOpen ) {
							classie.remove( morphSearch, 'open' );

							// trick to hide input text once the search overlay closes 
							// todo: hardcoded times, should be done after transition ends
							if( input.value !== '' ) {
								setTimeout(function() {
									classie.add( morphSearch, 'hideInput' );
									setTimeout(function() {
										classie.remove( morphSearch, 'hideInput' );
										input.value = '';
									}, 300 );
								}, 500);
							}
							
							input.blur();
						}
						else {
							classie.add( morphSearch, 'open' );
						}
						isOpen = !isOpen;
					};

				// events
				input.addEventListener( 'focus', toggleSearch );
				ctrlClose.addEventListener( 'click', toggleSearch );
				// esc key closes search overlay
				// keyboard navigation events
				document.addEventListener( 'keydown', function( ev ) {
					var keyCode = ev.keyCode || ev.which;
					if( keyCode === 27 && isOpen ) {
						toggleSearch(ev);
					}
				} );
			})();
		</script>
	</body>
</html>