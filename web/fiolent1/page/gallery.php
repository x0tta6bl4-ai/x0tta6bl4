<?php
	Head('Главная страница');
?>
<link rel="stylesheet" type="text/css" href="/resource/css/font-awesome.min.css" />
<link rel="stylesheet" type="text/css" href="/resource/css/jgallery.min.css?v=1.5.0" />
<script type="text/javascript" src="/resource/js/jgallery.min.js?v=1.5.0"></script>
<script type="text/javascript" src="/resource/js/touchswipe.min.js"></script>
</head>
<body>

<div class="wrapper">
<?php
	HeaderMenu();
?>
	<main class="content">
		<div id="gallery">
			<a href="/resource/gallery/large/1.jpg"><img src="/resource/gallery/thumbs/1.jpg" alt="Территория гостиницы" /></a>
			<a href="/resource/gallery/large/2.jpg"><img src="/resource/gallery/thumbs/2.jpg" alt="Территория гостиницы" /></a>
			<a href="/resource/gallery/large/3.jpg"><img src="/resource/gallery/thumbs/3.jpg" alt="Беседка с мангалом" /></a>
			<a href="/resource/gallery/large/4.jpg"><img src="/resource/gallery/thumbs/4.jpg" alt="Номер с двухспальной кроватью" /></a>
			<a href="/resource/gallery/large/5.jpg"><img src="/resource/gallery/thumbs/5.jpg" alt="Столовая" /></a>
			<a href="/resource/gallery/large/6.jpg"><img src="/resource/gallery/thumbs/6.jpg" alt="Вид с мыса Фиолент" /></a>
			<a href="/resource/gallery/large/7.jpg"><img src="/resource/gallery/thumbs/7.jpg" alt="Вид с мыса Фиолент" /></a>
			<a href="/resource/gallery/large/8.jpg"><img src="/resource/gallery/thumbs/8.jpg" alt="Вид с мыса Фиолент" /></a>
			<a href="/resource/gallery/large/9.jpg"><img src="/resource/gallery/thumbs/9.jpg" alt="Пляж Яшмовый" /></a>
			<a href="/resource/gallery/large/10.jpg"><img src="/resource/gallery/thumbs/10.jpg" alt="Пляж Яшмовый" /></a>
			<a href="/resource/gallery/large/11.jpg"><img src="/resource/gallery/thumbs/11.jpg" alt="Пляж Яшмовый" /></a>
		</div>
<script type="text/javascript">
$( function(){
    $( "#gallery" ).jGallery( {
        "transition":"rotateCubeLeftOut_rotateCubeLeftIn",
        "transitionBackward":"rotateCubeRightOut_rotateCubeRightIn",
        "transitionCols":"1",
        "transitionRows":"1",
        "thumbnailsPosition":"bottom",
        "thumbType":"image",
        "textColor":"000000",
        "mode":"standard"
    } );
} );
</script>
	</main>
</div>

<footer class="footer">
<?php
	Footer();
?>
</footer>

</body>
</html>