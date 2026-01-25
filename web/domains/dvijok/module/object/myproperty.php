<?php 
	ULogin(1);
	Head('Добавить файл');
?>
<link rel="stylesheet" type="text/css" href="/resource/css/myproperty.css" />
</head>
<body>
	<div class="container">
		<script src="/resource/js/notificationFx.js"></script>
		<?php
			MessageShow();
			include ('include/header.php');
			include ('include/menu_object.php');
		?>
		<div class="content-wrap">
			<div class="content">
				<?php
					$Query = mysqli_query($CONNECT, "SELECT * FROM `appartment` WHERE `added` = $_SESSION[USER_ID]");
					while ($Row = mysqli_fetch_assoc($Query)) echo '
					<div class="object_box">
						<div class="photo_box">
							<a href="/'.$Row['type'].'/basic/id/'.$Row['id'].'">
								<img src="/catalog/object/0.jpg" width="150" height="150" alt="Нет фото">
							</a>
						</div>
						<div class="info_box">
							<br>'.$Row['number_guests'].'
							<br>'.$Row['city'].'
							<br>'.$Row['date'].'
						</div>
					</div>
					';
				?>
			</div>
		</div>
	</div>
</body>
</html>