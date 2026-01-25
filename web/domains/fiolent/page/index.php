<?php
	Head('Главная страница');
?>
<link rel="stylesheet" type="text/css" href="/resource/css/slider.css" />
<script src="/resource/js/modernizr.custom.53451.js"></script>
</head>
<body>
	<div class="wrapper">
	<?php
		HeaderMenu();
	?>
		<main class="content">
			<h1>Горный отдых в Крыму. Мыс Фиолент.</h1>
			<section id="dg-container" class="dg-container">
				<div class="dg-wrapper">
					<a href="/gallery#/resource/gallery/large/6.jpg"><img src="/resource/images/1.jpg" alt="image01"></a>
					<a href="/gallery#/resource/gallery/large/2.jpg"><img src="/resource/images/2.jpg" alt="image02"></a>
					<a href="/gallery#/resource/gallery/large/8.jpg"><img src="/resource/images/3.jpg" alt="image03"></a>
				</div>
			</section>
			<p>Добро пожаловать на наш сайт. Здесь мы расскажем Вам о мысе Фиолент и предложим провести незабываемый отдых в горах.</p>
			<div class="VideoBlock">
				<iframe width="100%" height="360" src="https://www.youtube.com/embed/fliAXrvqy2A" frameborder="0" allowfullscreen></iframe>
			</div>
			<div class="TextBlock">
				<p>Чистейшее море и <a href="https://ru.wikipedia.org/wiki/%D0%AF%D1%88%D0%BC%D0%BE%D0%B2%D1%8B%D0%B9_%D0%BF%D0%BB%D1%8F%D0%B6" target="_blank">Яшмовый пляж</a> на мысе Фиолент порадует даже искушенных туристов.</p>
			</div>
			<div class="TextBlock">
				<p>Горы, скалы, множество спусков, троп и пещер - то что нужно активным туристам.</p>
			</div>
			<div class="VideoBlock-2">
				<iframe width="100%" height="360" src="https://www.youtube.com/embed/U2uPFuw73oQ" frameborder="0" allowfullscreen></iframe>
			</div>
			<div class="TextBlock-2">
				<p>Благодаря своему расположению, мыс Фиолент, расположенный в Крымских горах, станет местом отдыха для туристов любой возрастной категории с любыми интересами.</p>
			</div>
		</main>
	</div>
	<script type="text/javascript" src="/resource/js/jquery.gallery.js"></script>
	<script type="text/javascript">
		$(function() {
			$('#dg-container').gallery({
				autoplay	:	true
			});
		});
	</script/>
	<footer class="footer">
	<?php
		Footer();
	?>
	</footer>

</body>
</html>