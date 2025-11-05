<header class="cd-main-header">
	<a href="/" class="cd-logo"><img src="/resource/img/cd-logo.svg" alt="Logo"></a>
	<div class="cd-search is-hidden">
		<form action="#0">
			<input type="search" placeholder="Поиск...">
		</form>
	</div> <!-- cd-search -->
	<?php 
		Buttons();
	?>
	<?php 
		if ($_SESSION['USER_LOGIN_IN'] == 1 and $Page == 'index') {
			echo '<a href="#" class="cd-nav-trigger" id="open-button">Меню<span></span></a>';
		}
	?>
	<div class="overlay"></div>
</header>
<script src="resource/js/jquery-2.1.4.js"></script>
<script src="resource/js/main.js"></script>
<script src="resource/js/classie.js"></script>
<script src="resource/js/uiMorphingButton_fixed.js"></script>
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