<?php
	Head('Контакты');
?>
<link rel="stylesheet" type="text/css" href="/resource/css/form.css" />
</head>
<body>
<div class="wrapper">
<?php
	HeaderMenu();
?>
	<main class="content">
		<div class="MailBox">
			<form id="ad_com"method="POST">
				<div class="form-group">
					<div class="controls">
						<input type="text" id="name" class="floatLabel" name="nameFF" required>
						<label for="name">Ваше имя</label>
					</div>
				</div>
				<div class="form-group">
					<div class="controls">
						<input type="email" id="name" class="floatLabel" name="contactFF" required>
						<label for="email">Ваш email</label>
					</div>
				</div>
				<div class="form-group">
					<div class="controls">
						<textarea name="messageFF" class="floatLabel ChatMessage" id="comments" required></textarea>
						<label for="comments">Отзыв</label>
						<br>
						<br>
						<button value="save" name="submit">Отправить</button>
					</div>
				</div>
			</form>
		</div>
		<div class="ContactBox">
			<h1>Мыс Фиолент</h1>
			<h2>Координаты:</h2>
			<p><a href="https://maps.yandex.ru/959/sevastopol/?ll=33.462425%2C44.525962&z=16&l=sat%2Cskl&poi%5Bpoint%5D=33.462832%2C44.525154&text=44%C2%B031%2733.0%22N%2033%C2%B027%2754.8%22E&sll=33.465156%2C44.526052&sspn=0.005107%2C0.002099&ol=geo&ouri=ymapsbm1%3A%2F%2Fgeo%3Fll%3D33.462%252C44.531%26spn%3D0.060%252C0.039%26text%3D%25D0%25A0%25D0%25BE%25D1%2581%25D1%2581%25D0%25B8%25D1%258F%252C%2520%25D0%25A1%25D0%25B5%25D0%25B2%25D0%25B0%25D1%2581%25D1%2582%25D0%25BE%25D0%25BF%25D0%25BE%25D0%25BB%25D1%258C%252C%2520%25D0%259A%25D1%2580%25D0%25B5%25D0%25BF%25D0%25BE%25D1%2581%25D1%2582%25D0%25BD%25D0%25BE%25D0%25B5%2520%25D1%2588%25D0%25BE%25D1%2581%25D1%2581%25D0%25B5" target="_blank">44°31'33.0"N 33°27'54.8"E</a></p>
			<br>
			<h2>Телефон</h2>
			<p>+7 (978) 854-70-30</p>
			<p>+7 (978) 854-70-24</p>
			<br>
			<h2>Email</h2>
			<p>ks.aist@yandex.ru</p>
			<br>
			<h2>Социальные сети</h2>
			<a href="https://vk.com"><img src="/resource/images/vk.png" height="40" width="40"></a>
			<a href="https://ok.ru"><img src="/resource/images/ok.png" height="40" width="40"></a>
			
		</div>
		<script>
			(function($) {
			  function floatLabel(inputType) {
				$(inputType).each(function() {
				  var $this = $(this);
				  // on focus add cladd active to label
				  $this.focus(function() {
					$this.next().addClass("active");
				  });
				  //on blur check field and remove class if needed
				  $this.blur(function() {
					if ($this.val() === '' || $this.val() === 'blank') {
					  $this.next().removeClass();
					}
				  });
				});
			  }
			  floatLabel(".floatLabel");
			})(jQuery);
		</script>
		<script>
		document.getElementById('ad_com').addEventListener('submit', function(evt){
		  var http = new XMLHttpRequest(), f = this;
		  evt.preventDefault();
		  http.open("POST", "/mail", true);
		  http.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");
		  http.send("nameFF=" + f.nameFF.value + "&contactFF=" + f.contactFF.value + "&messageFF=" + f.messageFF.value);
		  http.onreadystatechange = function() {
			if (http.readyState == 4 && http.status == 200) {
			  alert(http.responseText + ', Ваше сообщение отправлено.\nМы ответим Вам в ближайшее время!');    
			  f.messageFF.removeAttribute('value'); // очистить поле сообщения (две строки)
			  f.messageFF.value='';
			}
		  }
		  http.onerror = function() {
			alert('Извините, данные не были переданы');
		  }
		}, false);
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