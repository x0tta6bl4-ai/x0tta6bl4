<?php
$photo = $_FILES['uploaded_file']['tmp_name'];
$name = md5($photo) . '.jpg';
$dir = substr(md5(microtime()), mt_rand(0, 30), 2) . '/' . substr(md5(microtime()), mt_rand(0, 30), 2);
$path = 'uploads/'.$dir . '/' . $name; # по этому пути сохраняем фотку

if (isset($_FILES['uploaded_file'])) {
	if (!mkdir('uploads/'.$dir, 0, true)) {
		MessageSend(1, 'Директория не создана.', '/'.$Row['type'].'/photo/id/'.$Param['id']);
	}
	$imagick = new Imagick($photo); 
	$imagick->setCompression(imagick::COMPRESSION_JPEG); 
	$imagick->setCompressionQuality(90); 
	$imagick->stripImage(); 
	$imagick->thumbnailImage(1024, 0);
	$imagick->writeImage($photo);
	if (move_uploaded_file($photo, $path)) {
		mysqli_query($CONNECT, "INSERT INTO `photo` VALUES ('', '$_SESSION[USER_ID]', '$_SESSION[object_id]', '$path')");
		unset ($_SESSION['object_id']);
    } 
	else {
        MessageSend(1, 'Фотографии не загружены.', '/'.$Row['type'].'/photo/id/'.$Param['id']);
    }
} 
else {
    MessageSend(1, 'Ошибка.','/object/photo/');
}
?>