<?php
	if($_POST['submit'] and $_POST['name'] and $_POST['text']) {
		$_POST['name'] = FormChars($_POST['name']);
		$_POST['text'] = FormChars($_POST['text']);
		mysqli_query($CONNECT, "INSERT INTO `comments`  VALUES ('', '$_POST[name]', '$_POST[text]', NOW())");
		MessageSend (3,'Ваш отзыв добавлен','/comments');
	}
	Head('Отзывы');
?>
<link rel="stylesheet" type="text/css" href="/resource/css/form.css" />
<script src="/resource/js/jquery-2.2.0.min.js"></script>
</head>

<body>

<div class="wrapper">
<?php
	HeaderMenu();
?>
	<main class="content">
	<h1>Отзывы об отдыхе на мысе Фиолент</h1>
		<div class="FormBox">
			<form id="ad_com"method="POST">
				<div class="form-group">
					<div class="controls">
						<input type="text" id="name" class="floatLabel" name="name" required>
						<label for="name">Ваше имя</label>
					</div>
				</div>
				<div class="form-group">
					<div class="controls">
						<textarea name="text" class="floatLabel ChatMessage" id="comments" required></textarea>
						<label for="comments">Отзыв</label>
						<br>
						<br>
						<button value="save" name="submit">Добавить</button>
					</div>
				</div>
			</form>
			<script>
			$(function(){
				$('#ad_com').attr({'action': '/comments'});
			});
			</script>
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
		<?php
			MessageShow();
		?>
		<div class="ChatBox">
		<?php
			$Query = mysqli_query($CONNECT, 'SELECT * FROM `comments` ORDER By `time` DESC LIMIT 50');
			while ($Row = mysqli_fetch_assoc($Query)) echo '<div class="ChatBlock"><span>'.$Row['name'].' | '.$Row['time'].'</span><p>'.$Row['message'].'</p></div>';
		?>
		</div>
	</main>
</div>

<footer class="footer">
<?php
	Footer();
?>
</footer>

</body>
</html>