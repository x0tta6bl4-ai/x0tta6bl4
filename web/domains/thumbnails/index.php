<?php 
require 'config.php'; //Подключаем файл конфигурации
require 'process.php'; //Подключаем файл-обработчик

if(isset($_FILES['fupload'])) {
	
	if(preg_match('/[.](jpg)|(gif)|(png)$/', //Ставим допустимые форматы изображений для загрузки
	 $_FILES['fupload']['name'])) {
		
		$filename = $_FILES['fupload']['name'];
		$source = $_FILES['fupload']['tmp_name'];	
		$target = $path_to_image_directory . $filename;
		
		move_uploaded_file($source, $target);
		
		createThumbnail($filename);		
	}
}
?>

<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html>

<head>
	<meta http-equiv="content-type" content="text/html; charset=windows-1251" />
	<meta name="author" content="" />
	<title>Делаем миниатюры на лету с использованием PHP</title>
</head>

<body>
	<h1>Загрузка изображений:</h1>
	<form enctype="multipart/form-data" action="" method="post">
		<input type="file" name="fupload" />
		<input type="submit" value="Загрузить" />
	</form>
</body>
</html>